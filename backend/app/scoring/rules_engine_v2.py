"""
Deterministic Scoring Engine v2.0.0 (Gate G6).

Key invariants:
- Existing dimensions (security, tests, scalability, duplication, maintainability)
  retain identical 1.0.0 deductions (no confidence scaling) so legacy fixtures match.
- New dimensions (agent_integrity, licenses) apply confidence multipliers (1.0 / 0.75 / 0.5).
- Uses int(x + 0.5) half-up rounding everywhere (never banker's rounding).
- Never rewards missing evidence: Production-track is strictly unattainable unless
  every weighted dimension is either assessed or explicitly `not_applicable`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.app.collectors.models import AuditFinding
from backend.app.scoring.rubric import RUBRIC_2_0_0
from backend.app.scoring.rules_engine import AuditScorecard, DimensionalScore, score_audit


def round_half_up(value: float) -> int:
    """Deterministic half-up integer rounding (never Python banker's rounding)."""
    if value <= 0.0:
        return 0
    return int(value + 0.5)


@dataclass
class DimensionalScoreV2:
    dimension: str
    score: Optional[int]
    assessed: bool
    not_applicable: bool = False
    reason: Optional[str] = None
    weight_effective: float = 0.0
    findings_count: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0


@dataclass
class AuditScorecardV2:
    rubric_version: str
    overall_score: int
    phase: str  # "Prototype", "MVP", "Production-track"
    dimensions: Dict[str, DimensionalScoreV2]
    has_critical_blocker: bool
    findings_summary: Dict[str, int]
    phase_qualifiers: List[str] = field(default_factory=list)
    blockers: List[str] = field(default_factory=list)
    not_assessed: List[Dict[str, Optional[str]]] = field(default_factory=list)

    @property
    def overall(self) -> int:
        return self.overall_score

    def to_v2_dict(self) -> Dict[str, Any]:
        return {
            "rubric_version": self.rubric_version,
            "overall": self.overall_score,
            "overall_score": self.overall_score,
            "phase": self.phase,
            "phase_qualifiers": list(self.phase_qualifiers),
            "blockers": list(self.blockers),
            "has_critical_blocker": self.has_critical_blocker,
            "not_assessed": list(self.not_assessed),
            "findings_summary": dict(self.findings_summary),
            "dimensions": {
                k: {
                    "dimension": d.dimension,
                    "score": d.score,
                    "assessed": d.assessed,
                    "not_applicable": d.not_applicable,
                    "reason": d.reason,
                    "weight_effective": d.weight_effective,
                    "findings_count": d.findings_count,
                    "critical_count": d.critical_count,
                    "high_count": d.high_count,
                    "medium_count": d.medium_count,
                    "low_count": d.low_count,
                }
                for k, d in self.dimensions.items()
            },
        }


_AGT_INTEGRITY_RULES = frozenset({
    "AGT-001", "AGT-002", "AGT-003", "AGT-004", "AGT-005", "AGT-006",
    "AGT-007", "AGT-008", "AGT-009", "AGT-011", "AGT-012", "GRD-001", "GRD-002",
})


def _map_finding_dimension(f: AuditFinding) -> str:
    rid = (f.rule_id or "").upper()
    if rid == "AGT-010":
        return "security"
    if rid in _AGT_INTEGRITY_RULES:
        return "agent_integrity"
    if rid.startswith("LIC-"):
        return "licenses"
    return (f.dimension or "maintainability").lower()


def _parse_iso_dt(val: Optional[str]) -> Optional[datetime]:
    if not val:
        return None
    try:
        dt = datetime.fromisoformat(str(val).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _count_recent_90d_agt_commits(
    dim_findings: List[AuditFinding],
    process_data: Optional[Dict[str, Any]],
) -> Tuple[bool, int]:
    """
    Determine whether any high-confidence high/critical AGT finding fell in the
    most recent 90 days of the analyzed history window, and count distinct commits.
    """
    commit_dates: Dict[str, datetime] = {}
    if process_data:
        for c in process_data.get("commits") or []:
            sha = c.get("sha")
            dt = _parse_iso_dt(c.get("date"))
            if sha and dt is not None:
                commit_dates[sha] = dt

    window_end: Optional[datetime] = max(commit_dates.values()) if commit_dates else None
    for f in dim_findings:
        dt = _parse_iso_dt((f.params or {}).get("commit_date"))
        if dt is not None and (window_end is None or dt > window_end):
            window_end = dt

    cutoff = (window_end - timedelta(days=90)) if window_end else None

    recent_commits: Set[str] = set()
    has_recent = False
    for f in dim_findings:
        if (f.confidence or "").lower() != "high":
            continue
        if (f.severity or "").lower() not in ("high", "critical"):
            continue
        dt = _parse_iso_dt((f.params or {}).get("commit_date"))
        if dt is None and f.commit_sha:
            dt = commit_dates.get(f.commit_sha)
        if cutoff is not None and dt is not None:
            in_window = dt >= cutoff
        elif f.params and "in_recent_90d" in f.params:
            in_window = bool(f.params["in_recent_90d"])
        else:
            in_window = True
        if in_window:
            has_recent = True
            recent_commits.add(f.commit_sha or f.id)

    return has_recent, len(recent_commits)


def score_audit_v2(
    findings: List[AuditFinding],
    *,
    coverage: Optional[Dict[str, Any]] = None,
    process_data: Optional[Dict[str, Any]] = None,
) -> AuditScorecardV2:
    """
    Compute deterministic Rubric 2.0.0 scorecard with missing-evidence awareness,
    caps, confidence scaling on new dimensions only, and strict Production-track gating.
    """
    cov = coverage or {}
    deductions = RUBRIC_2_0_0["severity_deductions"]
    conf_mults = RUBRIC_2_0_0["confidence_multipliers"]
    new_dims = RUBRIC_2_0_0["new_dimensions"]
    base_weights: Dict[str, float] = RUBRIC_2_0_0["weights"]
    caps = RUBRIC_2_0_0["caps"]

    by_dim: Dict[str, List[AuditFinding]] = {d: [] for d in RUBRIC_2_0_0["dimensions_order"]}
    for f in findings:
        d = _map_finding_dimension(f)
        if d in by_dim:
            by_dim[d].append(f)

    # Determine availability for new dimensions (`agent_integrity`, `licenses`)
    history_cov = cov.get("history") or {}
    history_assessed = bool(history_cov.get("assessed", False))
    history_reason = history_cov.get("reason") or "history_not_assessed"

    lic_cov = cov.get("licenses") or {}
    if not lic_cov:
        lic_assessed = False
        lic_na = False
        lic_reason: Optional[str] = "license_coverage_missing"
    elif lic_cov.get("not_applicable"):
        lic_assessed = False
        lic_na = True
        lic_reason = "no_dependencies"
    else:
        prod_total = int(lic_cov.get("prod_total", 0))
        prod_pct = int(lic_cov.get("prod_resolved_pct", 100))
        if prod_total > 0 and prod_pct < 90:
            lic_assessed = False
            lic_na = False
            lic_reason = "license_coverage_partial"
        else:
            lic_assessed = True
            lic_na = False
            lic_reason = None

    dim_scores: Dict[str, DimensionalScoreV2] = {}
    phase_qualifiers: List[str] = []
    not_assessed: List[Dict[str, Optional[str]]] = []

    if history_assessed and (history_cov.get("shallow_boundary") or history_cov.get("caps_hit")):
        phase_qualifiers.append("history_partial")

    for dim in RUBRIC_2_0_0["dimensions_order"]:
        dfindings = by_dim[dim]
        counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        total_deduction = 0.0

        for f in dfindings:
            sev = (f.severity or "medium").lower()
            counts[sev] = counts.get(sev, 0) + 1
            base_pen = float(deductions.get(sev, 5))
            if dim in new_dims:
                mult = float(conf_mults.get((f.confidence or "high").lower(), 1.0))
                total_deduction += base_pen * mult
            else:
                total_deduction += base_pen

        if dim == "agent_integrity" and not history_assessed:
            dim_scores[dim] = DimensionalScoreV2(
                dimension=dim,
                score=None,
                assessed=False,
                not_applicable=False,
                reason=history_reason,
                weight_effective=0.0,
                findings_count=len(dfindings),
                critical_count=counts["critical"],
                high_count=counts["high"],
                medium_count=counts["medium"],
                low_count=counts["low"],
            )
            phase_qualifiers.append("process_integrity_not_assessed")
            not_assessed.append({"dimension": dim, "reason": history_reason})
            continue

        if dim == "licenses" and (lic_na or not lic_assessed):
            dim_scores[dim] = DimensionalScoreV2(
                dimension=dim,
                score=None,
                assessed=False,
                not_applicable=lic_na,
                reason=lic_reason,
                weight_effective=0.0,
                findings_count=len(dfindings),
                critical_count=counts["critical"],
                high_count=counts["high"],
                medium_count=counts["medium"],
                low_count=counts["low"],
            )
            if lic_na:
                phase_qualifiers.append("licenses_not_applicable")
            else:
                qual = "license_coverage_partial" if lic_reason == "license_coverage_partial" else "license_coverage_missing"
                phase_qualifiers.append(qual)
                not_assessed.append({"dimension": dim, "reason": lic_reason})
            continue

        raw = max(0.0, 100.0 - total_deduction)
        score_int = round_half_up(raw)

        # Dimension-specific caps
        if dim == "security" and counts["critical"] > 0:
            score_int = min(score_int, caps["security_critical"])
        elif dim == "licenses":
            if counts["critical"] > 0:
                score_int = min(score_int, caps["licenses_critical"])
            elif counts["high"] > 0:
                score_int = min(score_int, caps["licenses_high"])
        elif dim == "agent_integrity":
            has_recent, commit_cnt = _count_recent_90d_agt_commits(dfindings, process_data)
            if commit_cnt >= 3:
                score_int = min(score_int, caps["agent_integrity_three_commits_90d"])
            elif has_recent:
                score_int = min(score_int, caps["agent_integrity_recent_90d"])

        dim_scores[dim] = DimensionalScoreV2(
            dimension=dim,
            score=score_int,
            assessed=True,
            not_applicable=False,
            reason=None,
            weight_effective=base_weights[dim],
            findings_count=len(dfindings),
            critical_count=counts["critical"],
            high_count=counts["high"],
            medium_count=counts["medium"],
            low_count=counts["low"],
        )

    # Renormalize weights over assessed dimensions (score is not None)
    assessed_weight_sum = sum(
        base_weights[dim]
        for dim, dscore in dim_scores.items()
        if dscore.assessed and dscore.score is not None
    )
    if assessed_weight_sum > 0.0:
        weighted_total = 0.0
        for dim, dscore in dim_scores.items():
            if dscore.assessed and dscore.score is not None:
                eff_w = base_weights[dim] / assessed_weight_sum
                dscore.weight_effective = round(eff_w, 6)
                weighted_total += dscore.score * eff_w
        overall_score = round_half_up(weighted_total)
    else:
        overall_score = 0

    # Blockers list
    blockers: List[str] = []
    if dim_scores["security"].critical_count > 0:
        blockers.append("critical_security")
    if any((f.rule_id or "").upper() in ("LIC-001", "LIC-002") and (f.severity or "").lower() in ("critical", "high") for f in by_dim["licenses"]):
        blockers.append("copyleft_conflict")
    if any((f.rule_id or "").upper() == "AGT-010" for f in findings):
        blockers.append("history_secret_unrotated")
    if any(
        (f.confidence or "").lower() == "high" and (f.severity or "").lower() in ("high", "critical")
        for f in by_dim["agent_integrity"]
    ):
        blockers.append("high_confidence_test_integrity_event")

    findings_summary = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0, "total": len(findings)}
    for f in findings:
        s = (f.severity or "").lower()
        if s in findings_summary:
            findings_summary[s] += 1

    has_any_critical = findings_summary["critical"] > 0
    sec_score = dim_scores["security"].score if dim_scores["security"].score is not None else 0
    tests_score = dim_scores["tests"].score if dim_scores["tests"].score is not None else 0
    agt_dim = dim_scores["agent_integrity"]
    lic_dim = dim_scores["licenses"]

    all_assessed_or_na = all(
        (d.assessed and d.score is not None) or d.not_applicable
        for d in dim_scores.values()
    )
    agt_ok = agt_dim.assessed and agt_dim.score is not None and agt_dim.score >= 60
    lic_ok = lic_dim.not_applicable or (lic_dim.assessed and lic_dim.score is not None and lic_dim.score >= 60)

    if (
        not has_any_critical
        and all_assessed_or_na
        and overall_score >= 80
        and sec_score >= 75
        and tests_score >= 70
        and agt_ok
        and lic_ok
    ):
        phase = "Production-track"
    elif not has_any_critical and overall_score >= 55 and sec_score >= 50:
        phase = "MVP"
    else:
        phase = "Prototype"

    return AuditScorecardV2(
        rubric_version="2.0.0",
        overall_score=overall_score,
        phase=phase,
        dimensions=dim_scores,
        has_critical_blocker=has_any_critical,
        findings_summary=findings_summary,
        phase_qualifiers=list(dict.fromkeys(phase_qualifiers)),
        blockers=list(dict.fromkeys(blockers)),
        not_assessed=not_assessed,
    )


def score_audit_by_version(
    findings: List[AuditFinding],
    *,
    rubric_version: str = "2.0.0",
    coverage: Optional[Dict[str, Any]] = None,
    process_data: Optional[Dict[str, Any]] = None,
) -> AuditScorecard | AuditScorecardV2:
    """Dispatch scoring deterministically by the persisted audit's immutable rubric_version."""
    if rubric_version == "1.0.0":
        return score_audit(findings)
    return score_audit_v2(findings, coverage=coverage, process_data=process_data)
