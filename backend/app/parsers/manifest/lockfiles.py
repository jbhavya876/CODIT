"""
Lockfile parsers for npm (package-lock, yarn.lock v1, pnpm-lock) and Python (poetry.lock, Pipfile.lock, requirements.txt).

Unpinned requirements produce explicit `UnpinnedEntry` (`not_assessed(reason="unpinned")`)
records — versions are never guessed (P5 item 1).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import yaml

try:
    import tomllib
except ImportError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

from backend.app.ingestion.models import FileEntry

_PINNED_REQ_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*(?:\[[^\]]+\])?)\s*==\s*([A-Za-z0-9._+-]+)")
_ANY_REQ_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)")


@dataclass(frozen=True)
class LockDependency:
    name: str
    version: str
    ecosystem: str  # "npm" | "PyPI"
    scope: str      # "prod" | "dev"
    direct: bool
    source_file: str
    line: int
    lockfile_license: Optional[str] = None


@dataclass(frozen=True)
class UnpinnedDependency:
    name: str
    ecosystem: str
    source_file: str
    line: int
    reason: str = "unpinned"


def _extract_direct_manifest_sets(files: List[FileEntry]) -> Tuple[Set[str], Set[str], Set[str]]:
    """Return (npm_prod, npm_dev, pypi_direct)."""
    npm_prod: Set[str] = set()
    npm_dev: Set[str] = set()
    pypi_direct: Set[str] = set()

    for f in files:
        fname = Path(f.path).name.lower()
        if fname == "package.json":
            try:
                doc = json.loads(f.content)
                npm_prod.update((doc.get("dependencies") or {}).keys())
                npm_dev.update((doc.get("devDependencies") or {}).keys())
            except Exception:
                pass
        elif fname == "pyproject.toml":
            try:
                doc = tomllib.loads(f.content)
                for req in (doc.get("project") or {}).get("dependencies") or []:
                    m = _ANY_REQ_RE.match(str(req).strip())
                    if m:
                        pypi_direct.add(m.group(1).lower())
                poetry_deps = ((doc.get("tool") or {}).get("poetry") or {}).get("dependencies") or {}
                for k in poetry_deps:
                    if k.lower() != "python":
                        pypi_direct.add(k.lower())
            except Exception:
                pass
        elif fname == "requirements.txt":
            for raw in (f.content or "").splitlines():
                line = raw.split("#", 1)[0].strip()
                if not line or line.startswith(("-", "--")):
                    continue
                m = _ANY_REQ_RE.match(line)
                if m:
                    pypi_direct.add(m.group(1).lower())
    return npm_prod, npm_dev, pypi_direct


def _find_line(text: str, needle: str, start_hint: int = 1) -> int:
    lines = text.splitlines()
    for idx, line in enumerate(lines, 1):
        if idx >= start_hint and needle in line:
            return idx
    return 1


def _parse_package_lock(entry: FileEntry, npm_prod: Set[str], npm_dev: Set[str]) -> List[LockDependency]:
    out: List[LockDependency] = []
    try:
        doc = json.loads(entry.content)
    except Exception:
        return out

    packages = doc.get("packages")
    if isinstance(packages, dict) and packages:
        for pkg_key, info in packages.items():
            if not pkg_key or not isinstance(info, dict):
                continue
            # Handle nested paths like node_modules/a/node_modules/b or node_modules/@scope/pkg
            if "node_modules/" in pkg_key:
                name = pkg_key.rsplit("node_modules/", 1)[-1]
            else:
                name = pkg_key
            ver = str(info.get("version") or "").strip()
            if not name or not ver:
                continue
            is_dev = bool(info.get("dev") or info.get("devOptional"))
            scope = "dev" if is_dev else "prod"
            direct = (name in npm_prod) or (name in npm_dev)
            lic = info.get("license") if isinstance(info.get("license"), str) else None
            ln = _find_line(entry.content, f'"{pkg_key}"')
            out.append(LockDependency(name=name, version=ver, ecosystem="npm", scope=scope, direct=direct, source_file=entry.path, line=ln, lockfile_license=lic))
        return out

    # Fallback v1 `dependencies` tree
    def walk_v1(deps_map: dict) -> None:
        for name, info in deps_map.items():
            if not isinstance(info, dict):
                continue
            ver = str(info.get("version") or "").strip()
            if ver:
                is_dev = bool(info.get("dev"))
                direct = (name in npm_prod) or (name in npm_dev)
                ln = _find_line(entry.content, f'"{name}"')
                out.append(LockDependency(name=name, version=ver, ecosystem="npm", scope="dev" if is_dev else "prod", direct=direct, source_file=entry.path, line=ln))
            nested = info.get("dependencies")
            if isinstance(nested, dict):
                walk_v1(nested)

    if isinstance(doc.get("dependencies"), dict):
        walk_v1(doc["dependencies"])
    return out


def _parse_yarn_lock_v1(entry: FileEntry, npm_prod: Set[str], npm_dev: Set[str]) -> List[LockDependency]:
    out: List[LockDependency] = []
    seen: Set[Tuple[str, str]] = set()
    cur_names: List[str] = []
    cur_header_line = 1

    for idx, raw_line in enumerate(entry.content.splitlines(), 1):
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if not line[0].isspace() and line.endswith(":"):
            cur_names = []
            cur_header_line = idx
            header = line[:-1]
            for spec in header.split(","):
                s = spec.strip().strip('"').strip("'")
                if not s:
                    continue
                if s.startswith("@"):
                    at_idx = s.find("@", 1)
                    pkg_name = s[:at_idx] if at_idx != -1 else s
                else:
                    at_idx = s.find("@")
                    pkg_name = s[:at_idx] if at_idx != -1 else s
                if pkg_name:
                    cur_names.append(pkg_name)
        elif cur_names and line.strip().startswith("version "):
            m = re.match(r'^version\s+["\']?([^"\']+)["\']?', line.strip())
            if m:
                ver = m.group(1).strip()
                for pkg in dict.fromkeys(cur_names):
                    if (pkg, ver) in seen:
                        continue
                    seen.add((pkg, ver))
                    is_dev = pkg in npm_dev and pkg not in npm_prod
                    out.append(LockDependency(name=pkg, version=ver, ecosystem="npm", scope="dev" if is_dev else "prod", direct=(pkg in npm_prod or pkg in npm_dev), source_file=entry.path, line=cur_header_line))
    return out


def _parse_pnpm_lock(entry: FileEntry, npm_prod: Set[str], npm_dev: Set[str]) -> List[LockDependency]:
    out: List[LockDependency] = []
    try:
        doc = yaml.safe_load(entry.content) or {}
    except Exception:
        return out
    if not isinstance(doc, dict):
        return out

    pnpm_prod = set(npm_prod)
    pnpm_dev = set(npm_dev)
    for imp in (doc.get("importers") or {}).values():
        if isinstance(imp, dict):
            pnpm_prod.update((imp.get("dependencies") or {}).keys())
            pnpm_dev.update((imp.get("devDependencies") or {}).keys())
    if isinstance(doc.get("dependencies"), dict):
        pnpm_prod.update(doc["dependencies"].keys())
    if isinstance(doc.get("devDependencies"), dict):
        pnpm_dev.update(doc["devDependencies"].keys())

    packages = doc.get("packages") or doc.get("snapshots") or {}
    if not isinstance(packages, dict):
        return out

    seen: Set[Tuple[str, str]] = set()
    for key, info in packages.items():
        raw_k = str(key).lstrip("/")
        # Strip peer suffix like `(react@18.2.0)` or `_react@18.2.0`
        raw_k = raw_k.split("(", 1)[0].split("_", 1)[0]
        if raw_k.startswith("@"):
            at_idx = raw_k.find("@", 1)
            if at_idx != -1:
                name, ver = raw_k[:at_idx], raw_k[at_idx + 1 :]
            else:
                parts = raw_k.split("/")
                if len(parts) >= 3:
                    name, ver = f"{parts[0]}/{parts[1]}", parts[2]
                else:
                    continue
        else:
            at_idx = raw_k.find("@")
            if at_idx != -1:
                name, ver = raw_k[:at_idx], raw_k[at_idx + 1 :]
            else:
                parts = raw_k.split("/")
                if len(parts) >= 2:
                    name, ver = parts[0], parts[1]
                else:
                    continue
        if not name or not ver or (name, ver) in seen:
            continue
        seen.add((name, ver))
        is_dev = bool(isinstance(info, dict) and info.get("dev") is True) or (name in pnpm_dev and name not in pnpm_prod)
        lic = info.get("license") if (isinstance(info, dict) and isinstance(info.get("license"), str)) else None
        ln = _find_line(entry.content, name)
        out.append(LockDependency(name=name, version=ver, ecosystem="npm", scope="dev" if is_dev else "prod", direct=(name in pnpm_prod or name in pnpm_dev), source_file=entry.path, line=ln, lockfile_license=lic))
    return out


def _parse_poetry_lock(entry: FileEntry, pypi_direct: Set[str]) -> List[LockDependency]:
    out: List[LockDependency] = []
    try:
        doc = tomllib.loads(entry.content)
    except Exception:
        return out
    for pkg in doc.get("package") or []:
        if not isinstance(pkg, dict):
            continue
        name = str(pkg.get("name") or "").strip()
        ver = str(pkg.get("version") or "").strip()
        if not name or not ver:
            continue
        cat = str(pkg.get("category") or "main").lower()
        groups = [str(g).lower() for g in (pkg.get("groups") or [])]
        is_dev = cat == "dev" or (bool(groups) and all(g in ("dev", "test", "docs", "lint") for g in groups))
        ln = _find_line(entry.content, f'name = "{name}"')
        out.append(LockDependency(name=name, version=ver, ecosystem="PyPI", scope="dev" if is_dev else "prod", direct=name.lower() in pypi_direct, source_file=entry.path, line=ln))
    return out


def _parse_pipfile_lock(entry: FileEntry, pypi_direct: Set[str]) -> Tuple[List[LockDependency], List[UnpinnedDependency]]:
    out: List[LockDependency] = []
    unpinned: List[UnpinnedDependency] = []
    try:
        doc = json.loads(entry.content)
    except Exception:
        return out, unpinned

    for section, scope in (("default", "prod"), ("develop", "dev")):
        sec = doc.get(section) or {}
        if not isinstance(sec, dict):
            continue
        for name, info in sec.items():
            ver_raw = str(info.get("version") or "").strip() if isinstance(info, dict) else ""
            ln = _find_line(entry.content, f'"{name}"')
            if ver_raw.startswith("=="):
                ver = ver_raw[2:].strip()
                if ver:
                    out.append(LockDependency(name=name, version=ver, ecosystem="PyPI", scope=scope, direct=True, source_file=entry.path, line=ln))
                else:
                    unpinned.append(UnpinnedDependency(name=name, ecosystem="PyPI", source_file=entry.path, line=ln))
            else:
                unpinned.append(UnpinnedDependency(name=name, ecosystem="PyPI", source_file=entry.path, line=ln))
    return out, unpinned


def _parse_pinned_requirements(entry: FileEntry) -> Tuple[List[LockDependency], List[UnpinnedDependency]]:
    out: List[LockDependency] = []
    unpinned: List[UnpinnedDependency] = []
    is_dev_file = "dev" in Path(entry.path).name.lower()
    scope = "dev" if is_dev_file else "prod"

    for idx, raw in enumerate(entry.content.splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith(("-", "--", "git+", "http://", "https://")):
            continue
        # Handle environment markers cleanly (`pkg==1.2.3 ; python_version >= "3.10"`)
        line_core = line.split(";", 1)[0].strip()
        m_pin = _PINNED_REQ_RE.match(line_core)
        if m_pin:
            name = m_pin.group(1).split("[", 1)[0].strip()
            ver = m_pin.group(2).strip()
            out.append(LockDependency(name=name, version=ver, ecosystem="PyPI", scope=scope, direct=True, source_file=entry.path, line=idx))
        else:
            m_any = _ANY_REQ_RE.match(line_core)
            if m_any:
                unpinned.append(UnpinnedDependency(name=m_any.group(1), ecosystem="PyPI", source_file=entry.path, line=idx))
    return out, unpinned


def parse_all_lockfiles(files: List[FileEntry]) -> Tuple[List[LockDependency], List[UnpinnedDependency]]:
    """
    Extract deterministic pinned dependencies from lockfiles (and requirements.txt).
    Unpinned entries are returned separately as UnpinnedDependency (`not_assessed(reason="unpinned")`).
    """
    npm_prod, npm_dev, pypi_direct = _extract_direct_manifest_sets(files)
    locked: List[LockDependency] = []
    unpinned: List[UnpinnedDependency] = []

    for f in files:
        fname = Path(f.path).name.lower()
        if fname == "package-lock.json":
            locked.extend(_parse_package_lock(f, npm_prod, npm_dev))
        elif fname == "yarn.lock":
            locked.extend(_parse_yarn_lock_v1(f, npm_prod, npm_dev))
        elif fname == "pnpm-lock.yaml":
            locked.extend(_parse_pnpm_lock(f, npm_prod, npm_dev))
        elif fname == "poetry.lock":
            locked.extend(_parse_poetry_lock(f, pypi_direct))
        elif fname == "pipfile.lock":
            l_deps, u_deps = _parse_pipfile_lock(f, pypi_direct)
            locked.extend(l_deps)
            unpinned.extend(u_deps)
        elif fname == "requirements.txt" or (fname.startswith("requirements") and fname.endswith(".txt")):
            l_deps, u_deps = _parse_pinned_requirements(f)
            locked.extend(l_deps)
            unpinned.extend(u_deps)

    # Deduplicate by (ecosystem, name.lower(), version) while preserving prod over dev scope
    dedup: Dict[Tuple[str, str, str], LockDependency] = {}
    for d in locked:
        key = (d.ecosystem, d.name.lower(), d.version)
        existing = dedup.get(key)
        if existing is None:
            dedup[key] = d
        elif existing.scope == "dev" and d.scope == "prod":
            dedup[key] = d

    return list(dedup.values()), unpinned
