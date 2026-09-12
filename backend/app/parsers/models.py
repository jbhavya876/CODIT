"""Data models for dependency manifest entries and tech-stack signals."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DependencyEntry:
    name: str
    raw_version: str
    normalized_version: str
    ecosystem: str  # "npm" or "PyPI"
    dep_type: str   # "dependency", "devDependency", "peerDependency", "optionalDependency"
    evidence_file: str
    evidence_line: Optional[int] = None


@dataclass
class TechStackSignal:
    category: str   # "framework", "database", "infra", "cache", "message_queue", "ci"
    name: str
    evidence_file: str
    confidence: str # "high", "medium", "low"
    detail: str = ""
