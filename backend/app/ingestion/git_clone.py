"""
Private repository ingestion via scoped GitHub App token shallow clone.

Security constraints:
- Constraint 1: Never execute ingested code (no npm install, no pip install, no setup.py).
- Constraint 4: Runs inside an isolated, ephemeral sandbox directory.
- Constraint 5: Ephemeral clone state wiped immediately after reading.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

from backend.app.config import Config
from backend.app.ingestion.models import FileEntry, detect_language, is_ignored_path

log = logging.getLogger(__name__)


class GitCloneError(Exception):
    """Raised when git clone fails."""


def clone_private_repo(
    repo_slug: str,
    access_token: str,
    destination_dir: Path,
    branch: Optional[str] = None,
) -> List[FileEntry]:
    """
    Performs a shallow clone (--depth 1) using GitHub App access token.
    Reads file contents statically into memory and strips git credentials.
    """
    destination_dir.mkdir(parents=True, exist_ok=True)
    target_repo = repo_slug.strip().lstrip("/").replace("https://github.com/", "")
    clone_url = f"https://x-access-token:{access_token}@github.com/{target_repo}.git"

    cmd = [
        "git", "clone",
        "--depth", "1",
        "--config", "core.hooksPath=/dev/null",  # Prevent any git hooks execution
    ]
    if branch:
        cmd.extend(["--branch", branch])
    cmd.extend([clone_url, str(destination_dir)])

    # Run git clone with timeout
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=Config.INGESTION_TIMEOUT_SECONDS,
            check=False,
        )
        if proc.returncode != 0:
            # Mask access token in error message
            err_msg = proc.stderr.decode("utf-8", errors="replace").replace(access_token, "***")
            raise GitCloneError(f"git clone failed with code {proc.returncode}: {err_msg}")
    except subprocess.TimeoutExpired:
        raise GitCloneError(f"git clone timed out after {Config.INGESTION_TIMEOUT_SECONDS}s.")

    # Immediately delete .git directory to destroy credentials and hooks
    dot_git = destination_dir / ".git"
    if dot_git.exists():
        shutil.rmtree(dot_git, ignore_errors=True)

    # Read extracted files into normalized FileEntry manifest
    entries: List[FileEntry] = []
    max_file_size = Config.MAX_INDIVIDUAL_FILE_MB * 1024 * 1024
    resolved_dest = destination_dir.resolve()

    for root, dirs, files in os.walk(resolved_dest):
        dirs[:] = [d for d in dirs if not is_ignored_path(d)]
        for file_name in files:
            full_path = Path(root) / file_name
            rel_path = full_path.relative_to(resolved_dest).as_posix()

            if is_ignored_path(rel_path):
                continue

            size = full_path.stat().st_size
            if size > max_file_size:
                continue

            lang = detect_language(rel_path)
            content = ""
            try:
                with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except Exception as exc:
                log.debug("Could not read %s: %s", rel_path, exc)

            entries.append(FileEntry(
                path=rel_path,
                size=size,
                language=lang,
                content=content,
            ))

    return entries
