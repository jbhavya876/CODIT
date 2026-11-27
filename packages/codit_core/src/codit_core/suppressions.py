"""Suppression directives & dangerous construct pattern detection (Section 8.3, AGT-009)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Tuple

from codit_core.delta import AddedLine

# Note: @ts-expect-error is explicitly excluded because TypeScript errors when it is unused.
_PY_SUPPRESSION_RE = re.compile(
    r"(?:#\s*noqa\b|#\s*type:\s*ignore\b|#\s*pylint:\s*disable\b|#\s*nosec\b|#\s*pragma:\s*no\s+cover\b|#\s*nosemgrep\b)"
)
_JS_SUPPRESSION_RE = re.compile(
    r"(?://\s*eslint-disable(?:-next-line|-line)?\b|/\*\s*eslint-disable\b|//\s*@ts-(?:ignore|nocheck)\b|/\*\s*istanbul\s+ignore|//\s*nosemgrep\b)"
)

_SECURITY_SUPPRESSION_RE = re.compile(
    r"(?:#\s*nosec\b|//\s*nosemgrep\b|#\s*nosemgrep\b|#\s*noqa:\s*S\d+)"
)

_DANGEROUS_CONSTRUCT_RE = re.compile(
    r"(?:shell\s*=\s*True|\beval\(|\bexec\(|pickle\.loads?\(|yaml\.load\(|verify\s*=\s*False|innerHTML|dangerouslySetInnerHTML)"
)


@dataclass(frozen=True)
class SuppressionHit:
    line: int
    text: str
    is_security_suppression: bool
    has_dangerous_construct: bool


def scan_added_suppressions(
    language: str | None,
    added_lines: Tuple[AddedLine, ...],
) -> Tuple[List[SuppressionHit], bool]:
    """
    Scan added lines in a FileDelta for suppression directives and dangerous constructs.
    Returns (hits, commit_has_dangerous_construct).
    """
    pattern = _PY_SUPPRESSION_RE if language == "python" else _JS_SUPPRESSION_RE
    hits: List[SuppressionHit] = []
    any_dangerous = False

    for al in added_lines:
        if _DANGEROUS_CONSTRUCT_RE.search(al.text):
            any_dangerous = True
        if pattern.search(al.text):
            hits.append(
                SuppressionHit(
                    line=al.lineno,
                    text=al.text,
                    is_security_suppression=bool(_SECURITY_SUPPRESSION_RE.search(al.text)),
                    has_dangerous_construct=bool(_DANGEROUS_CONSTRUCT_RE.search(al.text)),
                )
            )
    return hits, any_dangerous
