"""Stable finding fingerprints independent of line numbers."""

from __future__ import annotations

import hashlib
import re
from typing import Optional


def normalize_path(path: str) -> str:
    """Normalize repository-relative path using POSIX separators without leading './'."""
    norm = path.replace("\\", "/").strip()
    while norm.startswith("./"):
        norm = norm[2:]
    return norm


def normalize_match(text: str) -> str:
    """Collapse runs of whitespace so minor indentation/formatting edits preserve fingerprints."""
    return re.sub(r"\s+", " ", (text or "").strip())


def compute_fingerprint(
    rule_id: str,
    evidence_file: str,
    match_text: str = "",
    *,
    commit_sha: Optional[str] = None,
    secret_hash: Optional[str] = None,
) -> str:
    """
    Compute deterministic 32-char SHA-256 prefix for finding deduplication & baselines.

    Line numbers are intentionally excluded so unrelated edits above a finding keep its
    fingerprint stable. Secrets hash only `secret_hash`, never the plaintext value.
    """
    norm_path = normalize_path(evidence_file)
    if secret_hash:
        match_part = secret_hash
    else:
        match_part = normalize_match(match_text)

    parts = [rule_id or "", norm_path, match_part]
    if commit_sha:
        parts.append(commit_sha)
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:32]
