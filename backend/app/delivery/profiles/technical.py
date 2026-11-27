"""Technical report profile (P7): full engineering report + Process, Licenses, and Effort."""

from __future__ import annotations

from typing import Any, Dict

from backend.app.delivery.profiles.shared import (
    ATTRIBUTION_LIMITATION,
    LICENSE_DISCLAIMER,
    METHODOLOGY_PARAGRAPH,
    AuditContext,
    format_not_assessed,
    qualifier_texts,
    safe_hex_sha,
    summarize_not_assessed,
)


def build_technical_view(ctx: AuditContext) -> Dict[str, Any]:
    base = ctx.report.to_dict()
    sc = ctx.report.scorecard
    hist_cov = ctx.coverage.get("history") or {}
    history_assessed = bool(hist_cov.get("assessed", False))

    if history_assessed:
        process_section: Dict[str, Any] = {
            "assessed": True,
            "coverage": hist_cov,
            "attribution": ctx.process.get("attribution") or {},
            "attribution_limitation": ATTRIBUTION_LIMITATION,
            "series": ctx.process.get("series") or [],
            "head_tooling_present": bool(ctx.process.get("head_tooling_present", False)),
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
                for c in (ctx.process.get("commits") or [])
                if c.get("flagged") or c.get("claims_tests_pass")
            ][:50],
        }
    else:
        reason = str(hist_cov.get("reason") or "history_not_assessed")
        process_section = {
            "assessed": False,
            "reason": reason,
            "status_text": format_not_assessed(reason),
            "attribution_limitation": ATTRIBUTION_LIMITATION,
        }

    licenses_section: Dict[str, Any] = dict(ctx.licenses or {})
    if not licenses_section:
        licenses_section = {
            "disclaimer": LICENSE_DISCLAIMER,
            "project_license": None,
            "coverage": ctx.coverage.get("licenses") or {"total": 0, "resolved": 0, "unresolved": 0, "resolved_pct": 0},
            "register": [],
        }
    else:
        licenses_section.setdefault("disclaimer", LICENSE_DISCLAIMER)

    base.update({
        "profile": "technical",
        "coverage": ctx.coverage,
        "phase_qualifiers": qualifier_texts(list(getattr(sc, "phase_qualifiers", []) or [])),
        "blockers": list(getattr(sc, "blockers", []) or []),
        "not_assessed": summarize_not_assessed(ctx),
        "effort": ctx.effort,
        "process": process_section,
        "licenses": licenses_section,
        "methodology": METHODOLOGY_PARAGRAPH,
    })
    return base
