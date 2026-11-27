"""Test-to-production source mapping: Tier A (naming) and Tier B (static imports)."""

from __future__ import annotations

import ast
import posixpath
import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Iterable, List, Optional, Tuple

from codit_core.fingerprint import normalize_path

_JS_IMPORT_RE = re.compile(
    r"""(?:import\s+[^'"]*?\s+from\s+['"]([^'"]+)['"]|require\(\s*['"]([^'"]+)['"]\s*\))"""
)


@dataclass(frozen=True)
class MappedTarget:
    path: str
    tier: str  # "name" | "import"


def _normalize_test_stem(path_str: str) -> str:
    name = PurePosixPath(path_str.replace("\\", "/")).name.lower()
    for suffix in (".test.tsx", ".test.ts", ".test.jsx", ".test.js", ".spec.tsx", ".spec.ts", ".spec.jsx", ".spec.js"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    stem = PurePosixPath(name).stem
    if stem.startswith("test_"):
        stem = stem[5:]
    if stem.endswith("_test"):
        stem = stem[:-5]
    return stem


def _resolve_python_imports(test_path: str, content: str, candidate_set: set[str]) -> List[str]:
    results: List[str] = []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return results

    test_dir = posixpath.dirname(test_path.replace("\\", "/"))
    for node in ast.walk(tree):
        module_candidates: List[str] = []
        if isinstance(node, ast.Import):
            for alias in node.names:
                mod_path = alias.name.replace(".", "/")
                module_candidates.extend([
                    f"{mod_path}.py",
                    f"src/{mod_path}.py",
                    f"{mod_path}/__init__.py",
                    f"src/{mod_path}/__init__.py",
                ])
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                base_dir = test_dir
                for _ in range(node.level - 1):
                    base_dir = posixpath.dirname(base_dir)
                sub = (node.module or "").replace(".", "/")
                joined = posixpath.normpath(posixpath.join(base_dir, sub)) if sub else base_dir
                module_candidates.extend([f"{joined}.py", f"{joined}/__init__.py"])
                for alias in node.names:
                    module_candidates.append(posixpath.normpath(posixpath.join(joined, f"{alias.name}.py")))
            elif node.module:
                mod_path = node.module.replace(".", "/")
                module_candidates.extend([
                    f"{mod_path}.py",
                    f"src/{mod_path}.py",
                    f"{mod_path}/__init__.py",
                    f"src/{mod_path}/__init__.py",
                ])
                for alias in node.names:
                    module_candidates.extend([
                        f"{mod_path}/{alias.name}.py",
                        f"src/{mod_path}/{alias.name}.py",
                    ])
        for cand in module_candidates:
            cand_norm = normalize_path(cand)
            if cand_norm in candidate_set and cand_norm not in results:
                results.append(cand_norm)
    return results


def _resolve_js_imports(test_path: str, content: str, candidate_set: set[str]) -> List[str]:
    results: List[str] = []
    test_dir = posixpath.dirname(test_path.replace("\\", "/"))
    exts = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")

    for m in _JS_IMPORT_RE.finditer(content or ""):
        spec = m.group(1) or m.group(2)
        if not spec or not spec.startswith("."):
            continue
        joined = normalize_path(posixpath.normpath(posixpath.join(test_dir, spec)))
        tries = [joined]
        for ext in exts:
            tries.append(f"{joined}{ext}")
            tries.append(f"{joined}/index{ext}")
        for cand in tries:
            if cand in candidate_set and cand not in results:
                results.append(cand)
    return results


def map_test_to_production(
    test_path: str,
    candidate_paths: Iterable[str],
    test_content: Optional[str] = None,
) -> List[MappedTarget]:
    """
    Map a test file to likely production files using:
    - Tier B (import): direct resolved static imports when `test_content` is supplied
    - Tier A (name): matching module stem (`test_foo.py` -> `foo.py`)
    """
    candidates = [p.replace("\\", "/") for p in candidate_paths]
    candidate_set = set(candidates)
    norm_test = test_path.replace("\\", "/")
    out: List[MappedTarget] = []
    seen: set[str] = set()

    if test_content:
        if norm_test.endswith((".py", ".pyi")):
            imp_hits = _resolve_python_imports(norm_test, test_content, candidate_set)
        else:
            imp_hits = _resolve_js_imports(norm_test, test_content, candidate_set)
        for p in imp_hits:
            if p != norm_test and p not in seen:
                seen.add(p)
                out.append(MappedTarget(path=p, tier="import"))

    test_stem = _normalize_test_stem(norm_test)
    if test_stem:
        for cand in candidates:
            if cand == norm_test or cand in seen:
                continue
            cand_stem = PurePosixPath(cand).stem.lower()
            if cand_stem == test_stem and not PurePosixPath(cand).name.lower().startswith("test_"):
                seen.add(cand)
                out.append(MappedTarget(path=cand, tier="name"))

    return out
