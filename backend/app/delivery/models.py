"""
Canonical shared report data structure ensuring zero divergence between
dashboard, PDF, and Markdown export formats.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from backend.app.collectors.models import AuditFinding
from backend.app.scoring.roadmap_synthesis import AuditRoadmap
from backend.app.scoring.rules_engine import AuditScorecard


@dataclass
class AuditReport:
    report_id: str
    target_name: str
    target_type: str        # "public", "private", "zip"
    access_tier: str        # "free_public", "paid_private", "premium_zip"
    created_at: float
    scorecard: AuditScorecard
    findings: List[AuditFinding]
    roadmap: AuditRoadmap
    architecture_diagram_mermaid: str
    criticality_leaderboard: List[Dict[str, Any]]
    stats: Dict[str, Any]
    source_deleted: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "target_name": self.target_name,
            "target_type": self.target_type,
            "access_tier": self.access_tier,
            "created_at": self.created_at,
            "scorecard": {
                "overall_score": self.scorecard.overall_score,
                "phase": self.scorecard.phase,
                "has_critical_blocker": self.scorecard.has_critical_blocker,
                "findings_summary": self.scorecard.findings_summary,
                "dimensions": {
                    k: asdict(v) for k, v in self.scorecard.dimensions.items()
                },
            },
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
        }
