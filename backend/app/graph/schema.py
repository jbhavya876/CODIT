"""
Graph schema definitions and constants for the codebase audit platform.

Preserves all labels and relationship types from Dependency-Detective,
and extends them with :Module, :Finding, IMPORTS, and FLAGGED_BY.
"""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field

# --- Labels -------------------------------------------------------------------
LABEL_COMPONENT = "Component"
LABEL_SERVICE = "Service"
LABEL_DATABASE = "Database"
LABEL_API = "API"
LABEL_LIBRARY = "Library"
LABEL_INFRASTRUCTURE = "Infrastructure"
LABEL_TEAM = "Team"
LABEL_MODULE = "Module"       # New in M4
LABEL_FINDING = "Finding"     # New in M4/M5

ALL_COMPONENT_LABELS = {
    LABEL_SERVICE,
    LABEL_DATABASE,
    LABEL_API,
    LABEL_LIBRARY,
    LABEL_INFRASTRUCTURE,
    LABEL_MODULE,
}

# --- Relationships ------------------------------------------------------------
REL_DEPENDS_ON = "DEPENDS_ON"
REL_USES = "USES"
REL_CALLS = "CALLS"
REL_READS_FROM = "READS_FROM"
REL_WRITES_TO = "WRITES_TO"
REL_DEPLOYED_ON = "DEPLOYED_ON"
REL_OWNED_BY = "OWNED_BY"
REL_IMPORTS = "IMPORTS"       # New in M3/M4 (Module -> Module)
REL_FLAGGED_BY = "FLAGGED_BY" # New in M4/M5 (Component -> Finding)

TRAVERSAL_RELATIONSHIPS = {
    REL_DEPENDS_ON,
    REL_USES,
    REL_CALLS,
    REL_READS_FROM,
    REL_WRITES_TO,
    REL_DEPLOYED_ON,
    REL_IMPORTS,
}


# --- Pydantic Models for Graph Entities ---------------------------------------

class ModuleNode(BaseModel):
    id: str
    name: str
    path: str
    language: str
    loc: int = 0
    has_tests: bool = False
    props: dict[str, Any] = Field(default_factory=dict)


class FindingNode(BaseModel):
    id: str
    dimension: str
    severity: str
    confidence: str
    description: str
    evidence_file: str
    evidence_line: int | None = None
    rule_id: str = ""
    remediation: str = ""


class RelationshipEdge(BaseModel):
    source_id: str
    rel_type: str
    target_id: str
    props: dict[str, Any] = Field(default_factory=dict)
