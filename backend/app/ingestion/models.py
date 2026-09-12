"""Ingestion data models and language detection."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class FileEntry:
    path: str
    size: int
    language: str
    content: str


LANGUAGE_EXTENSIONS = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".mts": "typescript",
    ".cts": "typescript",
    ".tsx": "typescript",
    ".json": "json",
    ".toml": "toml",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".md": "markdown",
    ".rst": "rst",
    ".txt": "text",
    ".sh": "shell",
    ".env": "env",
}

SPECIAL_FILENAMES = {
    "dockerfile": "dockerfile",
    "docker-compose.yml": "yaml",
    "docker-compose.yaml": "yaml",
    "requirements.txt": "text",
    "pipfile": "toml",
    "pyproject.toml": "toml",
    "package.json": "json",
    ".env.example": "env",
}

IGNORED_DIR_NAMES = {
    ".git",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "venv",
    "env",
    "dist",
    "build",
    ".next",
    ".nuxt",
    "coverage",
    ".mypy_cache",
}

IGNORED_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".svg",
    ".mp4", ".mp3", ".wav",
    ".zip", ".tar", ".gz", ".bz2", ".7z",
    ".exe", ".dll", ".so", ".dylib",
    ".pyc", ".pyo", ".pyd",
    ".woff", ".woff2", ".ttf", ".eot",
    ".pdf", ".doc", ".docx",
}


def is_ignored_path(path_str: str) -> bool:
    parts = Path(path_str).parts
    for part in parts:
        if part in IGNORED_DIR_NAMES:
            return True
    ext = os.path.splitext(path_str)[1].lower()
    if ext in IGNORED_EXTENSIONS:
        return True
    return False


def detect_language(path_str: str) -> str:
    filename = Path(path_str).name.lower()
    if filename in SPECIAL_FILENAMES:
        return SPECIAL_FILENAMES[filename]
    if filename.startswith("dockerfile"):
        return "dockerfile"
    if filename.startswith(".env"):
        return "env"
    ext = os.path.splitext(path_str)[1].lower()
    return LANGUAGE_EXTENSIONS.get(ext, "other")
