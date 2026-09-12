"""
Canonical shared in-memory state for active codebase and audit reports.
Prevents dual-module import state splitting across uvicorn reloaders.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pathlib import Path

_ACTIVE_CODEBASE: Dict[str, Any] = {
    "target": "demo",
    "type": "demo",
    "entries": [],
    "languages": {},
    "file_count": 0,
    "total_size_kb": 0,
    "temp_dir": None,
}

_ACTIVE_REPORT: Optional[Any] = None


def get_active_codebase() -> Dict[str, Any]:
    global _ACTIVE_CODEBASE
    return _ACTIVE_CODEBASE


def set_active_codebase(
    target: str,
    target_type: str,
    entries: List[Any],
    temp_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    global _ACTIVE_CODEBASE

    lang_counts: Dict[str, int] = {}
    total_bytes = 0
    for e in entries:
        lang = getattr(e, "language", "other")
        lang_counts[lang] = lang_counts.get(lang, 0) + 1
        total_bytes += getattr(e, "size", len(getattr(e, "content", "") or ""))

    _ACTIVE_CODEBASE = {
        "target": target,
        "type": target_type,
        "entries": entries,
        "languages": lang_counts,
        "file_count": len(entries),
        "total_size_kb": round(total_bytes / 1024, 1),
        "temp_dir": str(temp_dir) if temp_dir else None,
    }
    return _ACTIVE_CODEBASE


def get_active_report() -> Optional[Any]:
    global _ACTIVE_REPORT
    return _ACTIVE_REPORT


def set_active_report(report: Any) -> None:
    global _ACTIVE_REPORT
    _ACTIVE_REPORT = report
