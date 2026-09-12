"""
Data models for audit findings emitted by collectors.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class AuditFinding:
    id: str
    dimension: str      # "security", "tests", "duplication", "scalability", "maintainability"
    severity: str       # "critical", "high", "medium", "low", "info"
    confidence: str     # "high", "medium", "low"
    description: str
    evidence_file: str  # MANDATORY non-null reference
    evidence_line: Optional[int] = None
    rule_id: str = ""
    remediation: str = ""
    component_id: Optional[str] = None
