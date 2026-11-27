"""
Underwriting machine-readable profile (`codit.underwriting.v1`).

Guarantees: ZERO strings derived from the repository (no file paths, messages,
commit authors, branch names, rule descriptions, or package names). Validated against
`schemas/underwriting.v1.json` before returning.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

import jsonschema

from backend.app.delivery.profiles.shared import AuditContext, safe_hex_40, safe_hex_64
from backend.app.scoring.rubric import RUBRIC_2_0_0


@lru_cache(maxsize=1)
def _load_underwriting_schema() -> Dict[str, Any]:
    schema_path = Path(__file__).with_name("schemas") / "underwriting.v1.json"
    return json.loads(schema_path.read_text(encoding="utf-8"))


def _fraction_bucket(assessed: bool, declared_fraction: Optional[float]) -> str:
    if not assessed or declared_fraction is None:
        return "not_assessed"
    if declared_fraction <= 0.0:
        return "none"
    if declared_fraction < 0.25:
        return "low"
    if declared_fraction < 0.60:
        return "medium"
    return "high"


def build_underwriting_view(ctx: AuditContext) -> Dict[str, Any]:
    row = ctx.row
    report = ctx.report
    sc = report.scorecard

    hist_cov = ctx.coverage.get("history") or {}
    history_assessed = bool(hist_cov.get("assessed", False))
    commits_analyzed = int(hist_cov.get("commits_analyzed", 0)) if history_assessed else 0

    lic_cov = ctx.coverage.get("licenses") or {}
    if not lic_cov or lic_cov.get("not_applicable"):
        lic_resolved_pct: Optional[int] = None if lic_cov.get("not_applicable") else 0
    else:
        lic_resolved_pct = int(lic_cov.get("resolved_pct", 0))

    src_kind = (row.source_kind if row else report.target_type) or "zip"
    subject_kind = "git" if src_kind in ("public", "private") else "archive"
    commit_hex = safe_hex_40(ctx.process.get("source_commit") or (row.source_commit if row else None))
    archive_hex = safe_hex_64(row.source_archive_sha256 if row else None)

    if subject_kind == "archive":
        commit_hex = None
    else:
        archive_hex = None

    dims_out: Dict[str, Optional[int]] = {}
    for dname in RUBRIC_2_0_0["dimensions_order"]:
        ds = sc.dimensions.get(dname)
        if ds is None:
            dims_out[dname] = None
        else:
            assessed_flag = getattr(ds, "assessed", True)
            dims_out[dname] = ds.score if (assessed_flag and ds.score is not None) else None

    findings = ctx.findings
    secret_at_head = any(
        f.dimension == "security" and (f.rule_id or "").upper().startswith("SECRET")
        for f in findings
    )
    secret_in_history = any((f.rule_id or "").upper() == "AGT-010" for f in findings)
    critical_vuln = any(
        f.dimension == "security"
        and (f.severity or "").lower() == "critical"
        and (f.rule_id or "").upper().startswith(("CVE-", "GHSA-", "OSV-"))
        for f in findings
    )
    copyleft_conflict = any(
        (f.rule_id or "").upper() in ("LIC-001", "LIC-002")
        and (f.severity or "").lower() in ("critical", "high")
        for f in findings
    )
    test_integrity_90d = "high_confidence_test_integrity_event" in list(getattr(sc, "blockers", []) or [])

    attr = ctx.process.get("attribution") or {}
    declared_fraction = attr.get("declared_fraction")
    bucket = _fraction_bucket(history_assessed, declared_fraction)

    summary = dict(sc.findings_summary or {})
    counts = {
        "critical": int(summary.get("critical", 0)),
        "high": int(summary.get("high", 0)),
        "medium": int(summary.get("medium", 0)),
        "low": int(summary.get("low", 0)),
        "info": int(summary.get("info", 0)),
    }

    att_id = ctx.attestation_id
    if att_id and not str(att_id).startswith("att_"):
        att_id = None

    payload: Dict[str, Any] = {
        "schema": "codit.underwriting.v1",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "rubric_version": str(report.rubric_version or "2.0.0"),
        "engine_version": str((row.engine_version if row else None) or "3.0.0"),
        "subject_kind": subject_kind,
        "commit": commit_hex,
        "archive_sha256": archive_hex,
        "coverage": {
            "files_scanned": int(ctx.coverage.get("files_scanned", len(report.findings))),
            "files_total": int(ctx.coverage.get("files_total", len(report.findings))),
            "history_assessed": history_assessed,
            "commits_analyzed": commits_analyzed,
            "licenses_resolved_pct": lic_resolved_pct,
        },
        "scores": {
            "overall": int(sc.overall_score),
            "phase": str(sc.phase),
            "dimensions": dims_out,
        },
        "flags": {
            "secret_at_head": bool(secret_at_head),
            "secret_in_history": bool(secret_in_history),
            "critical_vulnerability": bool(critical_vuln),
            "copyleft_conflict": bool(copyleft_conflict),
            "test_integrity_event_90d": bool(test_integrity_90d),
            "agent_declared_fraction_bucket": bucket,
        },
        "counts": counts,
        "attestation_id": att_id,
    }

    jsonschema.validate(instance=payload, schema=_load_underwriting_schema())
    return payload
