"""
Canonical shared report data structure ensuring zero divergence between
dashboard, PDF, and Markdown export formats.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from backend.app.collectors.models import AuditFinding
from backend.app.scoring.roadmap_synthesis import AuditRoadmap
from backend.app.scoring.rubric import RUBRIC_VERSION
from backend.app.scoring.rules_engine import AuditScorecard
from backend.app.scoring.rules_engine_v2 import AuditScorecardV2


@dataclass
class AuditReport:
    report_id: str
    target_name: str
    target_type: str        # "public", "private", "zip"
    access_tier: str        # "free_public", "paid_private", "premium_zip"
    created_at: float
    scorecard: AuditScorecard | AuditScorecardV2
    findings: List[AuditFinding]
    roadmap: AuditRoadmap
    architecture_diagram_mermaid: str
    criticality_leaderboard: List[Dict[str, Any]]
    stats: Dict[str, Any]
    source_deleted: bool = False
    ml_insights: Dict[str, Any] = field(default_factory=dict)
    rubric_version: str = RUBRIC_VERSION
    audit_id: str = ""
    effort: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        sc_dict: Dict[str, Any] = {
            "rubric_version": self.rubric_version,
            "overall": self.scorecard.overall_score,
            "overall_score": self.scorecard.overall_score,
            "phase": self.scorecard.phase,
            "has_critical_blocker": self.scorecard.has_critical_blocker,
            "findings_summary": self.scorecard.findings_summary,
            "dimensions": {
                k: asdict(v) for k, v in self.scorecard.dimensions.items()
            },
        }
        if hasattr(self.scorecard, "phase_qualifiers"):
            sc_dict["phase_qualifiers"] = list(getattr(self.scorecard, "phase_qualifiers", []))
        if hasattr(self.scorecard, "blockers"):
            sc_dict["blockers"] = list(getattr(self.scorecard, "blockers", []))
        if hasattr(self.scorecard, "not_assessed"):
            sc_dict["not_assessed"] = list(getattr(self.scorecard, "not_assessed", []))

        payload: Dict[str, Any] = {
            "report_id": self.report_id,
            "target_name": self.target_name,
            "target_type": self.target_type,
            "access_tier": self.access_tier,
            "created_at": self.created_at,
            "rubric_version": self.rubric_version,
            "scorecard": sc_dict,
            "findings": [asdict(f) for f in self.findings],
            "roadmap": {
                "goal": self.roadmap.goal,
                "summary_narrative": self.roadmap.summary_narrative,
                "blockers_summary": self.roadmap.blockers_summary,
                "phases": [asdict(p) for p in self.roadmap.phases],
            },
            "architecture_diagram_mermaid": self.architecture_diagram_mermaid,
            "criticality_leaderboard": self.criticality_leaderboard,
            "stats": self.stats,
            "source_deleted": self.source_deleted,
            "ml_insights": self.ml_insights,
        }
        if self.effort is not None:
            payload["effort"] = self.effort
        if self.audit_id:
            payload["audit_id"] = self.audit_id
        return payload
