"""
Hardened remote bare-history acquisition (P1, ADR-0002).

Security invariants:
- Never accept client-supplied clone URLs, hosts, or git flags (SSRF & RCE prevention).
- Validate owner, repo, and branch strictly; always reconstruct https://github.com/{owner}/{repo}.git.
- Pass private GitHub tokens strictly through GIT_CONFIG_COUNT/http.extraHeader env vars.
- Enforce transfer byte limit via active directory size watchdog.
"""

from __future__ import annotations

import base64
import logging
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional, Tuple

from backend.app.config import Config

log = logging.getLogger(__name__)

_SLUG_PART_RE = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
_BRANCH_RE = re.compile(r"^[A-Za-z0-9._/-]{1,100}$")
_GITHUB_URL_RE = re.compile(
    r"^https://github\.com/([A-Za-z0-9_.-]{1,100})/([A-Za-z0-9_.-]{1,100}?)(?:\.git)?/?$"
)


class HistoryAcquisitionError(ValueError):
    """Raised when source validation, clone, or transfer limits fail."""


def validate_slug_part(part: str, label: str = "slug") -> str:
    cleaned = (part or "").strip()
    if not cleaned or cleaned in (".", "..") or ".." in cleaned or cleaned.startswith("-"):
        raise HistoryAcquisitionError(f"Invalid {label}: {cleaned!r}")
    if not _SLUG_PART_RE.match(cleaned):
        raise HistoryAcquisitionError(f"Invalid {label}: {cleaned!r}")
    return cleaned


def validate_github_repo_input(repo_or_url: str) -> Tuple[str, str]:
    """
    Validate public or private repository identifier against strict GitHub allowlist.
    Rejects non-https schemes (`file://`, `ext::`), embedded credentials, and flag prefixes.
    """
    raw = (repo_or_url or "").strip()
    if not raw or raw.startswith("-") or "@" in raw or any(ch.isspace() for ch in raw):
        raise HistoryAcquisitionError("Invalid repository specifier.")

    m = _GITHUB_URL_RE.match(raw)
    if m:
        owner, repo = m.group(1), m.group(2)
        return validate_slug_part(owner, "owner"), validate_slug_part(repo, "repo")

    if "/" in raw and "://" not in raw and ":" not in raw:
        parts = raw.split("/")
        if len(parts) == 2:
            owner, repo = parts[0], parts[1]
            if repo.endswith(".git"):
                repo = repo[:-4]
            return validate_slug_part(owner, "owner"), validate_slug_part(repo, "repo")

    raise HistoryAcquisitionError("Only GitHub repository slugs or https://github.com/owner/repo URLs are allowed.")


def validate_branch_name(branch: Optional[str]) -> Optional[str]:
    if branch is None:
        return None
    cleaned = branch.strip()
    if not cleaned:
        return None
    if (
        cleaned.startswith("-")
        or ".." in cleaned
        or "//" in cleaned
        or not _BRANCH_RE.match(cleaned)
    ):
        raise HistoryAcquisitionError(f"Invalid branch reference: {cleaned!r}")
    return cleaned


def check_git_version() -> Tuple[int, int]:
    """Verify installed git version and warn if < 2.32 (required for GIT_CONFIG_GLOBAL)."""
    try:
        res = subprocess.run(["git", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
        txt = res.stdout.decode("utf-8", errors="replace").strip()
        m = re.search(r"(\d+)\.(\d+)", txt)
        if m:
            ver = (int(m.group(1)), int(m.group(2)))
            if ver < (2, 32):
                log.warning("Installed git %s is older than 2.32; GIT_CONFIG_GLOBAL may be ignored.", txt)
            return ver
    except Exception as exc:
        log.warning("Could not verify git version: %s", exc)
    return (0, 0)


def _dir_size_bytes(root: Path) -> int:
    total = 0
    if not root.exists():
        return 0
    for path in root.rglob("*"):
        try:
            if path.is_file() and not path.is_symlink():
                total += path.stat().st_size
        except OSError:
            pass
    return total


def build_hardened_git_env(access_token: Optional[str] = None) -> dict[str, str]:
    env = os.environ.copy()
    env.update({
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_LFS_SKIP_SMUDGE": "1",
        "GIT_NO_LAZY_FETCH": "1",
    })
    if os.name != "nt":
        env["GIT_ASKPASS"] = "/bin/true"
    if access_token:
        basic = base64.b64encode(f"x-access-token:{access_token}".encode("utf-8")).decode("ascii")
        env["GIT_CONFIG_COUNT"] = "1"
        env["GIT_CONFIG_KEY_0"] = "http.extraHeader"
        env["GIT_CONFIG_VALUE_0"] = f"Authorization: Basic {basic}"
    return env


def build_clone_command(
    owner: str,
    repo: str,
    dest_dir: Path,
    *,
    depth: int,
    branch: Optional[str] = None,
    use_filter: bool = True,
) -> list[str]:
    url = f"https://github.com/{owner}/{repo}.git"
    cmd = [
        "git",
        "-c", "core.hooksPath=/dev/null",
        "-c", "protocol.file.allow=never",
        "-c", "protocol.ext.allow=never",
        "-c", "core.symlinks=false",
        "-c", "credential.helper=",
        "-c", "core.fsmonitor=false",
        "clone",
        "--bare",
        "--depth", str(depth),
        "--single-branch",
        "--no-tags",
    ]
    if branch:
        cmd.extend(["--branch", branch])
    if use_filter:
        cmd.append(f"--filter=blob:limit={Config.HISTORY_MAX_BLOB_KB}k")
    cmd.extend(["--", url, str(dest_dir)])
    return cmd


def acquire_bare_history(
    repo_or_url: str,
    dest_dir: Path,
    *,
    depth: int = 500,
    branch: Optional[str] = None,
    access_token: Optional[str] = None,
    timeout_seconds: Optional[int] = None,
    max_transfer_mb: Optional[int] = None,
) -> Path:
    """
    Clone bare history with hardened flags and a directory-size transfer watchdog.
    Retries once without `--filter` if the remote rejects partial-clone filtering.
    """
    check_git_version()
    owner, repo = validate_github_repo_input(repo_or_url)
    safe_branch = validate_branch_name(branch)
    effective_depth = max(1, min(depth, Config.HISTORY_MAX_COMMITS))
    wall_timeout = timeout_seconds or Config.HISTORY_WALLTIME_SECONDS
    transfer_cap_bytes = (max_transfer_mb or Config.HISTORY_TRANSFER_MAX_MB) * 1024 * 1024

    env = build_hardened_git_env(access_token)

    for use_filter in (True, False):
        if dest_dir.exists():
            shutil.rmtree(dest_dir, ignore_errors=True)
        dest_dir.mkdir(parents=True, exist_ok=True)

        cmd = build_clone_command(
            owner,
            repo,
            dest_dir,
            depth=effective_depth,
            branch=safe_branch,
            use_filter=use_filter,
        )

        proc = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        deadline = time.monotonic() + wall_timeout
        try:
            while proc.poll() is None:
                if time.monotonic() > deadline:
                    proc.kill()
                    proc.wait(timeout=5)
                    raise HistoryAcquisitionError(f"History clone timed out after {wall_timeout}s.")
                if _dir_size_bytes(dest_dir) > transfer_cap_bytes:
                    proc.kill()
                    proc.wait(timeout=5)
                    raise HistoryAcquisitionError("History clone exceeded transfer size limit.")
                time.sleep(0.5)
            stdout_b, stderr_b = proc.communicate(timeout=5)
        except Exception:
            if proc.poll() is None:
                proc.kill()
            raise

        if proc.returncode == 0:
            return dest_dir

        err_txt = stderr_b.decode("utf-8", errors="replace")
        if access_token:
            err_txt = err_txt.replace(access_token, "***")

        if use_filter and ("filter" in err_txt.lower() or "filtering" in err_txt.lower()):
            log.info("Remote rejected --filter; retrying bare clone without filter")
            continue

        raise HistoryAcquisitionError(f"git bare clone failed (exit {proc.returncode}): {err_txt.strip()}")

    raise HistoryAcquisitionError("git bare clone failed.")
