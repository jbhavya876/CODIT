"""
Transparent, assumption-labeled remediation effort model (Gate G6).

Never mixed with or influenced by ONNX "technical debt days" ML estimates.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from backend.app.collectors.models import AuditFinding

EFFORT_MODEL_VERSION = "1.0.0"
HOURS_PER_PERSON_DAY = 8.0
MIN_HOURLY_RATE = 1.0
MAX_HOURLY_RATE = 2000.0

# (min_hours, likely_hours, max_hours, unit_label)
EFFORT_TABLE: Dict[str, Tuple[float, float, float, str]] = {
    "SEC-SECRET": (2.0, 4.0, 8.0, "per unique secret (rotate, purge)"),
    "VULN-DEP": (1.0, 2.0, 6.0, "per dependency"),
    "AGT-001": (2.0, 4.0, 12.0, "per event"),
    "AGT-002": (1.0, 3.0, 8.0, "per event"),
    "AGT-003": (0.5, 1.5, 4.0, "per test file"),
    "AGT-004": (1.0, 2.0, 6.0, "per event"),
    "AGT-005": (0.5, 1.0, 3.0, "per assertion"),
    "AGT-007": (1.0, 2.0, 6.0, "per workflow"),
    "AGT-008": (0.5, 1.0, 3.0, "per gate"),
    "AGT-009": (1.0, 3.0, 8.0, "per burst"),
    "AGT-010": (2.0, 4.0, 12.0, "per unique secret"),
    "AGT-011": (2.0, 6.0, 16.0, "per commit"),
    "AGT-012": (0.25, 0.5, 1.0, "per marker"),
    "LIC-001": (4.0, 16.0, 80.0, "per dependency"),
    "LIC-002": (8.0, 24.0, 120.0, "per dependency"),
    "LIC-003": (0.5, 1.0, 4.0, "per dependency"),
    "LIC-004": (1.0, 2.0, 8.0, "per dependency"),
    "LIC-005": (4.0, 16.0, 80.0, "per dependency"),
    "LIC-006": (0.25, 0.5, 1.0, "per repository"),
    "LIC-007": (1.0, 3.0, 12.0, "per file group"),
    "LIC-008": (1.0, 3.0, 12.0, "per directory"),
}

EFFORT_FALLBACK_BY_SEVERITY: Dict[str, Tuple[float, float, float]] = {
    "low": (1.0, 2.0, 4.0),
    "medium": (2.0, 6.0, 16.0),
    "high": (4.0, 12.0, 40.0),
    "critical": (8.0, 24.0, 80.0),
    "info": (0.0, 0.0, 0.0),
}


def validate_hourly_rate(hourly_rate: Optional[float]) -> Optional[float]:
    if hourly_rate is None:
        return None
    rate = float(hourly_rate)
    if rate < MIN_HOURLY_RATE or rate > MAX_HOURLY_RATE:
        raise ValueError(f"hourly_rate must be between {int(MIN_HOURLY_RATE)} and {int(MAX_HOURLY_RATE)}.")
    return rate


def lookup_finding_effort_hours(finding: AuditFinding) -> Tuple[float, float, float, str]:
    rid = (finding.rule_id or "").upper()
    if rid in EFFORT_TABLE:
        return EFFORT_TABLE[rid]
    if rid.startswith("SECRET_") or rid == "SEC_SECRET":
        return EFFORT_TABLE["SEC-SECRET"]
    if rid.startswith(("CVE-", "GHSA-", "OSV-")):
        return EFFORT_TABLE["VULN-DEP"]
    sev = (finding.severity or "medium").lower()
    mn, lk, mx = EFFORT_FALLBACK_BY_SEVERITY.get(sev, EFFORT_FALLBACK_BY_SEVERITY["medium"])
    return mn, lk, mx, f"severity fallback ({sev})"


def compute_effort_estimate(
    findings: List[AuditFinding],
    *,
    hourly_rate: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Compute deterministic person-day effort range (`min..max`, `likely`) from finding rules.
    Monetary cost appears ONLY when a valid `hourly_rate` (1..2000) is supplied.
    """
    validated_rate = validate_hourly_rate(hourly_rate)

    total_min_h = 0.0
    total_likely_h = 0.0
    total_max_h = 0.0
    breakdown_counts: Dict[str, int] = {}

    for f in findings:
        mn, lk, mx, _ = lookup_finding_effort_hours(f)
        total_min_h += mn
        total_likely_h += lk
        total_max_h += mx
        key = (f.rule_id or "UNKNOWN").upper()
        breakdown_counts[key] = breakdown_counts.get(key, 0) + 1

    hours = {
        "min": round(total_min_h, 2),
        "likely": round(total_likely_h, 2),
        "max": round(total_max_h, 2),
    }
    person_days = {
        "min": round(total_min_h / HOURS_PER_PERSON_DAY, 2),
        "likely": round(total_likely_h / HOURS_PER_PERSON_DAY, 2),
        "max": round(total_max_h / HOURS_PER_PERSON_DAY, 2),
    }

    assumptions = [
        f"Assumes {int(HOURS_PER_PERSON_DAY)} engineering hours per person-day.",
        "Ranges reflect declared per-rule remediation assumptions (effort_model_version "
        f"{EFFORT_MODEL_VERSION}) and are independent of ML heuristic estimates.",
    ]

    result: Dict[str, Any] = {
        "effort_model_version": EFFORT_MODEL_VERSION,
        "findings_counted": len(findings),
        "hours": hours,
        "person_days": person_days,
        "rule_counts": breakdown_counts,
        "assumptions": assumptions,
    }

    if validated_rate is not None:
        result["monetary_range"] = {
            "min": round(total_min_h * validated_rate, 2),
            "likely": round(total_likely_h * validated_rate, 2),
            "max": round(total_max_h * validated_rate, 2),
            "rate_supplied": validated_rate,
            "unit": "per hour, same currency as supplied",
        }
        assumptions.append(
            f"Monetary range computed strictly as hours * {validated_rate:g} (per hour, same currency as supplied)."
        )

    return result
