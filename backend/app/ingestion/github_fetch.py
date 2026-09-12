"""
Public repository ingestion via GitHub REST API tree fetch.

Fetches file trees recursively without performing full git clones.
Enforces size and file count caps, and implements rate-limit backoff and caching.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
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


def fetch_public_repo(
    repo_url: str,
    ref: str = "main",
    max_files: Optional[int] = None,
    auth_token: Optional[str] = None,
) -> List[FileEntry]:
    """
    Ingests a public GitHub repository using the recursive tree API.
    Does NOT clone untrusted code (Constraint 1).
    """
    owner, repo = parse_github_url(repo_url)
    limit_files = max_files or Config.MAX_FILE_COUNT
    max_file_size = Config.MAX_INDIVIDUAL_FILE_MB * 1024 * 1024

    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Codebase-Audit-Platform/2.0",
    }
    if auth_token:
        headers["Authorization"] = f"token {auth_token}"

    client = httpx.Client(timeout=30.0)

    # 1. Resolve repository default branch if needed
    branches_to_try = [ref, "main", "master"]
    tree_data = None
    resolved_branch = ref

    for candidate_branch in branches_to_try:
        tree_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{candidate_branch}?recursive=1"
        try:
            res = client.get(tree_url, headers=headers)
            if res.status_code == 200:
                tree_data = res.json()
                resolved_branch = candidate_branch
                break
            elif res.status_code == 403:
                # Rate limit hit
                remaining = res.headers.get("x-ratelimit-remaining", "0")
                reset_time = res.headers.get("x-ratelimit-reset")
                log.warning("GitHub API rate limit hit (remaining=%s, reset=%s)", remaining, reset_time)
                # If cached version exists, use it
                cached_files = list(CACHE_DIR.glob(f"{owner}_{repo}_*.json"))
                if cached_files:
                    log.info("Serving from local tree cache for %s/%s", owner, repo)
                    with open(cached_files[0], "r", encoding="utf-8") as f:
                        tree_data = json.load(f)
                        break
                raise GitHubIngestionError(
                    f"GitHub API rate limit exceeded. Reset at {reset_time}. Provide GITHUB_TOKEN or use ZIP upload."
                )
        except httpx.RequestError as exc:
            log.warning("Error fetching tree for %s (%s): %s", candidate_branch, tree_url, exc)

    if not tree_data or "tree" not in tree_data:
        raise GitHubIngestionError(f"Unable to fetch repository tree for '{owner}/{repo}'. Check repository name or permissions.")

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

    entries: List[FileEntry] = []

    # Fetch blob contents via raw.githubusercontent.com (fast, no API token needed)
    raw_base = f"https://raw.githubusercontent.com/{owner}/{repo}/{resolved_branch}"

    for blob in valid_blobs:
        path = blob["path"]
        size = blob.get("size", 0)
        lang = detect_language(path)

        # Only fetch text content for relevant languages and configs
        content = ""
        if lang in ("python", "javascript", "typescript", "json", "toml", "yaml", "dockerfile", "env", "text", "markdown"):
            raw_url = f"{raw_base}/{path}"
            try:
                blob_res = client.get(raw_url)
                if blob_res.status_code == 200:
                    content = blob_res.text
            except Exception as exc:
                log.debug("Failed to fetch raw content for %s: %s", path, exc)

        entries.append(FileEntry(
            path=path,
            size=size,
            language=lang,
            content=content,
        ))

    client.close()
    return entries
