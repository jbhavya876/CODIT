"""
Deterministic Rules & Scoring Engine.

Explicit, documented rules rolling audit findings into 0-100 dimensional scores
and assigning a maturity phase label: "Prototype", "MVP", or "Production-track".

Documented Scoring Rules Reference:
-----------------------------------
1. Dimensional Base: Each dimension begins with a baseline score of 100 points.
2. Severity Penalties per finding:
   - CRITICAL: -35 points
   - HIGH:     -18 points
   - MEDIUM:   -8 points
   - LOW:      -3 points
   - INFO:     0 points
3. Hard Security Caps (Constraint 10 & Acceptance Criteria):
   - If any CRITICAL vulnerability (e.g. CVE >= 9.0) or leaked secret is present,
     the Security score is capped at a fixed maximum of 25/100, regardless of all other signals.
   - Any codebase with an unaddressed critical security finding is immediately disqualified
     from "Production-track" and "MVP", and assigned the "Prototype" phase label.
4. Dimensional Weighting for Overall Score:
   - Security:       35%
   - Tests:          25%
   - Scalability:    20%
   - Duplication:    10%
   - Maintainability:10%
5. Maturity Phase Thresholds:
   - "Production-track": Overall >= 80 AND Security >= 75 AND Tests >= 70 AND no Critical findings.
   - "MVP":             Overall >= 55 AND Security >= 50 AND no Critical findings.
   - "Prototype":       Otherwise (or if any Critical security finding is present).
6. Determinism: Zero randomness. Identical findings always yield identical scores.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List

from backend.app.collectors.models import AuditFinding

SEVERITY_DEDUCTIONS = {
    "critical": 35,
    "high": 18,
    "medium": 8,
    "low": 3,
    "info": 0,
}

DIMENSION_WEIGHTS = {
    "security": 0.35,
    "tests": 0.25,
    "scalability": 0.20,
    "duplication": 0.10,
    "maintainability": 0.10,
}


@dataclass
class DimensionalScore:
    dimension: str
    score: int
    findings_count: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int


@dataclass
class AuditScorecard:
    overall_score: int
    phase: str  # "Prototype", "MVP", "Production-track"
    dimensions: Dict[str, DimensionalScore]
    has_critical_blocker: bool
    findings_summary: Dict[str, int]


def calculate_dimensional_score(dimension: str, findings: List[AuditFinding]) -> DimensionalScore:
    """Calculates deterministic score for a single dimension."""
    dim_findings = [f for f in findings if f.dimension == dimension]

    counts = {
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
        "info": 0,
    }

    total_deduction = 0
    for f in dim_findings:
        sev = f.severity.lower()
        counts[sev] = counts.get(sev, 0) + 1
        total_deduction += SEVERITY_DEDUCTIONS.get(sev, 5)

    raw_score = max(0, 100 - total_deduction)

    # Hard Cap: Critical vulnerability in security caps score at max 25
    if dimension == "security" and counts["critical"] > 0:
        raw_score = min(raw_score, 25)

    return DimensionalScore(
        dimension=dimension,
        score=raw_score,
        findings_count=len(dim_findings),
        critical_count=counts["critical"],
        high_count=counts["high"],
        medium_count=counts["medium"],
        low_count=counts["low"],
    )


def score_audit(findings: List[AuditFinding]) -> AuditScorecard:
    """
    Rolls up all audit findings into deterministic per-dimension scores
    and assigns an overall maturity phase.
    """
    dimensions_list = ["security", "tests", "scalability", "duplication", "maintainability"]
    dim_scores: Dict[str, DimensionalScore] = {}

    total_weighted = 0.0
    for dim in dimensions_list:
        score_obj = calculate_dimensional_score(dim, findings)
        dim_scores[dim] = score_obj
        weight = DIMENSION_WEIGHTS.get(dim, 0.20)
        total_weighted += score_obj.score * weight

    overall_score = int(round(total_weighted))

    # Check for hard security blockers
    has_critical_security = dim_scores["security"].critical_count > 0

    # Determine Phase
    sec_score = dim_scores["security"].score
    test_score = dim_scores["tests"].score
    scale_score = dim_scores["scalability"].score

    if (
        not has_critical_security
        and overall_score >= 80
        and sec_score >= 75
        and test_score >= 70
        and scale_score >= 70
    ):
        phase = "Production-track"
    elif not has_critical_security and overall_score >= 55 and sec_score >= 50:
        phase = "MVP"
    else:
        phase = "Prototype"

    # Aggregated findings count by severity
    findings_summary = {"critical": 0, "high": 0, "medium": 0, "low": 0, "total": len(findings)}
    for f in findings:
        s = f.severity.lower()
        if s in findings_summary:
            findings_summary[s] += 1

    return AuditScorecard(
        overall_score=overall_score,
        phase=phase,
        dimensions=dim_scores,
        has_critical_blocker=has_critical_security,
        findings_summary=findings_summary,
    )
