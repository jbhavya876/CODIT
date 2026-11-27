"""Pure path classification helpers for Python and JavaScript/TypeScript repositories."""

from __future__ import annotations

import fnmatch
import posixpath
from pathlib import PurePosixPath
from typing import Iterable, Optional

TEST_DIR_NAMES = {"tests", "test", "__tests__", "spec"}

GATE_CONFIG_FILENAMES = {
    ".coveragerc",
    "pyproject.toml",
    "setup.cfg",
    "pytest.ini",
    "tox.ini",
    "package.json",
    "jest.config.json",
    "jest.config.js",
    "jest.config.ts",
    "jest.config.mjs",
    "vitest.config.ts",
    "vitest.config.js",
    ".eslintrc",
    ".eslintrc.json",
    ".eslintrc.yml",
    ".eslintrc.yaml",
    ".eslintrc.js",
    "eslint.config.js",
    "eslint.config.mjs",
    "tsconfig.json",
}

LOCKFILE_NAMES = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "pipfile.lock",
    "uv.lock",
}

MANIFEST_NAMES = LOCKFILE_NAMES | {
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "pipfile",
    "setup.py",
    "setup.cfg",
}


def _posix_path(path_str: str) -> str:
    norm = path_str.replace("\\", "/")
    while norm.startswith("./"):
        norm = norm[2:]
    return norm


def is_test_file(path_str: str) -> bool:
    """Preserve exact existing test-path heuristic from backend/app/collectors/tests.py."""
    p_lower = _posix_path(path_str).lower()
    parts = PurePosixPath(p_lower).parts
    if any(part in TEST_DIR_NAMES for part in parts):
        return True
    name = PurePosixPath(p_lower).name
    if name.startswith("test_") or name.endswith("_test.py"):
        return True
    if ".test." in name or ".spec." in name:
        return True
    return False


def is_test_path(path_str: str, test_globs: Optional[Iterable[str]] = None) -> bool:
    """Classify test file using built-in conventions plus optional custom globs."""
    if is_test_file(path_str):
        return True
    if test_globs:
        norm = _posix_path(path_str)
        for pattern in test_globs:
            if fnmatch.fnmatch(norm, pattern):
                return True
    return False


def is_ci_path(path_str: str) -> bool:
    """Return True if path is a GitHub Actions workflow or known CI configuration file."""
    norm = _posix_path(path_str).lower()
    if norm.startswith(".github/workflows/") and (norm.endswith(".yml") or norm.endswith(".yaml")):
        return True
    ci_files = {
        ".gitlab-ci.yml",
        ".circleci/config.yml",
        ".travis.yml",
        "azure-pipelines.yml",
        "jenkinsfile",
    }
    if norm in ci_files or posixpath.basename(norm) == "jenkinsfile":
        return True
    return False


def is_gate_config_path(path_str: str) -> bool:
    """Return True if file can define coverage/lint/typecheck quality gates."""
    norm = _posix_path(path_str).lower()
    name = posixpath.basename(norm)
    return name in GATE_CONFIG_FILENAMES


def is_generated_path(path_str: str) -> bool:
    """Identify generated, vendored, lockfile, or snapshot artifacts."""
    norm = _posix_path(path_str).lower()
    parts = PurePosixPath(norm).parts
    if any(p in {"vendor", "third_party", "node_modules", "dist", "build", "__snapshots__"} for p in parts):
        return True
    name = posixpath.basename(norm)
    if name in LOCKFILE_NAMES:
        return True
    if name.endswith((".min.js", ".min.css", ".snap", ".map")):
        return True
    return False


def language_of(path_str: str) -> Optional[str]:
    """Return normalized analysis language ('python', 'javascript', 'typescript') or None."""
    norm = _posix_path(path_str).lower()
    if norm.endswith((".py", ".pyi")):
        return "python"
    if norm.endswith((".js", ".mjs", ".cjs", ".jsx")):
        return "javascript"
    if norm.endswith((".ts", ".mts", ".cts", ".tsx")):
        return "typescript"
    return None
