"""
Manifest parsing and tech-stack signal aggregation coordinator.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

from backend.app.ingestion.models import FileEntry
from backend.app.parsers.manifest.config_signals import detect_config_signals
from backend.app.parsers.manifest.npm import parse_package_json
from backend.app.parsers.manifest.python import (
    parse_pipfile,
    parse_pyproject_toml,
    parse_requirements_txt,
)
from backend.app.parsers.models import DependencyEntry, TechStackSignal


def extract_manifests_and_signals(
    files: List[FileEntry],
) -> Tuple[List[DependencyEntry], List[TechStackSignal]]:
    """
    Parses all discovered manifests across the repository and detects tech-stack signals.
    Returns:
      (dependencies_list, tech_signals_list)
    """
    dependencies: List[DependencyEntry] = []

    for entry in files:
        fname = Path(entry.path).name.lower()
        if fname == "package.json":
            dependencies.extend(parse_package_json(entry.content, file_path=entry.path))
        elif fname == "requirements.txt" or (fname.startswith("requirements") and fname.endswith(".txt")):
            dependencies.extend(parse_requirements_txt(entry.content, file_path=entry.path))
        elif fname == "pyproject.toml":
            dependencies.extend(parse_pyproject_toml(entry.content, file_path=entry.path))
        elif fname == "pipfile":
            dependencies.extend(parse_pipfile(entry.content, file_path=entry.path))

    signals = detect_config_signals(files, dependencies)
    return dependencies, signals
