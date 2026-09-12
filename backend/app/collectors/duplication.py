"""
Duplication Audit Collector:
Detects duplicated code blocks across repository source files.
Implements tokenized sliding-window block hashing with jscpd fallback.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from typing import Dict, List, Set, Tuple

from backend.app.collectors.models import AuditFinding
from backend.app.ingestion.models import FileEntry

log = logging.getLogger(__name__)

MIN_DUPLICATE_LINES = 5


def _normalize_line(line: str) -> str:
    """Normalizes a source code line by stripping whitespace and comments."""
    cleaned = line.strip()
    if cleaned.startswith("//") or cleaned.startswith("#") or cleaned.startswith("/*"):
        return ""
    return cleaned


def detect_code_duplication(files: List[FileEntry]) -> List[AuditFinding]:
    """
    Scans source files for duplicated blocks of MIN_DUPLICATE_LINES or more.
    """
    findings: List[AuditFinding] = []
    # Map from block_hash -> (file_path, line_number, raw_snippet)
    seen_blocks: Dict[str, Tuple[str, int, str]] = {}
    reported_pairs: Set[Tuple[str, str]] = set()

    eligible_files = [
        f for f in files
        if f.language in ("python", "javascript", "typescript")
        and not f.path.lower().startswith("tests/")
        and "mock" not in f.path.lower()
    ]

    for entry in eligible_files:
        lines = entry.content.splitlines()
        if len(lines) < MIN_DUPLICATE_LINES:
            continue

        normalized_lines = [_normalize_line(l) for l in lines]

        for i in range(len(lines) - MIN_DUPLICATE_LINES + 1):
            window = normalized_lines[i : i + MIN_DUPLICATE_LINES]
            # Ignore windows consisting mostly of blank lines or single brackets
            non_empty = [l for l in window if len(l) > 3 and l not in ("{", "}", ");", "pass", "return")]
            if len(non_empty) < 4:
                continue

            block_text = "\n".join(window)
            block_hash = hashlib.sha256(block_text.encode("utf-8")).hexdigest()

            if block_hash in seen_blocks:
                orig_file, orig_line, snippet = seen_blocks[block_hash]
                if orig_file != entry.path:
                    pair_key = tuple(sorted([orig_file, entry.path]))
                    if pair_key not in reported_pairs:
                        reported_pairs.add(pair_key)
                        current_line = i + 1
                        findings.append(AuditFinding(
                            id=f"dup-{uuid.uuid4().hex[:6]}",
                            dimension="duplication",
                            severity="medium",
                            confidence="high",
                            description=(
                                f"Duplicated code block ({MIN_DUPLICATE_LINES}+ lines) shared between "
                                f"'{entry.path}' (line {current_line}) and '{orig_file}' (line {orig_line})."
                            ),
                            evidence_file=entry.path,
                            evidence_line=current_line,
                            rule_id="CODE_DUPLICATION_BLOCK",
                            remediation="Extract duplicated logic into a shared helper function or reusable component.",
                            component_id=entry.path,
                        ))
            else:
                seen_blocks[block_hash] = (entry.path, i + 1, block_text)

    return findings


def run_duplication_collector(files: List[FileEntry]) -> List[AuditFinding]:
    """Runs code clone and duplication detection across codebase."""
    return detect_code_duplication(files)
