"""Pure secret-scanning patterns and helpers extracted from security collector."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import List, Tuple

SECRET_PATTERNS: List[Tuple[str, str, str, str]] = [
    (
        r"(?:A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}",
        "AWS Access Key ID",
        "critical",
        "AWS_KEY",
    ),
    (
        r"-----BEGIN (?:RSA|OPENSSH|DSA|EC|PGP) PRIVATE KEY-----",
        "Unencrypted Private Key",
        "critical",
        "PRIVATE_KEY",
    ),
    (
        r"(?:sk|rk)_(?:live|test)_[0-9a-zA-Z]{24,32}",
        "Stripe Secret Key",
        "critical",
        "STRIPE_SECRET",
    ),
    (
        r"gh[pousr]_[0-9a-zA-Z]{36,40}",
        "GitHub Personal Access Token",
        "critical",
        "GITHUB_TOKEN",
    ),
    (
        r"xox[baprs]-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24,32}",
        "Slack API Token",
        "high",
        "SLACK_TOKEN",
    ),
    (
        r"(?:api[_-]?key|secret[_-]?key|auth[_-]?token)\s*[:=]\s*['\"][0-9a-zA-Z\-_]{20,}['\"]",
        "Hardcoded Generic API Secret",
        "high",
        "GENERIC_SECRET",
    ),
    (
        r"(?:password|passwd|pwd)\s*[:=]\s*['\"][^'\"]{8,}['\"]",
        "Hardcoded Password Assignment",
        "high",
        "HARDCODED_PASSWORD",
    ),
]


@dataclass(frozen=True)
class SecretMatch:
    """Secret detection without storing the plaintext secret value."""

    secret_type: str
    severity: str
    rule_id: str
    kind: str
    line: int
    secret_hash: str


def hash_secret_value(raw_value: str) -> str:
    """Return full SHA-256 hex digest of the matched secret text."""
    return hashlib.sha256(raw_value.encode("utf-8", errors="replace")).hexdigest()


def is_placeholder_line(path: str, line_stripped: str) -> bool:
    """Skip explicit template placeholders in example/template files."""
    if path.endswith(".example") or ".template" in path.lower():
        lowered = line_stripped.lower()
        if "replace-me" in lowered or "your_" in lowered or "placeholder" in lowered:
            return True
    return False


def scan_text(path: str, content: str) -> List[SecretMatch]:
    """Scan text content for secret patterns without retaining raw secret values."""
    if not content:
        return []

    matches: List[SecretMatch] = []
    lines = content.splitlines()
    for line_idx, line in enumerate(lines, 1):
        line_str = line.strip()
        if is_placeholder_line(path, line_str):
            continue

        for pattern, secret_type, severity, kind in SECRET_PATTERNS:
            match = re.search(pattern, line)
            if match:
                matches.append(
                    SecretMatch(
                        secret_type=secret_type,
                        severity=severity,
                        rule_id=f"SECRET_{kind}",
                        kind=kind,
                        line=line_idx,
                        secret_hash=hash_secret_value(match.group(0)),
                    )
                )
    return matches
