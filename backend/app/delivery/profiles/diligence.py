"""
Due-diligence acquirer/investor report profile (P7).

Strict section ordering (Section 1..8):
1. Verdict, phase qualifiers, and coverage (stated first)
2. Red-flag register (blockers with appendix references)
3. IP and licensing register (disclaimer included)
4. Process-integrity timeline (always with attribution limitation string)
5. Key-person exposure (masked labels: Contributor A, B, ...)
6. Remediation estimate (effort range; dollars only when hourly_rate supplied)
7. Methodology and limitations
8. Appendix: complete evidenced finding index
"""

from __future__ import annotations

from typing import Any, Dict, List

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

_BLOCKER_DESCRIPTIONS = {
    "critical_security": "Critical vulnerability or committed credential at HEAD.",
    "copyleft_conflict": "Strong or network copyleft dependency conflict in production scope.",
    "history_secret_unrotated": "Credential detected in git history (still requires rotation even if removed at HEAD).",
    "high_confidence_test_integrity_event": "High-confidence high-severity process/test integrity removal or weakening.",
}


def build_diligence_view(ctx: AuditContext) -> Dict[str, Any]:
    sc = ctx.report.scorecard
    findings = ctx.findings
    appendix: List[Dict[str, Any]] = []
    for f in findings:
        appendix.append({
            "finding_id": f.id,
            "rule_id": f.rule_id,
            "dimension": f.dimension,
            "severity": f.severity,
            "confidence": f.confidence,
            "basis": f.basis,
            "evidence_file": f.evidence_file,
            "evidence_line": f.evidence_line,
            "commit_sha": safe_hex_sha(f.commit_sha),
            "fingerprint": f.fingerprint,
            "description": f.description,
            "remediation": f.remediation,
        })

    # 1. Verdict & Coverage (always stated first)
    not_assessed_items = summarize_not_assessed(ctx)
    verdict_and_coverage = {
        "overall_score": sc.overall_score,
        "phase": sc.phase,
        "rubric_version": ctx.report.rubric_version,
        "phase_qualifiers": qualifier_texts(list(getattr(sc, "phase_qualifiers", []) or [])),
        "coverage": {
            "files_scanned": int(ctx.coverage.get("files_scanned", 0)),
            "files_total": int(ctx.coverage.get("files_total", 0)),
            "history": ctx.coverage.get("history") or {"assessed": False, "reason": "history_not_assessed"},
            "licenses": ctx.coverage.get("licenses") or {"total": 0, "resolved": 0, "unresolved": 0, "resolved_pct": 0},
        },
        "not_assessed": not_assessed_items,
        "dimensions": {
            k: {
                "score": getattr(v, "score", None),
                "assessed": getattr(v, "assessed", True),
                "not_applicable": getattr(v, "not_applicable", False),
                "reason": getattr(v, "reason", None),
            }
            for k, v in sc.dimensions.items()
        },
    }

    # 2. Red-flag register
    red_flags: List[Dict[str, Any]] = []
    blockers = list(getattr(sc, "blockers", []) or [])
    for bcode in blockers:
        matching_ids: List[str] = []
        if bcode == "critical_security":
            matching_ids = [f.id for f in findings if f.dimension == "security" and f.severity == "critical"]
        elif bcode == "copyleft_conflict":
            matching_ids = [f.id for f in findings if (f.rule_id or "").upper() in ("LIC-001", "LIC-002") and f.severity in ("critical", "high")]
        elif bcode == "history_secret_unrotated":
            matching_ids = [f.id for f in findings if (f.rule_id or "").upper() == "AGT-010"]
        elif bcode == "high_confidence_test_integrity_event":
            matching_ids = [
                f.id for f in findings
                if f.dimension == "agent_integrity" and f.confidence == "high" and f.severity in ("high", "critical")
            ]
        red_flags.append({
            "blocker_code": bcode,
            "summary": _BLOCKER_DESCRIPTIONS.get(bcode, bcode.replace("_", " ")),
            "count": len(matching_ids),
            "appendix_refs": matching_ids,
        })

    # 3. IP and licensing register
    lic_findings_ids = [f.id for f in findings if f.dimension == "licenses" or (f.rule_id or "").upper().startswith("LIC-")]
    ip_and_licensing = {
        "disclaimer": LICENSE_DISCLAIMER,
        "project_license": (ctx.licenses or {}).get("project_license"),
        "coverage": (ctx.licenses or {}).get("coverage") or (ctx.coverage.get("licenses") or {}),
        "register": (ctx.licenses or {}).get("register") or [],
        "appendix_refs": lic_findings_ids,
    }

    # 4. Process-integrity timeline
    hist_cov = ctx.coverage.get("history") or {}
    history_assessed = bool(hist_cov.get("assessed", False))
    proc_finding_ids = [
        f.id for f in findings
        if f.dimension == "agent_integrity" or (f.rule_id or "").upper().startswith(("AGT-", "GRD-"))
    ]
    if history_assessed:
        process_timeline: Dict[str, Any] = {
            "assessed": True,
            "attribution": ctx.process.get("attribution") or {},
            "attribution_limitation": ATTRIBUTION_LIMITATION,
            "series": ctx.process.get("series") or [],
            "flagged_commits": [
                {
                    "sha": safe_hex_sha(f.commit_sha),
                    "rule_id": f.rule_id,
                    "severity": f.severity,
                    "confidence": f.confidence,
                    "evidence_file": f.evidence_file,
                    "appendix_refs": [f.id],
                }
                for f in findings
                if f.id in set(proc_finding_ids)
            ],
            "appendix_refs": proc_finding_ids,
        }
    else:
        reason = str(hist_cov.get("reason") or "history_not_assessed")
        process_timeline = {
            "assessed": False,
            "reason": reason,
            "status_text": format_not_assessed(reason),
            "attribution_limitation": ATTRIBUTION_LIMITATION,
            "appendix_refs": [],
        }

    # 5. Key-person exposure (masked labels ONLY: Contributor A, B, ...)
    if history_assessed and ctx.ownership:
        contributors = list(ctx.ownership.get("contributors") or [])
        masked_contributors = [
            {
                "label": c.get("label") or f"Contributor {chr(65 + idx)}",
                "commits": int(c.get("commits", 0)),
                "share_pct": float(c.get("share_pct", 0.0)),
            }
            for idx, c in enumerate(contributors)
        ]
        key_person_exposure: Dict[str, Any] = {
            "assessed": True,
            "top_contributor_share_pct": float(ctx.ownership.get("top_contributor_share_pct", 0.0)),
            "single_owner_dirs_count": int(ctx.ownership.get("single_owner_dirs_count", 0)),
            "contributors": masked_contributors,
        }
    elif not history_assessed:
        reason = str(hist_cov.get("reason") or "history_not_assessed")
        key_person_exposure = {
            "assessed": False,
            "reason": reason,
            "status_text": format_not_assessed(reason),
            "contributors": [],
        }
    else:
        key_person_exposure = {
            "assessed": True,
            "top_contributor_share_pct": 0.0,
            "single_owner_dirs_count": 0,
            "contributors": [],
        }

    # 6. Remediation estimate
    remediation_estimate = {
        **ctx.effort,
        "appendix_refs": [f.id for f in findings],
    }

    # 7. Methodology & limitations
    methodology_and_limitations = {
        "methodology": METHODOLOGY_PARAGRAPH,
        "attribution_limitation": ATTRIBUTION_LIMITATION,
        "license_disclaimer": LICENSE_DISCLAIMER,
        "not_assessed": not_assessed_items,
    }

    return {
        "profile": "diligence",
        "target_name": ctx.report.target_name,
        "rubric_version": ctx.report.rubric_version,
        "generated_at": ctx.report.created_at,
        "verdict_and_coverage": verdict_and_coverage,
        "red_flag_register": red_flags,
        "ip_and_licensing_register": ip_and_licensing,
        "process_integrity_timeline": process_timeline,
        "key_person_exposure": key_person_exposure,
        "remediation_estimate": remediation_estimate,
        "methodology_and_limitations": methodology_and_limitations,
        "appendix": appendix,
    }
