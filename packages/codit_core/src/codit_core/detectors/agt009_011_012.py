"""Detectors AGT-009 (suppression bursts), AGT-011 (megacommit without tests), AGT-012 (focus markers)."""

from __future__ import annotations

from typing import Dict, List

from codit_core.delta import CommitDelta, FileMetrics, PolicyThresholds
from codit_core.detectors.rules_catalog import make_core_finding
from codit_core.findings import CoreFinding
from codit_core.suppressions import scan_added_suppressions


def detect_agt009(commit: CommitDelta, policy: PolicyThresholds) -> List[CoreFinding]:
    findings: List[CoreFinding] = []
    commit_has_dangerous = False
    sec_suppressions: List[tuple[str, int, str]] = []
    total_hits = 0
    first_hit_path = ""
    first_hit_line = 1

    for f in commit.files:
        if f.kind == "generated" or f.language not in ("python", "javascript", "typescript"):
            continue
        hits, has_dangerous = scan_added_suppressions(f.language, f.added)
        if has_dangerous:
            commit_has_dangerous = True
        for h in hits:
            total_hits += 1
            if not first_hit_path:
                first_hit_path = f.path
                first_hit_line = h.line
            if h.is_security_suppression:
                sec_suppressions.append((f.path, h.line, h.text))

    if commit_has_dangerous and sec_suppressions:
        path, line, txt = sec_suppressions[0]
        findings.append(
            make_core_finding(
                rule_id="AGT-009",
                evidence_file=path,
                evidence_line=line,
                confidence="high",
                severity="high",
                basis="PATTERN",
                commit_sha=commit.sha,
                match_key=f"{path}:sec_suppression:{txt.strip()}",
                params={
                    "short": commit.short,
                    "n": len(sec_suppressions),
                    "path": path,
                    "escalated": True,
                },
            )
        )
    elif total_hits >= policy.suppression_burst and first_hit_path:
        findings.append(
            make_core_finding(
                rule_id="AGT-009",
                evidence_file=first_hit_path,
                evidence_line=first_hit_line,
                confidence="high",
                severity="low",
                basis="PATTERN",
                commit_sha=commit.sha,
                match_key=f"{first_hit_path}:burst:{total_hits}",
                params={
                    "short": commit.short,
                    "n": total_hits,
                    "path": first_hit_path,
                    "escalated": False,
                },
            )
        )

    return findings


def detect_agt011(commit: CommitDelta, policy: PolicyThresholds) -> List[CoreFinding]:
    """Large change without test changes (excludes generated/lockfiles/vendor/min.js/snapshots)."""
    non_generated_files = [f for f in commit.files if f.kind != "generated"]
    test_files_changed = any(f.kind == "test" for f in commit.files)
    if test_files_changed:
        return []

    prod_lines = sum(
        (f.added_count + f.removed_count)
        for f in non_generated_files
        if f.kind in ("source", "manifest")
    )
    non_gen_count = len(non_generated_files)

    if commit.skipped_deep or prod_lines >= policy.megacommit_lines or non_gen_count >= policy.megacommit_files:
        evidence_path = non_generated_files[0].path if non_generated_files else "repository"
        return [
            make_core_finding(
                rule_id="AGT-011",
                evidence_file=evidence_path,
                evidence_line=1,
                confidence="high",
                severity="low",
                basis="HISTORY PROOF",
                commit_sha=commit.sha,
                match_key=f"{commit.short}:{non_gen_count}:{prod_lines}",
                params={
                    "short": commit.short,
                    "files": commit.files_changed if commit.skipped_deep else non_gen_count,
                    "lines": prod_lines,
                    "path": evidence_path,
                },
            )
        ]
    return []


def detect_agt012_head(
    head_test_metrics: Dict[str, FileMetrics],
    focus_introduced_in: Optional[Dict[tuple[str, str], tuple[str, str]]] = None,
) -> List[CoreFinding]:
    """Emit AGT-012 for any `.only`, `fit`, `fdescribe` focus markers present at HEAD."""
    findings: List[CoreFinding] = []
    for path, fm in sorted(head_test_metrics.items()):
        for case in fm.cases:
            if not case.focused:
                continue
            intro = (focus_introduced_in or {}).get((path, case.name))
            intro_sha = intro[0] if intro else None
            short_sha = intro[1] if intro else "HEAD"
            f = make_core_finding(
                rule_id="AGT-012",
                evidence_file=path,
                evidence_line=case.line,
                confidence="high",
                severity="medium",
                basis="AST PROOF",
                commit_sha=intro_sha,
                match_key=f"{path}:{case.name}",
                params={
                    "form": ".only/fit/fdescribe",
                    "path": path,
                    "short": short_sha,
                    "introduced_in": intro_sha,
                },
            )
            findings.append(f)
    return findings
