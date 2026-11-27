"""P1/P2/P3 History Ingestion models validated strictly as JSON across process boundary."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class HistoryOptions(BaseModel):
    enabled: bool = True
    max_commits: int = Field(default=500, ge=1)
    max_days: int = Field(default=365, ge=1)


class HistoryCoverage(BaseModel):
    assessed: bool
    reason: Optional[str] = None
    commits_total_visible: int = 0
    commits_analyzed: int = 0
    shallow_boundary: bool = False
    caps_hit: List[str] = Field(default_factory=list)
    skipped_deep_commits: int = 0
    blobs_unavailable: int = 0
    notes: List[str] = Field(default_factory=list)


class CommitRecord(BaseModel):
    sha: str
    short: str
    date: str
    author_key: str
    has_agent_trailer: bool = False
    agent_id: Optional[str] = None
    attribution_basis: str = "none"
    attribution_confidence: str = "none"
    claims_tests_pass: bool = False
    skipped_deep: bool = False
    files_changed: int = 0
    prod_lines_delta: int = 0
    test_lines_delta: int = 0
    shallow_baseline: bool = False


class HistoryFindingRecord(BaseModel):
    id: str
    dimension: str
    severity: str
    confidence: str
    description: str
    evidence_file: str
    evidence_line: Optional[int] = None
    rule_id: str
    remediation: str = ""
    component_id: Optional[str] = None
    fingerprint: str
    basis: str
    commit_sha: Optional[str] = None
    params: Dict[str, Any] = Field(default_factory=dict)


class HistoryResult(BaseModel):
    coverage: HistoryCoverage
    source_commit: Optional[str] = None
    source_tree: Optional[str] = None
    commits: List[CommitRecord] = Field(default_factory=list)
    findings: List[HistoryFindingRecord] = Field(default_factory=list)
    attribution: Dict[str, Any] = Field(default_factory=dict)
    head_tooling_present: Dict[str, bool] = Field(default_factory=dict)
    head_secrets: List[Dict[str, Any]] = Field(default_factory=list)
    series: List[Dict[str, Any]] = Field(default_factory=list)
    ownership: Dict[str, Any] = Field(default_factory=dict)
