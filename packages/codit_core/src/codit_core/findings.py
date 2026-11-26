"""Shared CoreFinding dataclass compatible with backend AuditFinding."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class CoreFinding:
    id: str
    dimension: str
    severity: str
    confidence: str
    description: str
    evidence_file: str
    evidence_line: Optional[int] = None
    rule_id: str = ""
    remediation: str = ""
    component_id: Optional[str] = None
    fingerprint: str = ""
    basis: str = "AST PROOF"
    commit_sha: Optional[str] = None
    params: Dict[str, Any] = field(default_factory=dict)
