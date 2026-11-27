"""Shared immutable CommitDelta / FileDelta / TestCaseMetric models (P3)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Literal, Optional, Tuple


@dataclass(frozen=True)
class AddedLine:
    lineno: int
    text: str


@dataclass(frozen=True)
class TestCaseMetric:
    name: str
    assertions: int
    skipped: Literal["none", "unconditional", "conditional"]
    focused: bool
    body_hash: str
    line: int


@dataclass(frozen=True)
class FileMetrics:
    cases: Tuple[TestCaseMetric, ...] = ()
    unsupported_framework: bool = False
    metrics_unavailable: bool = False


@dataclass(frozen=True)
class FileDelta:
    path: str
    old_path: Optional[str]
    status: Literal["A", "M", "D", "R"]
    kind: Literal["test", "ci", "gate_config", "generated", "manifest", "source", "other"]
    language: Optional[str]
    added: Tuple[AddedLine, ...] = ()
    removed_count: int = 0
    added_count: int = 0
    removed_lines: Tuple[str, ...] = ()
    before: Optional[FileMetrics] = None
    after: Optional[FileMetrics] = None
    before_text: Optional[str] = None
    after_text: Optional[str] = None


@dataclass(frozen=True)
class CommitDelta:
    sha: str
    short: str
    date: str
    files: Tuple[FileDelta, ...]
    has_agent_trailer: bool = False
    agent_id: Optional[str] = None
    claims_tests_pass: bool = False
    skipped_deep: bool = False
    files_changed: int = 0
    tree_paths: Tuple[str, ...] = ()
    shallow_baseline: bool = False
    added_secrets: Tuple[Tuple[str, str, int, str], ...] = ()  # (path, kind, line, secret_hash)


@dataclass(frozen=True)
class PolicyThresholds:
    min_removed: int = 3
    min_removed_pct: float = 0.20
    skip_high_count: int = 5
    suppression_burst: int = 5
    megacommit_lines: int = 800
    megacommit_files: int = 40
    squash_confidence_cap_files: int = 40
    moved_name_similarity: float = 0.85
