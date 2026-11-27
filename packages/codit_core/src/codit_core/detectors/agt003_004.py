"""Detectors AGT-003 (existing tests newly skipped) & AGT-004 (assertions removed)."""

from __future__ import annotations

from typing import List

from codit_core.delta import CommitDelta, PolicyThresholds
from codit_core.detectors.rules_catalog import make_core_finding
from codit_core.findings import CoreFinding


def detect_agt003_agt004(commit: CommitDelta, policy: PolicyThresholds) -> List[CoreFinding]:
    findings: List[CoreFinding] = []

    total_unconditional_skips_in_commit = 0
    file_skip_batches: list[tuple[str, int, str, int, bool, list[str]]] = []

    for f in commit.files:
        if f.kind != "test" or not f.before or not f.after:
            continue
        if f.before.metrics_unavailable or f.after.metrics_unavailable:
            continue
        if f.before.unsupported_framework or f.after.unsupported_framework:
            continue

        before_map = {c.name: c for c in f.before.cases}
        after_map = {c.name: c for c in f.after.cases}

        # AGT-003: existing case newly skipped
        newly_uncond: list[str] = []
        newly_cond: list[str] = []
        first_skip_line = 1

        # AGT-004: surviving case with fewer assertions
        reduced_cases: list[tuple[str, int, int, int]] = []

        for name, b_case in before_map.items():
            a_case = after_map.get(name)
            if a_case is None:
                continue
            if b_case.skipped == "none" and a_case.skipped != "none":
                if not newly_uncond and not newly_cond:
                    first_skip_line = a_case.line
                if a_case.skipped == "conditional":
                    newly_cond.append(name)
                else:
                    newly_uncond.append(name)
            if a_case.assertions < b_case.assertions:
                reduced_cases.append((name, b_case.assertions, a_case.assertions, a_case.line))

        total_unconditional_skips_in_commit += len(newly_uncond)
        whole_file_skipped = (
            len(f.after.cases) > 0
            and all(c.skipped != "none" for c in f.after.cases)
            and len(newly_uncond) > 0
        )

        if newly_uncond:
            file_skip_batches.append((f.path, first_skip_line, "unconditional", len(newly_uncond), whole_file_skipped, newly_uncond))
        elif newly_cond:
            file_skip_batches.append((f.path, first_skip_line, "conditional", len(newly_cond), False, newly_cond))

        if reduced_cases:
            drops_to_zero = any(a_cnt == 0 for _, _, a_cnt, _ in reduced_cases)
            sev = "high" if drops_to_zero else "medium"
            conf = "high" if drops_to_zero else "medium"
            names_key = ",".join(sorted(r[0] for r in reduced_cases[:5]))
            findings.append(
                make_core_finding(
                    rule_id="AGT-004",
                    evidence_file=f.path,
                    evidence_line=reduced_cases[0][3],
                    confidence=conf,
                    severity=sev,
                    basis="HISTORY PROOF",
                    commit_sha=commit.sha,
                    match_key=f"{f.path}:{names_key}",
                    params={
                        "short": commit.short,
                        "n": len(reduced_cases),
                        "path": f.path,
                        "drops_to_zero": drops_to_zero,
                    },
                )
            )

    for path, line, kind, n_cases, whole_file, names in file_skip_batches:
        if kind == "conditional":
            sev = "low"
        elif whole_file or total_unconditional_skips_in_commit >= policy.skip_high_count:
            sev = "high"
        else:
            sev = "medium"

        findings.append(
            make_core_finding(
                rule_id="AGT-003",
                evidence_file=path,
                evidence_line=line,
                confidence="high",
                severity=sev,
                basis="AST PROOF",
                commit_sha=commit.sha,
                match_key=f"{path}:{','.join(sorted(names[:5]))}",
                params={
                    "short": commit.short,
                    "n": n_cases,
                    "path": path,
                    "skip_kind": kind,
                },
            )
        )

    return findings
