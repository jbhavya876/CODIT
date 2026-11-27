"""
Public repository ingestion via GitHub REST API tree fetch.

Fetches file trees recursively without performing full git clones.
Enforces size and file count caps, and implements rate-limit backoff and caching.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
import logging
import os
import re
import time
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import httpx

from backend.app.config import Config
from backend.app.ingestion.models import FileEntry, detect_language, is_ignored_path

log = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).resolve().parents[3] / ".cache" / "github_trees"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


class GitHubIngestionError(Exception):
    """Raised when GitHub API ingestion fails."""


def parse_github_url(url_or_slug: str) -> Tuple[str, str]:
    """Extract (owner, repo) from a GitHub URL or 'owner/repo' string."""
    cleaned = url_or_slug.strip().rstrip("/")
    # Handle https://github.com/owner/repo or git@github.com:owner/repo
    m = re.search(r"github\.com[/:]([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?$", cleaned)
    if m:
        return m.group(1), m.group(2)
    # Handle owner/repo format
    parts = cleaned.split("/")
    if len(parts) == 2 and parts[0] and parts[1]:
        return parts[0], parts[1].replace(".git", "")
    raise GitHubIngestionError(f"Invalid GitHub repository specifier: '{url_or_slug}'. Expected 'owner/repo' or GitHub URL.")


def _get_cache_path(owner: str, repo: str, tree_sha: str) -> Path:
    key = f"{owner}_{repo}_{tree_sha}"
    hashed = hashlib.sha256(key.encode()).hexdigest()[:16]
    return CACHE_DIR / f"{owner}_{repo}_{hashed}.json"


TEXT_LANGUAGES = frozenset(
    {"python", "javascript", "typescript", "json", "toml", "yaml", "dockerfile", "env", "text", "markdown"}
)


def _fetch_via_codeload_zipball(
    client: httpx.Client,
    owner: str,
    repo: str,
    branches: List[str],
    limit_files: int,
    max_file_size: int,
) -> Optional[List[FileEntry]]:
    """Bounded in-memory zipball fallback via codeload.github.com when REST tree API is rate-limited."""
    max_zip_bytes = Config.MAX_REPO_SIZE_MB * 1024 * 1024
    seen_branches: List[str] = []
    for b in branches:
        if b and b not in seen_branches:
            seen_branches.append(b)
    if "HEAD" not in seen_branches:
        seen_branches.append("HEAD")

    for br in seen_branches:
        zip_url = f"https://codeload.github.com/{owner}/{repo}/zip/{br}"
        try:
            with client.stream("GET", zip_url, follow_redirects=False) as resp:
                if resp.status_code != 200:
                    continue
                buf = io.BytesIO()
                total = 0
                for chunk in resp.iter_bytes(chunk_size=65536):
                    total += len(chunk)
                    if total > max_zip_bytes:
                        raise GitHubIngestionError(
                            f"Repository archive exceeds {Config.MAX_REPO_SIZE_MB} MB limit."
                        )
                    buf.write(chunk)
        except GitHubIngestionError:
            raise
        except httpx.HTTPError as exc:
            log.debug("Codeload fallback failed for %s/%s@%s: %s", owner, repo, br, exc)
            continue

        buf.seek(0)
        try:
            with zipfile.ZipFile(buf, "r") as zf:
                entries: List[FileEntry] = []
                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    norm = info.filename.replace("\\", "/")
                    parts = norm.split("/", 1)
                    rel = parts[1] if len(parts) == 2 else parts[0]
                    if not rel or rel.startswith("/") or ".." in rel.split("/"):
                        continue
                    if rel.startswith(".git/") or is_ignored_path(rel):
                        continue
                    if info.file_size > max_file_size:
                        continue
                    lang = detect_language(rel)
                    content = ""
                    if lang in TEXT_LANGUAGES:
                        try:
                            with zf.open(info, "r") as member:
                                raw = member.read(max_file_size + 1)
                            if len(raw) <= max_file_size and b"\x00" not in raw:
                                content = raw.decode("utf-8", errors="replace")
                        except Exception:
                            content = ""
                    entries.append(FileEntry(path=rel, size=info.file_size, language=lang, content=content))
                    if len(entries) >= limit_files:
                        break
                return entries
        except zipfile.BadZipFile:
            continue
    return None


def fetch_public_repo(
    repo_url: str,
    ref: str = "main",
    max_files: Optional[int] = None,
    auth_token: Optional[str] = None,
) -> List[FileEntry]:
    """
    Ingests a public GitHub repository using the recursive tree API with bounded codeload fallback.
    Does NOT clone untrusted code (Constraint 1).
    """
    owner, repo = parse_github_url(repo_url)
    limit_files = max_files or Config.MAX_FILE_COUNT
    max_file_size = Config.MAX_INDIVIDUAL_FILE_MB * 1024 * 1024

    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Codebase-Audit-Platform/3.0",
    }
    if auth_token:
        headers["Authorization"] = f"token {auth_token}"

    branches_to_try = [ref, "main", "master"]
    tree_data = None
    resolved_branch = ref
    rate_limited_err: Optional[str] = None

    with httpx.Client(timeout=30.0) as client:
        for candidate_branch in branches_to_try:
            tree_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{candidate_branch}?recursive=1"
            try:
                res = client.get(tree_url, headers=headers)
                if res.status_code == 200:
                    tree_data = res.json()
                    resolved_branch = candidate_branch
                    break
                elif res.status_code == 403:
                    remaining = res.headers.get("x-ratelimit-remaining", "0")
                    reset_time = res.headers.get("x-ratelimit-reset")
                    log.warning("GitHub API rate limit hit (remaining=%s, reset=%s)", remaining, reset_time)
                    cached_files = list(CACHE_DIR.glob(f"{owner}_{repo}_*.json"))
                    if cached_files:
                        log.info("Serving from local tree cache for %s/%s", owner, repo)
                        with open(cached_files[0], "r", encoding="utf-8") as f:
                            tree_data = json.load(f)
                            break
                    rate_limited_err = (
                        f"GitHub API rate limit exceeded. Reset at {reset_time}. Provide GITHUB_TOKEN or use ZIP upload."
                    )
                    break
            except (httpx.HTTPError, ValueError) as exc:
                log.warning("Error fetching tree for %s (%s): %s", candidate_branch, tree_url, exc)

        if not tree_data or "tree" not in tree_data:
            fallback_entries = _fetch_via_codeload_zipball(
                client, owner, repo, branches_to_try, limit_files, max_file_size
            )
            if fallback_entries is not None:
                return fallback_entries
            if rate_limited_err:
                raise GitHubIngestionError(rate_limited_err)
            raise GitHubIngestionError(
                f"Unable to fetch repository tree for '{owner}/{repo}'. Check repository name or permissions."
            )

        # Cache successful tree response
        try:
            cache_file = _get_cache_path(owner, repo, tree_data.get("sha", resolved_branch))
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(tree_data, f)
        except Exception as exc:
            log.debug("Failed to cache tree: %s", exc)

        tree_entries = tree_data.get("tree", [])

        # Filter entries: blobs only, non-ignored paths
        valid_blobs = []
        for item in tree_entries:
            if item.get("type") != "blob":
                continue
            path = item.get("path", "")
            if is_ignored_path(path):
                continue
            size = item.get("size", 0)
            if size > max_file_size:
                continue
            valid_blobs.append(item)

        if len(valid_blobs) > limit_files:
            log.warning("Repository has %d files; truncating to %d", len(valid_blobs), limit_files)
            valid_blobs = valid_blobs[:limit_files]

        raw_base = f"https://raw.githubusercontent.com/{owner}/{repo}/{resolved_branch}"

        def _fetch_entry(blob: dict) -> FileEntry:
            path = blob["path"]
            size = blob.get("size", 0)
            lang = detect_language(path)
            content = ""
            if lang in TEXT_LANGUAGES:
                raw_url = f"{raw_base}/{path}"
                try:
                    blob_res = client.get(raw_url)
                    if blob_res.status_code == 200:
                        content = blob_res.text
                except Exception as exc:
                    log.debug("Failed to fetch raw content for %s: %s", path, exc)
            return FileEntry(path=path, size=size, language=lang, content=content)

        with ThreadPoolExecutor(max_workers=8) as pool:
            entries = list(pool.map(_fetch_entry, valid_blobs))

    return entries
