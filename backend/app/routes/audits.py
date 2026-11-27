"""
Section 10 Audit Lifecycle API Routes (`/api/audits/*`, `/api/audits/{id}/report`).

All unknown, expired, or non-existent audit IDs return identical `404 not_found`.
Commercial profiles (`diligence`, `executive`, `underwriting`) are gated behind
`EntitlementProvider` (`FreeTierProvider` / `X402Provider`).
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from sqlalchemy import asc, func, select

from backend.app.config import Config
from backend.app.db.engine import session_scope
from backend.app.db.models import AttestationRow, AuditEventRow, AuditRow, FindingRow
from backend.app.delivery.entitlements import enforce_entitlement
from backend.app.delivery.profiles.diligence import build_diligence_view
from backend.app.delivery.profiles.executive import build_executive_view
from backend.app.delivery.profiles.shared import (
    ATTRIBUTION_LIMITATION,
    LICENSE_DISCLAIMER,
    build_audit_context,
    format_not_assessed,
    safe_hex_sha,
)
from backend.app.delivery.profiles.technical import build_technical_view
from backend.app.delivery.profiles.underwriting import build_underwriting_view
from backend.app.delivery.renderers import render_minimal_pdf, render_profile_html, render_profile_markdown
from backend.app.history.acquire import (
    HistoryAcquisitionError,
    acquire_bare_history,
    validate_branch_name,
    validate_github_repo_input,
)
from backend.app.history.models import HistoryCoverage, HistoryOptions, HistoryResult
from backend.app.history.worker import run_history_worker
from backend.app.ingestion.git_clone import GitCloneError, clone_private_repo
from backend.app.ingestion.github_fetch import GitHubIngestionError, fetch_public_repo
from backend.app.ingestion.zip_extract import (
    ZipSecurityError,
    extract_git_history_from_zip,
    extract_zip,
    purge_extracted_files,
)
from backend.app.jobs.runner import submit_job
from backend.app.scoring.effort_model import validate_hourly_rate
from backend.app.services import audit_service, graph_service

router = APIRouter(prefix="/api/audits", tags=["audits"])

_STAGE_PROGRESS = {
    "ingest_started": ("ingest", 10),
    "ingest_done": ("ingest", 25),
    "history_started": ("history", 30),
    "history_done": ("history", 45),
    "history_not_assessed": ("history", 45),
    "parse_done": ("parse", 55),
    "collect_done": ("collect", 70),
    "licenses_started": ("licenses", 75),
    "licenses_done": ("licenses", 85),
    "score_done": ("score", 95),
    "report_ready": ("deliver", 100),
    "audit_failed": ("deliver", 100),
}


def _must_audit(audit_id: str) -> AuditRow:
    row = audit_service.get_audit_row(audit_id)
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Audit not found."})
    return row


def _mark_audit_failed(audit_id: str, error_code: str) -> None:
    with session_scope() as session:
        row = session.get(AuditRow, audit_id)
        if row is not None:
            row.status = "failed"
            row.error_code = error_code
            row.staged_at = None
    audit_service.emit_event(audit_id, "deliver", "audit_failed", level="error")


def _run_background_zip_audit(
    audit_id: str,
    filename: str,
    zip_bytes: bytes,
    goal: str,
    hist_opts: HistoryOptions,
) -> None:
    temp_dir = Path(tempfile.mkdtemp(prefix="audit_zip_"))
    git_temp_dir = Path(tempfile.mkdtemp(prefix="audit_zip_git_"))
    try:
        entries = extract_zip(zip_bytes, temp_dir)
        audit_service.emit_event(audit_id, "ingest", "ingest_done", data={"file_count": len(entries)})
        if not hist_opts.enabled:
            hist_res = HistoryResult(coverage=HistoryCoverage(assessed=False, reason="history_disabled"))
            audit_service.emit_event(audit_id, "history", "history_not_assessed")
        else:
            audit_service.emit_event(audit_id, "history", "history_started")
            extracted_ok, reason = extract_git_history_from_zip(zip_bytes, git_temp_dir)
            if not extracted_ok:
                hist_res = HistoryResult(coverage=HistoryCoverage(assessed=False, reason=reason))
                audit_service.emit_event(audit_id, "history", "history_not_assessed")
            else:
                hist_res = run_history_worker(git_temp_dir, options=hist_opts)
                audit_service.emit_event(
                    audit_id,
                    "history",
                    "history_done" if hist_res.coverage.assessed else "history_not_assessed",
                    data={"commits": hist_res.coverage.commits_analyzed},
                )
        audit_service.save_history_result(audit_id, hist_res)
        audit_service.run_audit_pipeline(
            audit_id=audit_id,
            entries=entries,
            target_name=filename,
            target_type="zip",
            goal=goal,
            temp_dir=str(temp_dir),
        )
    except ZipSecurityError:
        purge_extracted_files(temp_dir)
        _mark_audit_failed(audit_id, "invalid_archive")
    except Exception:
        purge_extracted_files(temp_dir)
        _mark_audit_failed(audit_id, "internal_error")
    finally:
        purge_extracted_files(git_temp_dir)


def _run_background_repo_audit(
    audit_id: str,
    source_kind: str,
    target: str,
    branch: Optional[str],
    token: Optional[str],
    goal: str,
    hist_opts: HistoryOptions,
) -> None:
    temp_dir = Path(tempfile.mkdtemp(prefix="audit_repo_")) if source_kind == "private" else None
    hist_dir = Path(tempfile.mkdtemp(prefix="codit_hist_bare_"))
    try:
        if source_kind == "public":
            entries = fetch_public_repo(target, ref=branch or "main")
        elif source_kind == "private":
            assert temp_dir is not None
            entries = clone_private_repo(target, token or "", temp_dir, branch=branch)
        else:
            entries = []
        audit_service.emit_event(audit_id, "ingest", "ingest_done", data={"file_count": len(entries)})

        if source_kind == "demo" or not hist_opts.enabled:
            reason = "not_applicable" if source_kind == "demo" else "history_disabled"
            hist_res = HistoryResult(coverage=HistoryCoverage(assessed=False, reason=reason))
            audit_service.emit_event(audit_id, "history", "history_not_assessed")
        else:
            audit_service.emit_event(audit_id, "history", "history_started")
            try:
                acquire_bare_history(target, hist_dir, depth=hist_opts.max_commits, branch=branch, access_token=token)
                hist_res = run_history_worker(hist_dir, options=hist_opts)
                audit_service.emit_event(
                    audit_id,
                    "history",
                    "history_done" if hist_res.coverage.assessed else "history_not_assessed",
                    data={"commits": hist_res.coverage.commits_analyzed},
                )
            except HistoryAcquisitionError:
                hist_res = HistoryResult(coverage=HistoryCoverage(assessed=False, reason="history_unavailable"))
                audit_service.emit_event(audit_id, "history", "history_not_assessed")

        audit_service.save_history_result(audit_id, hist_res)
        audit_service.run_audit_pipeline(
            audit_id=audit_id,
            entries=entries,
            target_name=target,
            target_type=source_kind,
            goal=goal,
            temp_dir=str(temp_dir) if temp_dir else None,
        )
    except (GitHubIngestionError, GitCloneError, HistoryAcquisitionError):
        if temp_dir:
            purge_extracted_files(temp_dir)
        _mark_audit_failed(audit_id, "invalid_source")
    except Exception:
        if temp_dir:
            purge_extracted_files(temp_dir)
        _mark_audit_failed(audit_id, "internal_error")
    finally:
        purge_extracted_files(hist_dir)


@router.post("", status_code=202)
async def create_audit_job(request: Request, response: Response):
    content_type = (request.headers.get("content-type") or "").lower()
    if "multipart/form-data" in content_type:
        form = await request.form()
        up_file = form.get("file")
        if up_file is None or not hasattr(up_file, "read"):
            raise HTTPException(status_code=400, detail={"code": "invalid_archive", "message": "Missing ZIP archive file."})
        filename = getattr(up_file, "filename", None) or "archive.zip"
        if not filename.lower().endswith(".zip"):
            raise HTTPException(status_code=400, detail={"code": "invalid_archive", "message": "Only .zip uploads are supported."})

        raw_bytes = await up_file.read()
        max_bytes = Config.MAX_INDIVIDUAL_FILE_MB * 1024 * 1024
        if len(raw_bytes) > max_bytes:
            raise HTTPException(
                status_code=413,
                detail={"code": "repo_too_large", "message": f"Archive exceeds {Config.MAX_INDIVIDUAL_FILE_MB} MB limit."},
            )

        archive_sha = hashlib.sha256(raw_bytes).hexdigest()
        goal = str(form.get("goal") or "production")
        hist_enabled = str(form.get("history_enabled", "true")).lower() != "false"
        max_commits = max(1, min(int(form.get("history_max_commits") or Config.HISTORY_MAX_COMMITS), Config.HISTORY_MAX_COMMITS))
        max_days = max(1, min(int(form.get("history_max_days") or Config.HISTORY_MAX_DAYS), Config.HISTORY_MAX_DAYS))
        hist_opts = HistoryOptions(enabled=hist_enabled, max_commits=max_commits, max_days=max_days)

        audit_id = audit_service.create_audit(
            source_kind="zip",
            source_ref=filename,
            status="queued",
            options={"goal": goal, "history": hist_opts.model_dump()},
            archive_sha256=archive_sha,
        )
        audit_service.emit_event(audit_id, "ingest", "ingest_started")
        audit_service.set_audit_cookie(response, audit_id)
        submit_job(_run_background_zip_audit, audit_id, filename, raw_bytes, goal, hist_opts)
        return {"audit_id": audit_id, "status": "queued"}

    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail={"code": "invalid_source", "message": "Expected JSON or multipart body."}) from exc

    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail={"code": "invalid_source", "message": "Request body must be a JSON object."})

    source_kind = str(body.get("type") or body.get("source_kind") or "public").lower()
    if source_kind not in ("public", "private", "demo"):
        raise HTTPException(status_code=400, detail={"code": "invalid_source", "message": "Unsupported source type."})

    goal = str(body.get("goal") or "production")
    hist_raw = body.get("history") or {}
    if not isinstance(hist_raw, dict):
        hist_raw = {}
    hist_opts = HistoryOptions(
        enabled=bool(hist_raw.get("enabled", True)) if source_kind != "demo" else False,
        max_commits=max(1, min(int(hist_raw.get("max_commits", Config.HISTORY_MAX_COMMITS)), Config.HISTORY_MAX_COMMITS)),
        max_days=max(1, min(int(hist_raw.get("max_days", Config.HISTORY_MAX_DAYS)), Config.HISTORY_MAX_DAYS)),
    )

    branch = body.get("ref") or body.get("branch")
    token = body.get("token")
    target = str(body.get("url") or body.get("repo") or ("Demo System" if source_kind == "demo" else "")).strip()

    if source_kind in ("public", "private"):
        try:
            owner, repo_name = validate_github_repo_input(target)
            safe_branch = validate_branch_name(branch)
        except HistoryAcquisitionError as exc:
            raise HTTPException(status_code=400, detail={"code": "invalid_source", "message": str(exc)}) from exc
        normalized_target = f"https://github.com/{owner}/{repo_name}" if source_kind == "public" else f"{owner}/{repo_name}"
        if source_kind == "private" and not token:
            raise HTTPException(status_code=400, detail={"code": "invalid_source", "message": "Access token required for private repository."})
    else:
        normalized_target = "Demo System"
        safe_branch = None

    audit_id = audit_service.create_audit(
        source_kind=source_kind,
        source_ref=normalized_target,
        status="queued",
        options={"goal": goal, "history": hist_opts.model_dump()},
    )
    audit_service.emit_event(audit_id, "ingest", "ingest_started")
    audit_service.set_audit_cookie(response, audit_id)
    submit_job(_run_background_repo_audit, audit_id, source_kind, normalized_target, safe_branch, token, goal, hist_opts)
    return {"audit_id": audit_id, "status": "queued"}


@router.get("/{audit_id}")
def get_audit_status(audit_id: str):
    row = _must_audit(audit_id)
    with session_scope() as session:
        last_ev = session.execute(
            select(AuditEventRow)
            .where(AuditEventRow.audit_id == audit_id)
            .order_by(AuditEventRow.id.desc())
            .limit(1)
        ).scalar_one_or_none()
        stage = last_ev.stage if last_ev else ("deliver" if row.status == "completed" else "ingest")
        progress = 100 if row.status == "completed" else (_STAGE_PROGRESS.get(last_ev.code, (stage, 5))[1] if last_ev else 0)

    out: Dict[str, Any] = {
        "audit_id": row.id,
        "status": row.status,
        "stage": stage,
        "progress": progress,
        "source_kind": row.source_kind,
        "source_ref": row.source_ref,
        "source_commit": row.source_commit,
        "source_archive_sha256": row.source_archive_sha256,
        "rubric_version": row.rubric_version,
        "coverage": row.coverage_json or {},
        "error_code": row.error_code,
    }
    if row.status == "completed" and row.scorecard_json is not None:
        out["scorecard"] = row.scorecard_json
    return out


@router.get("/{audit_id}/events")
def get_audit_events(audit_id: str, after: int = Query(default=0, ge=0)):
    _must_audit(audit_id)
    with session_scope() as session:
        rows = session.execute(
            select(AuditEventRow)
            .where(AuditEventRow.audit_id == audit_id, AuditEventRow.id > after)
            .order_by(asc(AuditEventRow.id))
            .limit(200)
        ).scalars().all()
        return [
            {
                "id": r.id,
                "ts": r.ts.isoformat().replace("+00:00", "Z"),
                "stage": r.stage,
                "level": r.level,
                "code": r.code,
                "data": r.data_json or {},
            }
            for r in rows
        ]


@router.get("/{audit_id}/findings")
def get_audit_findings(
    audit_id: str,
    dimension: Optional[str] = None,
    severity: Optional[str] = None,
    rule: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=200),
    cursor: int = Query(default=0, ge=0),
):
    _must_audit(audit_id)
    with session_scope() as session:
        stmt = select(FindingRow).where(FindingRow.audit_id == audit_id)
        cnt_stmt = select(func.count(FindingRow.id)).where(FindingRow.audit_id == audit_id)
        if dimension:
            stmt = stmt.where(FindingRow.dimension == dimension)
            cnt_stmt = cnt_stmt.where(FindingRow.dimension == dimension)
        if severity:
            stmt = stmt.where(FindingRow.severity == severity.lower())
            cnt_stmt = cnt_stmt.where(FindingRow.severity == severity.lower())
        if rule:
            stmt = stmt.where(FindingRow.rule_id == rule)
            cnt_stmt = cnt_stmt.where(FindingRow.rule_id == rule)
        if cursor > 0:
            stmt = stmt.where(FindingRow.id > cursor)
        rows = session.execute(stmt.order_by(asc(FindingRow.id)).limit(limit + 1)).scalars().all()
        total = int(session.execute(cnt_stmt).scalar_one() or 0)
        has_more = len(rows) > limit
        page = rows[:limit]
        next_cursor = page[-1].id if has_more and page else None
        items = [
            {
                "id": r.finding_uid,
                "row_id": r.id,
                "fingerprint": r.fingerprint,
                "rule_id": r.rule_id,
                "dimension": r.dimension,
                "severity": r.severity,
                "confidence": r.confidence,
                "basis": r.basis,
                "evidence_file": r.evidence_file,
                "evidence_line": r.evidence_line,
                "commit_sha": r.commit_sha,
                "description": r.description,
                "remediation": r.remediation,
                "component_id": r.component_id,
                "params": r.params_json or {},
            }
            for r in page
        ]
        return {"items": items, "next_cursor": next_cursor, "total": total}


@router.get("/{audit_id}/process")
def get_audit_process(audit_id: str):
    row = _must_audit(audit_id)
    cov = row.coverage_json or {}
    hist_cov = cov.get("history") or {}
    proc = row.process_json or {}
    if not hist_cov.get("assessed"):
        reason = str(hist_cov.get("reason") or "history_not_assessed")
        return {
            "assessed": False,
            "reason": reason,
            "status_text": format_not_assessed(reason),
            "coverage": hist_cov,
            "attribution_limitation": ATTRIBUTION_LIMITATION,
            "series": [],
            "flagged_commits": [],
            "attribution": {},
            "ownership": {},
        }
    return {
        "assessed": True,
        "coverage": hist_cov,
        "series": proc.get("series") or [],
        "flagged_commits": [
            {
                "sha": safe_hex_sha(c.get("sha")),
                "short": safe_hex_sha(c.get("short")),
                "date": c.get("date"),
                "author_key": c.get("author_key"),
                "attribution_basis": c.get("attribution_basis"),
                "attribution_confidence": c.get("attribution_confidence"),
                "claims_tests_pass": bool(c.get("claims_tests_pass", False)),
            }
            for c in (proc.get("commits") or [])
            if c.get("flagged") or c.get("claims_tests_pass")
        ],
        "attribution": proc.get("attribution") or {},
        "attribution_limitation": ATTRIBUTION_LIMITATION,
        "ownership": row.ownership_json or {},
        "head_tooling_present": bool(proc.get("head_tooling_present", False)),
    }


@router.get("/{audit_id}/licenses")
def get_audit_licenses(audit_id: str):
    row = _must_audit(audit_id)
    lic = dict(row.licenses_json or {})
    if not lic:
        cov = (row.coverage_json or {}).get("licenses") or {"total": 0, "resolved": 0, "unresolved": 0, "resolved_pct": 0}
        return {"disclaimer": LICENSE_DISCLAIMER, "project_license": None, "coverage": cov, "register": []}
    lic.setdefault("disclaimer", LICENSE_DISCLAIMER)
    return lic


@router.get("/{audit_id}/report")
def get_audit_profile_report(
    audit_id: str,
    request: Request,
    profile: str = Query(default="technical"),
    format: str = Query(default="json"),
    hourly_rate: Optional[float] = Query(default=None),
):
    if profile not in ("technical", "diligence", "executive", "underwriting"):
        raise HTTPException(status_code=400, detail={"code": "bad_request", "message": "Invalid profile."})
    if format not in ("json", "md", "html", "pdf"):
        raise HTTPException(status_code=400, detail={"code": "bad_request", "message": "Invalid format."})

    try:
        validated_rate = validate_hourly_rate(hourly_rate)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "invalid_rate", "message": str(exc)}) from exc

    row = _must_audit(audit_id)
    report = audit_service.get_report_for_audit(audit_id)
    if report is None:
        raise HTTPException(status_code=409, detail={"code": "audit_not_complete", "message": "Audit report is not ready."})

    decision = enforce_entitlement(
        request,
        resource=f"/api/audits/{audit_id}/report?profile={profile}",
        required=(profile in ("diligence", "executive", "underwriting")),
        audit_row=row,
    )
    if not decision.allowed:
        return JSONResponse(
            status_code=decision.status_code,
            content={"error": {"code": decision.code, "message": decision.message}, "payment_requirements": decision.challenge},
            headers=decision.headers,
        )

    att_id: Optional[str] = None
    with session_scope() as session:
        att_row = session.execute(
            select(AttestationRow)
            .where(AttestationRow.audit_id == audit_id, AttestationRow.revoked_at.is_(None))
            .order_by(AttestationRow.issued_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        if att_row is not None:
            att_id = att_row.id

    ctx = build_audit_context(report, row=row, hourly_rate=validated_rate, attestation_id=att_id)
    if profile == "underwriting":
        data = build_underwriting_view(ctx)
        if format == "json":
            return JSONResponse(content=data, headers=decision.headers)
    elif profile == "diligence":
        data = build_diligence_view(ctx)
    elif profile == "executive":
        data = build_executive_view(ctx)
    else:
        data = build_technical_view(ctx)

    if format == "json":
        return JSONResponse(content=data, headers=decision.headers)
    if format == "md":
        md = render_profile_markdown(profile, data)
        return PlainTextResponse(
            content=md,
            headers={**decision.headers, "Content-Disposition": f"attachment; filename=codit-{profile}-{audit_id}.md"},
        )
    if format == "html":
        html_out = render_profile_html(profile, data)
        return HTMLResponse(content=html_out, headers=decision.headers)

    md_lines = render_profile_markdown(profile, data).splitlines()
    pdf_bytes = render_minimal_pdf(f"CODIT {profile.title()} Report ({audit_id})", md_lines)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={**decision.headers, "Content-Disposition": f"attachment; filename=codit-{profile}-{audit_id}.pdf"},
    )


@router.delete("/{audit_id}", status_code=204)
def delete_audit_endpoint(audit_id: str, response: Response):
    deleted = audit_service.delete_audit(audit_id)
    if not deleted:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Audit not found."})
    response.delete_cookie(key=audit_service.COOKIE_NAME, path="/")
    return Response(status_code=204)
