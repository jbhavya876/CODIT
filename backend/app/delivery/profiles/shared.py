"""Shared fixed disclaimers, reason translation, and audit context loading for P7 profiles."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from codit_core.licenses import LICENSE_DISCLAIMER

from backend.app.collectors.models import AuditFinding
from backend.app.db.models import AuditRow
from backend.app.delivery.models import AuditReport
from backend.app.scoring.effort_model import compute_effort_estimate
from backend.app.scoring.rubric import RUBRIC_2_0_0

METHODOLOGY_PARAGRAPH = (
    "Static analysis of repository contents and history. No code was executed. "
    "This is not a certification, legal opinion, or guarantee."
)
ATTRIBUTION_LIMITATION = (
    "Attribution reflects declarations in commit metadata. Commits without a declaration "
    "are unknown, not human-authored."
)
NOT_ASSESSED_TEMPLATE = "Not assessed \u2014 {reason}."

_HEX_SHA_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")
_HEX_40_RE = re.compile(r"^[0-9a-fA-F]{40}$")
_HEX_64_RE = re.compile(r"^[0-9a-fA-F]{64}$")

_REASON_LABELS = {
    "history_disabled": "git history analysis was disabled for this audit",
    "not_enabled_in_legacy_flow": "git history analysis was disabled in legacy ingest mode",
    "history_not_assessed": "git history evidence was not available",
    "zip_without_git": "archive upload contained no .git history directory",
    "history_failed": "git history acquisition or worker analysis failed within sandbox limits",
    "license_coverage_partial": "fewer than 90% of production dependencies had resolved license identifiers",
    "license_coverage_missing": "dependency license lookup coverage was unavailable",
    "no_dependencies": "repository declared no pinned or unpinned package dependencies",
}


def format_not_assessed(reason_code: Optional[str]) -> str:
    code = (reason_code or "history_not_assessed").strip()
    label = _REASON_LABELS.get(code, code.replace("_", " "))
    return f"Not assessed \u2014 {label}."


def safe_hex_sha(sha: Optional[str]) -> Optional[str]:
    if not sha:
        return None
    s = str(sha).strip()
    return s if _HEX_SHA_RE.match(s) else None


def safe_hex_40(sha: Optional[str]) -> Optional[str]:
    if not sha:
        return None
    s = str(sha).strip()
    return s.lower() if _HEX_40_RE.match(s) else None


def safe_hex_64(digest: Optional[str]) -> Optional[str]:
    if not digest:
        return None
    s = str(digest).strip()
    return s.lower() if _HEX_64_RE.match(s) else None


@dataclass
class AuditContext:
    row: Optional[AuditRow]
    report: AuditReport
    coverage: Dict[str, Any]
    process: Dict[str, Any]
    licenses: Dict[str, Any]
    ownership: Dict[str, Any]
    effort: Dict[str, Any]
    attestation_id: Optional[str] = None

    @property
    def findings(self) -> List[AuditFinding]:
        return self.report.findings


def build_audit_context(
    report: AuditReport,
    row: Optional[AuditRow] = None,
    *,
    hourly_rate: Optional[float] = None,
    attestation_id: Optional[str] = None,
) -> AuditContext:
    cov = dict((row.coverage_json if row else None) or {})
    proc = dict((row.process_json if row else None) or {})
    lic = dict((row.licenses_json if row else None) or {})
    own = dict((row.ownership_json if row else None) or {})
    effort = compute_effort_estimate(report.findings, hourly_rate=hourly_rate)
    return AuditContext(
        row=row,
        report=report,
        coverage=cov,
        process=proc,
        licenses=lic,
        ownership=own,
        effort=effort,
        attestation_id=attestation_id,
    )


def summarize_not_assessed(ctx: AuditContext) -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []
    hist_cov = ctx.coverage.get("history") or {}
    if not hist_cov.get("assessed"):
        reason = str(hist_cov.get("reason") or "history_not_assessed")
        items.append({"dimension": "agent_integrity", "reason": reason, "text": format_not_assessed(reason)})

    lic_cov = ctx.coverage.get("licenses") or {}
    if not lic_cov:
        items.append({"dimension": "licenses", "reason": "license_coverage_missing", "text": format_not_assessed("license_coverage_missing")})
    elif lic_cov.get("not_applicable"):
        items.append({"dimension": "licenses", "reason": "no_dependencies", "text": "Not applicable \u2014 repository declared no dependencies."})
    elif int(lic_cov.get("prod_total", 0)) > 0 and int(lic_cov.get("prod_resolved_pct", 100)) < 90:
        items.append({"dimension": "licenses", "reason": "license_coverage_partial", "text": format_not_assessed("license_coverage_partial")})
    return items


def qualifier_texts(codes: List[str]) -> List[Dict[str, str]]:
    descs = RUBRIC_2_0_0["qualifier_descriptions"]
    return [{"code": c, "text": descs.get(c, c.replace("_", " "))} for c in codes]


__all__ = [
    "ATTRIBUTION_LIMITATION",
    "AuditContext",
    "LICENSE_DISCLAIMER",
    "METHODOLOGY_PARAGRAPH",
    "build_audit_context",
    "format_not_assessed",
    "qualifier_texts",
    "safe_hex_40",
    "safe_hex_64",
    "safe_hex_sha",
    "summarize_not_assessed",
]
