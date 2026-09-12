"""
Parser for Node.js / NPM package.json manifests.

Extracts regular, dev, peer, and optional dependencies with version normalization.
"""

from __future__ import annotations

import json
import logging
import re
from typing import List, Optional

from backend.app.parsers.models import DependencyEntry

log = logging.getLogger(__name__)


def normalize_npm_version(raw_version: str) -> str:
    """Strips npm version prefixes (^, ~, >=, v) to produce clean semver."""
    v = raw_version.strip()
    # Handle git or url references
    if v.startswith("git+") or v.startswith("http://") or v.startswith("https://"):
        return "git"
    if v.startswith("workspace:") or v.startswith("file:"):
        return "local"
    # Remove ^, ~, >=, <=, >, <, =, v
    cleaned = re.sub(r"^[~^><=v\s]+", "", v)
    # If range like "1.2.0 - 2.0.0" or ">=1.0 <2.0", take first version token
    m = re.search(r"(\d+\.\d+(?:\.\d+)?(?:-[0-9A-Za-z.-]+)?)", cleaned)
    if m:
        return m.group(1)
    return cleaned or "latest"


def find_line_in_content(content: str, token: str) -> Optional[int]:
    """Finds line number (1-indexed) containing the given token string."""
    lines = content.splitlines()
    for idx, line in enumerate(lines, 1):
        if token in line:
            return idx
    return None


def parse_package_json(content: str, file_path: str = "package.json") -> List[DependencyEntry]:
    """
    Parses package.json content and returns a list of DependencyEntry objects.
    Extracts dependencies, devDependencies, peerDependencies, and optionalDependencies.
    """
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        log.warning("Failed to decode JSON from %s: %s", file_path, exc)
        return []

    entries: List[DependencyEntry] = []
    dep_types = [
        ("dependencies", "dependency"),
        ("devDependencies", "devDependency"),
        ("peerDependencies", "peerDependency"),
        ("optionalDependencies", "optionalDependency"),
    ]

    for section_key, dep_type in dep_types:
        section = data.get(section_key, {})
        if not isinstance(section, dict):
            continue

        for pkg_name, raw_version in section.items():
            raw_v_str = str(raw_version)
            norm_v = normalize_npm_version(raw_v_str)
            line_no = find_line_in_content(content, f'"{pkg_name}"')

            entries.append(DependencyEntry(
                name=pkg_name,
                raw_version=raw_v_str,
                normalized_version=norm_v,
                ecosystem="npm",
                dep_type=dep_type,
                evidence_file=file_path,
                evidence_line=line_no,
            ))

    return entries
