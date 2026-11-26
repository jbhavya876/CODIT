"""
Audit lifecycle service replacing process-global state (ADR-0001).

Manages:
- Audit persistence in SQLAlchemy (derived metadata, findings, scorecard, graph_json)
- Legacy two-step staging in STAGING_DIR/<audit_id>/ with 0700 perms and hard purge
- Signed `codit_audit` cookie tokens (HMAC-SHA256, consistent across workers)
- Enumerated audit_events emission (zero repo-derived free text)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import shutil
import time
import uuid
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import Request, Response
from sqlalchemy import desc, select

from backend.app.collectors import run_all_collectors
from backend.app.collectors.models import AuditFinding
from backend.app.config import Config
from backend.app.db.engine import session_scope
from backend.app.db.models import AuditEventRow, AuditRow, FindingRow
from backend.app.delivery.models import AuditReport
from backend.app.diagrams.mermaid_generator import generate_architecture_diagram
from backend.app.graph.assembler import assemble_graph
from backend.app.ingestion.models import FileEntry
from backend.app.ingestion.zip_extract import purge_extracted_files
from backend.app.ml.explainability import compute_shap_score_attributions
from backend.app.ml.onnx_scorer import run_onnx_inference
from backend.app.parsers.ast.treesitter_walker import parse_codebase_ast
from backend.app.parsers.manifest import extract_manifests_and_signals
from backend.app.scoring.roadmap_synthesis import (
    AuditRoadmap,
    RoadmapActionItem,
    RoadmapPhase,
    generate_audit_roadmap,
)
from backend.app.scoring.rubric import RUBRIC_VERSION
from backend.app.scoring.rules_engine import AuditScorecard, DimensionalScore, score_audit
from backend.app.services import graph_service
from backend.app.services.demo_graph import GraphHandle, serialize_graph

log = logging.getLogger(__name__)

COOKIE_NAME = "codit_audit"
ENGINE_VERSION = "3.0.0"

ALLOWED_EVENT_CODES = {
    "ingest_started",
    "ingest_done",
    "history_started",
    "history_done",
    "history_not_assessed",
    "parse_done",
    "collect_done",
    "licenses_started",
    "licenses_done",
    "score_done",
    "report_ready",
    "audit_failed",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _get_cookie_secret() -> bytes:
    """
    Resolve cookie HMAC secret consistently across multiple uvicorn workers.
    Prefers COOKIE_SECRET env var; otherwise uses/creates a mode-0600 key file
    alongside staging data so sibling worker processes share the same secret.
    """
    env_secret = os.getenv("COOKIE_SECRET") or Config.COOKIE_SECRET
    if env_secret:
        return env_secret.encode("utf-8")

    key_path = Path(Config.STAGING_DIR).parent / ".cookie_secret"
    key_path.parent.mkdir(parents=True, exist_ok=True)
    if key_path.exists():
        raw = key_path.read_text(encoding="utf-8").strip()
        if raw:
            return raw.encode("utf-8")

    generated = secrets.token_urlsafe(32)
    try:
        fd = os.open(str(key_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(generated)
        return generated.encode("utf-8")
    except FileExistsError:
        return key_path.read_text(encoding="utf-8").strip().encode("utf-8")


def sign_audit_id(audit_id: str) -> str:
    sig = hmac.new(_get_cookie_secret(), audit_id.encode("utf-8"), hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).decode("ascii").rstrip("=")
    return f"{audit_id}.{sig_b64}"


def verify_audit_cookie(token: Optional[str]) -> Optional[str]:
    if not token or "." not in token:
        return None
    audit_id, _, provided_sig = token.partition(".")
    if not audit_id or not provided_sig:
        return None
    expected = sign_audit_id(audit_id)
    if hmac.compare_digest(expected, token):
        return audit_id
    return None


def set_audit_cookie(response: Response, audit_id: str) -> None:
    max_age = Config.AUDIT_RETENTION_HOURS * 3600
    response.set_cookie(
        key=COOKIE_NAME,
        value=sign_audit_id(audit_id),
        httponly=True,
        samesite="lax",
        secure=(Config.ENV == "production"),
        max_age=max_age,
        path="/",
    )


def get_audit_id_from_request(request: Optional[Request]) -> Optional[str]:
    if request is None:
        return None
    return verify_audit_cookie(request.cookies.get(COOKIE_NAME))


def generate_audit_id() -> str:
    return secrets.token_urlsafe(16)


def _staging_path(audit_id: str) -> Path:
    return Path(Config.STAGING_DIR) / audit_id


def purge_staging(audit_id: str, temp_dir: Optional[str] = None) -> None:
    if temp_dir:
        td = Path(temp_dir)
        if td.exists():
            purge_extracted_files(td)
    sp = _staging_path(audit_id)
    if sp.exists():
        shutil.rmtree(sp, ignore_errors=True)


def emit_event(
    audit_id: str,
    stage: str,
    code: str,
    level: str = "info",
    data: Optional[Dict[str, int | str | bool]] = None,
) -> None:
    if code not in ALLOWED_EVENT_CODES:
        raise ValueError(f"Disallowed event code: {code}")
    with session_scope() as session:
        session.add(
            AuditEventRow(
                audit_id=audit_id,
                ts=_utcnow(),
                stage=stage,
                level=level,
                code=code,
                data_json=data or {},
            )
        )


def _summarize_entries(entries: List[FileEntry]) -> Dict[str, Any]:
    lang_counts: Dict[str, int] = {}
    total_bytes = 0
    for e in entries:
        lang_counts[e.language] = lang_counts.get(e.language, 0) + 1
        total_bytes += e.size or len(e.content or "")
    return {
        "languages": lang_counts,
        "file_count": len(entries),
        "total_size_kb": round(total_bytes / 1024, 1),
    }


def create_audit(
    source_kind: str,
    source_ref: str,
    *,
    options: Optional[Dict[str, Any]] = None,
    status: str = "queued",
) -> str:
    audit_id = generate_audit_id()
    now = _utcnow()
    expires_at = now + timedelta(hours=Config.AUDIT_RETENTION_HOURS)
    with session_scope() as session:
        session.add(
            AuditRow(
                id=audit_id,
                created_at=now,
                expires_at=expires_at,
                status=status,
                source_kind=source_kind,
                source_ref=source_ref[:256],
                options_json=options or {},
                rubric_version=RUBRIC_VERSION,
                engine_version=ENGINE_VERSION,
            )
        )
    return audit_id


def create_staged_audit(
    target: str,
    target_type: str,
    entries: List[FileEntry],
    temp_dir: Optional[Path] = None,
) -> Tuple[str, Dict[str, Any]]:
    """
    Stage ingested file manifest in STAGING_DIR/<audit_id>/ for the legacy
    two-step ingest -> analyze flow. File contents NEVER enter SQLite/Postgres.
    """
    audit_id = create_audit(source_kind=target_type, source_ref=target, status="queued")
    now = _utcnow()
    summary = _summarize_entries(entries)

    stage_dir = _staging_path(audit_id)
    stage_dir.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(stage_dir, 0o700)
    except OSError:
        pass

    manifest = [
        {"path": e.path, "size": e.size, "language": e.language, "content": e.content}
        for e in entries
    ]
    (stage_dir / "entries.json").write_text(json.dumps(manifest), encoding="utf-8")
    meta = {
        "audit_id": audit_id,
        "target": target,
        "type": target_type,
        "temp_dir": str(temp_dir) if temp_dir else None,
        **summary,
    }
    (stage_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")

    with session_scope() as session:
        row = session.get(AuditRow, audit_id)
        if row is not None:
            row.staged_at = now
            row.coverage_json = {
                "files_total": len(entries),
                "files_scanned": len(entries),
                "partial": False,
                "graph_truncated": False,
                "history": {"assessed": False, "reason": "not_enabled_in_legacy_flow"},
            }

    emit_event(audit_id, "ingest", "ingest_done", data={"file_count": len(entries)})
    return audit_id, {
        "target": target,
        "type": target_type,
        "temp_dir": str(temp_dir) if temp_dir else None,
        "entries": entries,
        **summary,
    }


def save_history_result(audit_id: str, history_result: Any) -> None:
    """Persist scrubbed HistoryResult (no messages/names/emails/source) on AuditRow."""
    cov_dict = history_result.coverage.model_dump()
    proc_dict = {
        "source_commit": history_result.source_commit,
        "source_tree": history_result.source_tree,
        "commits": [
            {
                "sha": c.sha,
                "short": c.short,
                "date": c.date,
                "author_key": c.author_key,
                "has_agent_trailer": c.has_agent_trailer,
                "agent_id": c.agent_id,
                "attribution_basis": c.attribution_basis,
                "attribution_confidence": c.attribution_confidence,
                "claims_tests_pass": c.claims_tests_pass,
                "skipped_deep": c.skipped_deep,
                "files_changed": c.files_changed,
                "prod_lines_delta": c.prod_lines_delta,
                "test_lines_delta": c.test_lines_delta,
                "shallow_baseline": c.shallow_baseline,
            }
            for c in history_result.commits
        ],
        "head_tooling_present": history_result.head_tooling_present,
        "series": history_result.series,
    }
    with session_scope() as session:
        row = session.get(AuditRow, audit_id)
        if row is not None:
            row.source_commit = history_result.source_commit
            row.source_tree = history_result.source_tree
            existing_cov = dict(row.coverage_json or {})
            existing_cov["history"] = cov_dict
            if not cov_dict.get("assessed") or cov_dict.get("shallow_boundary") or cov_dict.get("caps_hit"):
                existing_cov["partial"] = True
            row.coverage_json = existing_cov
            row.process_json = proc_dict
            row.ownership_json = history_result.ownership or {}


def get_staged_codebase(audit_id: str) -> Optional[Dict[str, Any]]:
    stage_dir = _staging_path(audit_id)
    meta_file = stage_dir / "meta.json"
    entries_file = stage_dir / "entries.json"
    if not meta_file.exists() or not entries_file.exists():
        return None
    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    raw_entries = json.loads(entries_file.read_text(encoding="utf-8"))
    entries = [FileEntry(**item) for item in raw_entries]
    meta["entries"] = entries
    return meta


def get_latest_staged_codebase() -> Dict[str, Any]:
    """Compatibility helper for legacy tests reading staged zip metadata."""
    with session_scope() as session:
        row = session.execute(
            select(AuditRow)
            .where(AuditRow.staged_at.is_not(None))
            .order_by(desc(AuditRow.created_at))
            .limit(1)
        ).scalar_one_or_none()
        if row is not None:
            staged = get_staged_codebase(row.id)
            if staged is not None:
                return staged
    return {
        "target": "demo",
        "type": "demo",
        "entries": [],
        "languages": {},
        "file_count": 0,
        "total_size_kb": 0,
        "temp_dir": None,
    }


def get_audit_row(audit_id: str) -> Optional[AuditRow]:
    if not audit_id:
        return None
    now = _utcnow()
    with session_scope() as session:
        row = session.get(AuditRow, audit_id)
        if row is None:
            return None
        exp = row.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp <= now or row.status == "expired":
            return None
        session.expunge(row)
        return row


def run_audit_pipeline(
    audit_id: str,
    entries: List[FileEntry],
    target_name: str,
    target_type: str,
    goal: str = "production",
    temp_dir: Optional[str] = None,
) -> AuditReport:
    """
    Execute analysis pipeline isolated to `audit_id`, persist derived outputs to DB,
    and purge staging + temporary directories in `finally`.
    """
    with session_scope() as session:
        row = session.get(AuditRow, audit_id)
        if row is not None:
            row.status = "running"
            row.started_at = _utcnow()

    emit_event(audit_id, "parse", "ingest_started")
    try:
        # 1. Parse manifests & signals
        deps, signals = extract_manifests_and_signals(entries)

        # 2. Parse ASTs & internal imports
        ast_map = parse_codebase_ast(entries)
        emit_event(audit_id, "parse", "parse_done", data={"ast_files": len(ast_map)})

        # 3. Run collectors
        findings = run_all_collectors(entries, deps, ast_map)
        emit_event(audit_id, "collect", "collect_done", data={"findings_count": len(findings)})

        # 4. Deterministic scoring (v1.0.0 in P0; v2.0.0 added in P6)
        scorecard = score_audit(findings)
        emit_event(audit_id, "score", "score_done", data={"overall": scorecard.overall_score})

        # 5. Isolated graph assembly
        if target_type == "demo" and not entries:
            from database import seed_data

            nodes = []
            for nid, lbl in seed_data.LABELS.items():
                props = dict(seed_data.ALL_PROPERTIES.get(nid, {}))
                props["id"] = nid
                props["type"] = lbl
                props["labels"] = lbl
                nodes.append(props)
            edges = [
                {"source_id": src, "rel_type": rtype, "target_id": dst}
                for src, rtype, dst in seed_data.RELATIONSHIPS
            ]
        else:
            nodes, edges = assemble_graph(entries, deps, signals, ast_map, findings)

        graph_json, graph_truncated, kept_nodes, kept_edges = serialize_graph(nodes, edges)
        handle = graph_service.build_handle_from_json(audit_id, graph_json, truncated=graph_truncated)

        # 6. Diagrams & leaderboard strictly against this audit's isolated handle
        arch_diagram = generate_architecture_diagram(kept_nodes, kept_edges)
        leaderboard = graph_service.leaderboard(limit=8, graph=handle)

        # 7. Roadmap synthesis
        roadmap = generate_audit_roadmap(
            scorecard=scorecard,
            findings=findings,
            critical_components=leaderboard,
            goal=goal or "production",
        )

        tier_map = {
            "public": "free_public",
            "private": "paid_private",
            "zip": "premium_zip",
            "demo": "free_public",
        }
        access_tier = tier_map.get(target_type, "free_public")

        # 8. ONNX & SHAP insights strictly against this audit's isolated handle
        graph_stats = graph_service.stats(graph=handle)
        onnx_metrics = run_onnx_inference(entries, findings, graph_stats)
        shap_explainability = compute_shap_score_attributions(scorecard, findings, entries, graph_stats)
        ml_insights = {
            "onnx_metrics": onnx_metrics,
            "shap_explainability": shap_explainability,
        }

        source_deleted = target_type == "zip"
        report_id = f"audit-{uuid.uuid4().hex[:8]}"
        created_ts = time.time()

        report = AuditReport(
            report_id=report_id,
            target_name=target_name,
            target_type=target_type,
            access_tier=access_tier,
            created_at=created_ts,
            scorecard=scorecard,
            findings=findings,
            roadmap=roadmap,
            architecture_diagram_mermaid=arch_diagram,
            criticality_leaderboard=leaderboard,
            stats=graph_stats,
            source_deleted=source_deleted,
            ml_insights=ml_insights,
            rubric_version=RUBRIC_VERSION,
            audit_id=audit_id,
        )

        # 9. Persist ONLY derived data (NO source code) in SQLAlchemy
        scorecard_dict = {
            "rubric_version": RUBRIC_VERSION,
            "overall_score": scorecard.overall_score,
            "phase": scorecard.phase,
            "has_critical_blocker": scorecard.has_critical_blocker,
            "findings_summary": scorecard.findings_summary,
            "dimensions": {k: asdict(v) for k, v in scorecard.dimensions.items()},
        }
        roadmap_dict = {
            "goal": roadmap.goal,
            "summary_narrative": roadmap.summary_narrative,
            "blockers_summary": roadmap.blockers_summary,
            "phases": [asdict(p) for p in roadmap.phases],
            "all_recommendations_attributed": roadmap.all_recommendations_attributed,
        }

        with session_scope() as session:
            row = session.get(AuditRow, audit_id)
            if row is not None:
                row.status = "completed"
                row.rubric_version = RUBRIC_VERSION
                row.scorecard_json = scorecard_dict
                row.graph_json = graph_json
                row.staged_at = None
                existing_cov = dict(row.coverage_json or {})
                existing_cov["graph_truncated"] = graph_truncated
                existing_cov.setdefault("files_total", len(entries))
                existing_cov.setdefault("files_scanned", len(entries))
                row.coverage_json = existing_cov
                row.report_meta_json = {
                    "report_id": report_id,
                    "access_tier": access_tier,
                    "created_at": created_ts,
                    "source_deleted": source_deleted,
                    "roadmap": roadmap_dict,
                    "architecture_diagram_mermaid": arch_diagram,
                    "criticality_leaderboard": leaderboard,
                    "stats": graph_stats,
                    "ml_insights": ml_insights,
                }
                # Replace findings for idempotent re-runs on the same audit_id
                session.query(FindingRow).filter(FindingRow.audit_id == audit_id).delete()
                for f in findings:
                    session.add(
                        FindingRow(
                            finding_uid=f.id,
                            audit_id=audit_id,
                            fingerprint=f.fingerprint or f.id,
                            rule_id=f.rule_id,
                            dimension=f.dimension,
                            severity=f.severity,
                            confidence=f.confidence,
                            basis=f.basis,
                            evidence_file=f.evidence_file,
                            evidence_line=f.evidence_line,
                            commit_sha=f.commit_sha,
                            description=f.description,
                            remediation=f.remediation or "",
                            component_id=f.component_id,
                            params_json=f.params or {},
                        )
                    )

        emit_event(audit_id, "deliver", "report_ready")
        return report

    except Exception:
        with session_scope() as session:
            row = session.get(AuditRow, audit_id)
            if row is not None:
                row.status = "failed"
                row.error_code = "internal_error"
                row.staged_at = None
        emit_event(audit_id, "deliver", "audit_failed", level="error")
        raise
    finally:
        purge_staging(audit_id, temp_dir=temp_dir)


def get_graph_for_audit(audit_id: Optional[str]) -> Optional[GraphHandle]:
    if not audit_id:
        return None
    cached = graph_service.cache_get_graph(audit_id)
    if cached is not None:
        return cached
    row = get_audit_row(audit_id)
    if row is None or not row.graph_json:
        return None
    truncated = bool((row.coverage_json or {}).get("graph_truncated", False))
    return graph_service.build_handle_from_json(audit_id, row.graph_json, truncated=truncated)


def get_report_for_audit(audit_id: str) -> Optional[AuditReport]:
    now = _utcnow()
    with session_scope() as session:
        row = session.get(AuditRow, audit_id)
        if row is None:
            return None
        exp = row.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp <= now or row.status != "completed" or not row.scorecard_json or not row.report_meta_json:
            return None

        finding_rows = (
            session.execute(select(FindingRow).where(FindingRow.audit_id == audit_id).order_by(FindingRow.id))
            .scalars()
            .all()
        )
        findings = [
            AuditFinding(
                id=fr.finding_uid,
                dimension=fr.dimension,
                severity=fr.severity,
                confidence=fr.confidence,
                description=fr.description,
                evidence_file=fr.evidence_file,
                evidence_line=fr.evidence_line,
                rule_id=fr.rule_id,
                remediation=fr.remediation,
                component_id=fr.component_id,
                fingerprint=fr.fingerprint,
                basis=fr.basis,
                commit_sha=fr.commit_sha,
                params=fr.params_json or {},
            )
            for fr in finding_rows
        ]

        sc = row.scorecard_json
        dims = {k: DimensionalScore(**v) for k, v in sc["dimensions"].items()}
        scorecard = AuditScorecard(
            overall_score=sc["overall_score"],
            phase=sc["phase"],
            dimensions=dims,
            has_critical_blocker=sc["has_critical_blocker"],
            findings_summary=sc["findings_summary"],
        )

        meta = row.report_meta_json
        rm = meta["roadmap"]
        phases = [
            RoadmapPhase(
                phase_name=p["phase_name"],
                target_timeline=p["target_timeline"],
                objective=p["objective"],
                action_items=[RoadmapActionItem(**item) for item in p.get("action_items", [])],
            )
            for p in rm.get("phases", [])
        ]
        roadmap = AuditRoadmap(
            goal=rm["goal"],
            summary_narrative=rm["summary_narrative"],
            blockers_summary=rm["blockers_summary"],
            phases=phases,
            all_recommendations_attributed=rm.get("all_recommendations_attributed", True),
        )

        return AuditReport(
            report_id=meta["report_id"],
            target_name=row.source_ref,
            target_type=row.source_kind,
            access_tier=meta["access_tier"],
            created_at=meta["created_at"],
            scorecard=scorecard,
            findings=findings,
            roadmap=roadmap,
            architecture_diagram_mermaid=meta["architecture_diagram_mermaid"],
            criticality_leaderboard=meta["criticality_leaderboard"],
            stats=meta["stats"],
            source_deleted=meta.get("source_deleted", False),
            ml_insights=meta.get("ml_insights", {}),
            rubric_version=row.rubric_version,
            audit_id=row.id,
        )
