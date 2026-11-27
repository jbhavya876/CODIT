"""Orchestrator running all AGT-* detectors and computing Integrity Ledger series."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from codit_core.delta import CommitDelta, FileMetrics, PolicyThresholds
from codit_core.detectors.agt001_002 import detect_agt001_agt002
from codit_core.detectors.agt003_004 import detect_agt003_agt004
from codit_core.detectors.agt005_006 import detect_agt005_agt006
from codit_core.detectors.agt007_008 import detect_agt007_agt008
from codit_core.detectors.agt009_011_012 import detect_agt009, detect_agt011, detect_agt012_head
from codit_core.detectors.agt010 import detect_agt010
from codit_core.findings import CoreFinding

_CONF_ORDER = ("low", "medium", "high")


def _bump_confidence(conf: str) -> str:
    try:
        idx = _CONF_ORDER.index(conf)
    except ValueError:
        return "medium"
    return _CONF_ORDER[min(idx + 1, len(_CONF_ORDER) - 1)]


@dataclass
class DetectorRunResult:
    findings: List[CoreFinding]
    series: List[Dict[str, object]]
    notes: List[str] = field(default_factory=list)


def run_detectors(
    commits: List[CommitDelta],
    *,
    policy: Optional[PolicyThresholds] = None,
    head_secret_hashes: Optional[Set[str]] = None,
    head_test_metrics: Optional[Dict[str, FileMetrics]] = None,
    after_all_workflows: Optional[Dict[str, str]] = None,
    test_contents_by_commit: Optional[Dict[str, Dict[str, str]]] = None,
    apply_head_rules: bool = True,
) -> DetectorRunResult:
    """
    Execute all pure detectors deterministically across `commits` (oldest -> newest).
    Also applies Modifier M-1 (claim contradiction) and computes Integrity Ledger series.
    """
    pol = policy or PolicyThresholds()
    findings: List[CoreFinding] = []
    notes: List[str] = []
    series: List[Dict[str, object]] = []

    # Running totals of test metrics across test files per commit
    test_state: Dict[str, FileMetrics] = {}
    focus_intro: Dict[Tuple[str, str], Tuple[str, str]] = {}

    for commit in commits:
        commit_findings: List[CoreFinding] = []

        # Track running test suite totals even on shallow baseline
        for f in commit.files:
            if f.kind == "test":
                if f.old_path and f.old_path in test_state and f.status == "R":
                    test_state.pop(f.old_path, None)
                if f.status == "D":
                    test_state.pop(f.path, None)
                elif f.after is not None and not f.after.metrics_unavailable:
                    test_state[f.path] = f.after
                    before_focused = {c.name for c in (f.before.cases if f.before else ()) if c.focused}
                    for c in f.after.cases:
                        if c.focused and c.name not in before_focused and (f.path, c.name) not in focus_intro:
                            focus_intro[(f.path, c.name)] = (commit.sha, commit.short)

        total_tests = sum(len(fm.cases) for fm in test_state.values())
        total_assertions = sum(sum(c.assertions for c in fm.cases) for fm in test_state.values())
        total_skipped = sum(sum(1 for c in fm.cases if c.skipped != "none") for fm in test_state.values())
        prod_delta = sum(
            (f.added_count - f.removed_count)
            for f in commit.files
            if f.kind in ("source", "manifest")
        )
        series.append({
            "short": commit.short,
            "sha": commit.sha,
            "date": commit.date,
            "tests": total_tests,
            "assertions": total_assertions,
            "skipped": total_skipped,
            "prod_lines_delta": prod_delta,
        })

        if commit.shallow_baseline:
            continue

        t_contents = (test_contents_by_commit or {}).get(commit.sha)
        commit_findings.extend(detect_agt001_agt002(commit, pol, test_contents=t_contents))
        commit_findings.extend(detect_agt003_agt004(commit, pol))
        commit_findings.extend(detect_agt005_agt006(commit))
        commit_findings.extend(detect_agt007_agt008(commit, after_all_workflows=after_all_workflows, notes=notes))
        commit_findings.extend(detect_agt009(commit, pol))
        commit_findings.extend(detect_agt011(commit, pol))

        # Modifier M-1: Claim contradiction
        if commit.claims_tests_pass:
            for cf in commit_findings:
                if cf.rule_id in ("AGT-001", "AGT-002", "AGT-003", "AGT-004", "AGT-005"):
                    cf.confidence = _bump_confidence(cf.confidence)
                    cf.params["claim_contradiction"] = True

        findings.extend(commit_findings)

    if apply_head_rules:
        if head_secret_hashes is not None:
            findings.extend(detect_agt010(commits, head_secret_hashes))
        if head_test_metrics is not None:
            findings.extend(detect_agt012_head(head_test_metrics, focus_introduced_in=focus_intro))

    return DetectorRunResult(findings=findings, series=series, notes=notes)
