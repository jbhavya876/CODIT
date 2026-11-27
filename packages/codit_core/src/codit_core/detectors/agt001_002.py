"""Detectors AGT-001 (tests removed alongside covered code) & AGT-002 (pure test removal)."""

from __future__ import annotations

import difflib
from typing import Dict, List, Optional, Tuple

from codit_core.delta import CommitDelta, FileDelta, PolicyThresholds, TestCaseMetric
from codit_core.detectors.rules_catalog import make_core_finding
from codit_core.findings import CoreFinding
from codit_core.mapping import map_test_to_production


def _collect_added_cases(commit: CommitDelta) -> List[TestCaseMetric]:
    added: List[TestCaseMetric] = []
    for f in commit.files:
        if f.kind != "test":
            continue
        before_names = {c.name for c in (f.before.cases if f.before else ())}
        for c in (f.after.cases if f.after else ()):
            if c.name not in before_names:
                added.append(c)
    return added


def _is_moved_or_renamed(
    removed_case: TestCaseMetric,
    added_cases: List[TestCaseMetric],
    similarity_threshold: float,
) -> bool:
    for ac in added_cases:
        if ac.body_hash == removed_case.body_hash:
            return True
        ratio = difflib.SequenceMatcher(None, removed_case.name.lower(), ac.name.lower()).ratio()
        if ratio >= similarity_threshold:
            return True
    return False


def detect_agt001_agt002(
    commit: CommitDelta,
    policy: PolicyThresholds,
    test_contents: Optional[Dict[str, str]] = None,
) -> List[CoreFinding]:
    findings: List[CoreFinding] = []
    added_cases = _collect_added_cases(commit)

    deleted_paths = {f.path for f in commit.files if f.status == "D"}
    prod_changed_paths = {
        f.path: f.status
        for f in commit.files
        if f.kind in ("source", "manifest")
    }
    prod_am_paths = {p for p, st in prod_changed_paths.items() if st in ("A", "M")}
    candidate_paths = set(commit.tree_paths) | set(prod_changed_paths.keys())

    for f in commit.files:
        if f.kind != "test" or f.status not in ("M", "D"):
            continue
        if not f.before or f.before.metrics_unavailable or f.before.unsupported_framework:
            continue
        if f.after and f.after.metrics_unavailable:
            continue

        after_names = {c.name for c in (f.after.cases if f.after else ())}
        removed_cases = [c for c in f.before.cases if c.name not in after_names]
        if not removed_cases:
            continue

        # Exclude tests moved to another file or renamed with same body/similar name
        net_removed = [
            rc for rc in removed_cases
            if not _is_moved_or_renamed(rc, added_cases, policy.moved_name_similarity)
        ]
        if not net_removed:
            continue

        t_content = (test_contents or {}).get(f.path)
        mapped = map_test_to_production(f.path, candidate_paths, test_content=t_content)
        mapped_paths = {m.path for m in mapped}

        # Suppress if mapped production file was deleted in the same commit (legitimate feature removal, s15)
        if mapped_paths and (mapped_paths & deleted_paths) and not (mapped_paths & prod_am_paths):
            continue

        has_mapped_prod_am = bool(mapped_paths & prod_am_paths)
        has_any_prod_am = bool(prod_am_paths)
        has_any_prod_del = bool(deleted_paths & set(prod_changed_paths.keys()))

        squash_capped = commit.files_changed > policy.squash_confidence_cap_files

        if has_mapped_prod_am or has_any_prod_am:
            conf = "high" if has_mapped_prod_am else "medium"
            if squash_capped and conf == "high":
                conf = "medium"
            match_names = ",".join(sorted(c.name for c in net_removed[:5]))
            findings.append(
                make_core_finding(
                    rule_id="AGT-001",
                    evidence_file=f.path,
                    evidence_line=net_removed[0].line,
                    confidence=conf,
                    severity="high",
                    basis="HISTORY PROOF",
                    commit_sha=commit.sha,
                    match_key=f"{f.path}:{match_names}",
                    params={
                        "short": commit.short,
                        "n": len(net_removed),
                        "path": f.path,
                        "squash_capped": squash_capped,
                    },
                )
            )
        elif not has_any_prod_del:
            before_total = max(1, len(f.before.cases))
            pct = len(net_removed) / before_total
            if len(net_removed) >= policy.min_removed or pct >= policy.min_removed_pct:
                conf = "medium" if squash_capped else "high"
                match_names = ",".join(sorted(c.name for c in net_removed[:5]))
                findings.append(
                    make_core_finding(
                        rule_id="AGT-002",
                        evidence_file=f.path,
                        evidence_line=net_removed[0].line,
                        confidence=conf,
                        severity="medium",
                        basis="HISTORY PROOF",
                        commit_sha=commit.sha,
                        match_key=f"{f.path}:{match_names}",
                        params={
                            "short": commit.short,
                            "n": len(net_removed),
                            "path": f.path,
                            "squash_capped": squash_capped,
                        },
                    )
                )

    return findings
