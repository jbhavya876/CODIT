"""
Parsers for Python ecosystem manifests: requirements.txt, pyproject.toml, and Pipfile.

Supports PEP 621 dependencies, Poetry format tables, and standard pip requirements.
"""

from __future__ import annotations

import logging
import re
from typing import List, Optional

try:
    import tomllib  # Python 3.11+ standard library
except ImportError:
    try:
        import tomli as tomllib  # Fallback
    except ImportError:
        tomllib = None  # Handled with custom fallback parser

from backend.app.parsers.models import DependencyEntry

log = logging.getLogger(__name__)


def normalize_python_version(raw_spec: str) -> str:
    """Extracts a clean baseline version from specifiers (==, >=, ~=, etc.)."""
    spec = raw_spec.strip()
    if not spec or spec == "*":
        return "latest"
    # Match version after operators ==, >=, ~=, <=, >, <, =
    m = re.search(r"[=><~^!]+\s*([0-9A-Za-z_.\-+]+)", spec)
    if m:
        return m.group(1).rstrip(",")
    # Match standalone semver
    m = re.search(r"(\d+\.\d+(?:\.\d+)?(?:[a-zA-Z0-9.-]*)?)", spec)
    if m:
        return m.group(1)
    return spec


def parse_requirements_txt(content: str, file_path: str = "requirements.txt") -> List[DependencyEntry]:
    """
    Parses requirements.txt content line by line with line number attribution.
    """
    entries: List[DependencyEntry] = []
    lines = content.splitlines()

    for idx, line in enumerate(lines, 1):
        cleaned = line.strip()
        # Skip empty lines, comments, and pip flags
        if not cleaned or cleaned.startswith("#") or cleaned.startswith("-"):
            continue

        # Strip inline comments
        if " #" in cleaned:
            cleaned = cleaned.split(" #", 1)[0].strip()

        # Match package name and specifier: e.g. "requests>=2.28.0", "flask[async]==2.3.0", "pytest"
        m = re.match(r"^([A-Za-z0-9_.\-]+)(?:\[[^\]]+\])?\s*(.*)$", cleaned)
        if not m:
            continue

        pkg_name = m.group(1)
        raw_version = m.group(2).strip() or "*"
        norm_version = normalize_python_version(raw_version)

        entries.append(DependencyEntry(
            name=pkg_name,
            raw_version=raw_version,
            normalized_version=norm_version,
            ecosystem="PyPI",
            dep_type="dependency",
            evidence_file=file_path,
            evidence_line=idx,
        ))

    return entries


def parse_pyproject_toml(content: str, file_path: str = "pyproject.toml") -> List[DependencyEntry]:
    """
    Parses pyproject.toml supporting both PEP 621 ([project.dependencies])
    and Poetry format ([tool.poetry.dependencies] and dependency groups).
    """
    entries: List[DependencyEntry] = []
    lines = content.splitlines()

    def get_line_no(token: str) -> Optional[int]:
        for i, l in enumerate(lines, 1):
            if token in l:
                return i
        return None

    data = None
    if tomllib is not None:
        try:
            data = tomllib.loads(content)
        except Exception as exc:
            log.warning("tomllib parse error for %s: %s", file_path, exc)

    if data is not None:
        # 1. PEP 621 project.dependencies: list of requirement strings
        project = data.get("project", {})
        deps = project.get("dependencies", [])
        if isinstance(deps, list):
            for dep_str in deps:
                m = re.match(r"^([A-Za-z0-9_.\-]+)(?:\[[^\]]+\])?\s*(.*)$", dep_str.strip())
                if m:
                    pkg_name = m.group(1)
                    raw_v = m.group(2).strip() or "*"
                    entries.append(DependencyEntry(
                        name=pkg_name,
                        raw_version=raw_v,
                        normalized_version=normalize_python_version(raw_v),
                        ecosystem="PyPI",
                        dep_type="dependency",
                        evidence_file=file_path,
                        evidence_line=get_line_no(pkg_name),
                    ))

        # PEP 621 optional dependencies
        opt_deps = project.get("optional-dependencies", {})
        if isinstance(opt_deps, dict):
            for group, group_deps in opt_deps.items():
                if isinstance(group_deps, list):
                    for dep_str in group_deps:
                        m = re.match(r"^([A-Za-z0-9_.\-]+)(?:\[[^\]]+\])?\s*(.*)$", dep_str.strip())
                        if m:
                            pkg_name = m.group(1)
                            raw_v = m.group(2).strip() or "*"
                            entries.append(DependencyEntry(
                                name=pkg_name,
                                raw_version=raw_v,
                                normalized_version=normalize_python_version(raw_v),
                                ecosystem="PyPI",
                                dep_type="optionalDependency",
                                evidence_file=file_path,
                                evidence_line=get_line_no(pkg_name),
                            ))

        # 2. Poetry format: [tool.poetry.dependencies]
        tool = data.get("tool", {})
        poetry = tool.get("poetry", {})
        poetry_deps = poetry.get("dependencies", {})
        if isinstance(poetry_deps, dict):
            for pkg_name, val in poetry_deps.items():
                if pkg_name.lower() == "python":
                    continue  # Ignore Python runtime declaration
                if isinstance(val, str):
                    raw_v = val
                elif isinstance(val, dict):
                    raw_v = str(val.get("version", "*"))
                else:
                    raw_v = "*"
                entries.append(DependencyEntry(
                    name=pkg_name,
                    raw_version=raw_v,
                    normalized_version=normalize_python_version(raw_v),
                    ecosystem="PyPI",
                    dep_type="dependency",
                    evidence_file=file_path,
                    evidence_line=get_line_no(pkg_name),
                ))

        # Poetry dev/group dependencies
        dev_deps = poetry.get("dev-dependencies", {})
        if isinstance(dev_deps, dict):
            for pkg_name, val in dev_deps.items():
                raw_v = val if isinstance(val, str) else str(val.get("version", "*") if isinstance(val, dict) else "*")
                entries.append(DependencyEntry(
                    name=pkg_name,
                    raw_version=raw_v,
                    normalized_version=normalize_python_version(raw_v),
                    ecosystem="PyPI",
                    dep_type="devDependency",
                    evidence_file=file_path,
                    evidence_line=get_line_no(pkg_name),
                ))

        group_deps = poetry.get("group", {})
        if isinstance(group_deps, dict):
            for gname, gval in group_deps.items():
                if isinstance(gval, dict) and "dependencies" in gval:
                    for pkg_name, val in gval["dependencies"].items():
                        raw_v = val if isinstance(val, str) else str(val.get("version", "*") if isinstance(val, dict) else "*")
                        entries.append(DependencyEntry(
                            name=pkg_name,
                            raw_version=raw_v,
                            normalized_version=normalize_python_version(raw_v),
                            ecosystem="PyPI",
                            dep_type=f"group-{gname}",
                            evidence_file=file_path,
                            evidence_line=get_line_no(pkg_name),
                        ))

    return entries


def parse_pipfile(content: str, file_path: str = "Pipfile") -> List[DependencyEntry]:
    """Parses Pipfile sections [packages] and [dev-packages]."""
    entries: List[DependencyEntry] = []
    if tomllib is None:
        return entries
    try:
        data = tomllib.loads(content)
    except Exception:
        return entries

    lines = content.splitlines()

    def get_line_no(token: str) -> Optional[int]:
        for i, l in enumerate(lines, 1):
            if token in l:
                return i
        return None

    for section_name, dep_type in [("packages", "dependency"), ("dev-packages", "devDependency")]:
        pkgs = data.get(section_name, {})
        if isinstance(pkgs, dict):
            for pkg_name, val in pkgs.items():
                raw_v = val if isinstance(val, str) else str(val.get("version", "*") if isinstance(val, dict) else "*")
                entries.append(DependencyEntry(
                    name=pkg_name,
                    raw_version=raw_v,
                    normalized_version=normalize_python_version(raw_v),
                    ecosystem="PyPI",
                    dep_type=dep_type,
                    evidence_file=file_path,
                    evidence_line=get_line_no(pkg_name),
                ))
    return entries
