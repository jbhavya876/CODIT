"""Detector AGT-010: Secret present in git history but absent at HEAD."""

from __future__ import annotations

from typing import Dict, List, Set

from codit_core.delta import CommitDelta
from codit_core.detectors.rules_catalog import make_core_finding
from codit_core.findings import CoreFinding


def detect_agt010(
    commits: List[CommitDelta],
    head_secret_hashes: Set[str],
) -> List[CoreFinding]:
    """
    Track `secret_hash -> (first_sha, first_short, path, kind, line)` across commits.
    Any secret committed in history and absent from HEAD emits AGT-010.
    Never stores or prints raw secret text (evidence is `<redacted:KIND>`).
    """
    first_seen: Dict[str, tuple[str, str, str, str, int]] = {}
    for commit in commits:
        for path, kind, lineno, secret_hash in commit.added_secrets:
            if secret_hash not in first_seen:
                first_seen[secret_hash] = (commit.sha, commit.short, path, kind, lineno)

    findings: List[CoreFinding] = []
    for secret_hash, (sha, short, path, kind, lineno) in first_seen.items():
        if secret_hash in head_secret_hashes:
            continue
        findings.append(
            make_core_finding(
                rule_id="AGT-010",
                evidence_file=path,
                evidence_line=lineno,
                confidence="high",
                severity="high",
                basis="PATTERN",
                commit_sha=sha,
                secret_hash=secret_hash,
                match_key=secret_hash[:12],
                params={
                    "kind": kind,
                    "short": short,
                    "path": path,
                    "secret_hash_prefix": secret_hash[:12],
                    "redacted": f"<redacted:{kind}>",
                },
            )
        )
    return findings
