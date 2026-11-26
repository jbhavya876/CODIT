"""P1 History Ingestion models validated strictly as JSON across process boundary."""

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


class AddedLineModel(BaseModel):
    lineno: int
    text: str


class FileDeltaModel(BaseModel):
    path: str
    old_path: Optional[str] = None
    status: Literal["A", "M", "D", "R"]
    kind: Literal["test", "ci", "gate_config", "generated", "manifest", "source", "other"]
    language: Optional[str] = None
    added: List[AddedLineModel] = Field(default_factory=list)
    removed_count: int = 0
    added_count: int = 0
    before_metrics: Optional[Dict[str, Any]] = None
    after_metrics: Optional[Dict[str, Any]] = None
    before_text: Optional[str] = None
    after_text: Optional[str] = None
    before_blob_sha: Optional[str] = None
    after_blob_sha: Optional[str] = None


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
    files: List[FileDeltaModel] = Field(default_factory=list)


class HistoryResult(BaseModel):
    coverage: HistoryCoverage
    source_commit: Optional[str] = None
    source_tree: Optional[str] = None
    commits: List[CommitRecord] = Field(default_factory=list)
    head_tooling_present: Dict[str, bool] = Field(default_factory=dict)
    head_secrets: List[Dict[str, Any]] = Field(default_factory=list)
    head_focus_markers: List[Dict[str, Any]] = Field(default_factory=list)
    series: List[Dict[str, Any]] = Field(default_factory=list)
    ownership: Dict[str, Any] = Field(default_factory=dict)
