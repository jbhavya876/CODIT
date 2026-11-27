"""Local XDG file cache for `(blob_sha, analyzer_version) -> FileMetrics`."""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from codit_core.delta import FileMetrics, TestCaseMetric
from codit_core.testmetrics import ANALYZER_VERSION, extract_test_file_metrics


def _cache_dir() -> Path:
    xdg = os.getenv("XDG_CACHE_HOME")
    base = Path(xdg) if xdg else (Path.home() / ".cache")
    return base / "codit-guard" / ANALYZER_VERSION


def cached_test_metrics(path: str, content: Optional[str], blob_sha: Optional[str] = None) -> FileMetrics:
    if content is None:
        return FileMetrics(metrics_unavailable=True)
    if not blob_sha:
        return extract_test_file_metrics(path, content)

    cdir = _cache_dir()
    cfile = cdir / f"{blob_sha}.json"
    if cfile.exists():
        try:
            data = json.loads(cfile.read_text(encoding="utf-8"))
            return FileMetrics(
                cases=tuple(TestCaseMetric(**c) for c in data.get("cases", [])),
                unsupported_framework=bool(data.get("unsupported_framework", False)),
                metrics_unavailable=bool(data.get("metrics_unavailable", False)),
            )
        except Exception:
            pass

    fm = extract_test_file_metrics(path, content)
    try:
        cdir.mkdir(parents=True, exist_ok=True)
        cfile.write_text(
            json.dumps({
                "cases": [asdict(c) for c in fm.cases],
                "unsupported_framework": fm.unsupported_framework,
                "metrics_unavailable": fm.metrics_unavailable,
            }),
            encoding="utf-8",
        )
    except OSError:
        pass
    return fm
