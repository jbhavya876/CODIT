"""
Private repository ingestion via scoped GitHub App token shallow clone.

Security constraints:
- Never execute ingested code or git hooks (`core.hooksPath=/dev/null`).
- Never pass tokens inside CLI arguments or clone URLs (uses GIT_CONFIG_COUNT env).
- Ephemeral clone state wiped immediately after reading.
"""

from __future__ import annotations

import base64
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

from backend.app.config import Config
from backend.app.history.acquire import validate_branch_name, validate_github_repo_input
from backend.app.ingestion.models import FileEntry, detect_language, is_ignored_path

log = logging.getLogger(__name__)


class GitCloneError(Exception):
    """Raised when git clone fails."""


def _build_token_env(access_token: str) -> dict[str, str]:
    env = os.environ.copy()
    env.update({
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_LFS_SKIP_SMUDGE": "1",
        "GIT_NO_LAZY_FETCH": "1",
    })
    if access_token:
        basic = base64.b64encode(f"x-access-token:{access_token}".encode("utf-8")).decode("ascii")
        env["GIT_CONFIG_COUNT"] = "1"
        env["GIT_CONFIG_KEY_0"] = "http.extraHeader"
        env["GIT_CONFIG_VALUE_0"] = f"Authorization: Basic {basic}"
    return env


def clone_private_repo(
    repo_slug: str,
    access_token: str,
    destination_dir: Path,
    branch: Optional[str] = None,
) -> List[FileEntry]:
    """
    Performs a shallow clone (--depth 1) using GitHub App access token via env.
    Reads file contents statically into memory and strips git credentials.
    """
    try:
        owner, repo = validate_github_repo_input(repo_slug)
        safe_branch = validate_branch_name(branch)
    except ValueError as exc:
        raise GitCloneError(str(exc)) from exc

    destination_dir.mkdir(parents=True, exist_ok=True)
    clone_url = f"https://github.com/{owner}/{repo}.git"

    cmd = [
        "git",
        "-c", "core.hooksPath=/dev/null",
        "-c", "protocol.file.allow=never",
        "-c", "protocol.ext.allow=never",
        "-c", "core.symlinks=false",
        "-c", "credential.helper=",
        "-c", "core.fsmonitor=false",
        "clone",
        "--depth", "1",
    ]
    if safe_branch:
        cmd.extend(["--branch", safe_branch])
    cmd.extend(["--", clone_url, str(destination_dir)])

    env = _build_token_env(access_token)

    try:
        proc = subprocess.run(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=Config.INGESTION_TIMEOUT_SECONDS,
            check=False,
        )
        if proc.returncode != 0:
            err_msg = proc.stderr.decode("utf-8", errors="replace")
            if access_token:
                err_msg = err_msg.replace(access_token, "***")
            raise GitCloneError(f"git clone failed with code {proc.returncode}: {err_msg}")
    except subprocess.TimeoutExpired as exc:
        raise GitCloneError(f"git clone timed out after {Config.INGESTION_TIMEOUT_SECONDS}s.") from exc

    # Immediately delete .git directory to clean clone metadata
    dot_git = destination_dir / ".git"
    if dot_git.exists():
        shutil.rmtree(dot_git, ignore_errors=True)

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
