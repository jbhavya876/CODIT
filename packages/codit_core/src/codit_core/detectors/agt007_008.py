"""Detectors AGT-007 (CI verification weakened/removed) & AGT-008 (quality gate lowered)."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from codit_core.ci_weakening import analyze_gate_config_change, analyze_github_workflow_changes
from codit_core.delta import CommitDelta
from codit_core.detectors.rules_catalog import make_core_finding
from codit_core.findings import CoreFinding


def detect_agt007_agt008(
    commit: CommitDelta,
    after_all_workflows: Optional[Dict[str, str]] = None,
    notes: Optional[List[str]] = None,
) -> List[CoreFinding]:
    findings: List[CoreFinding] = []
    gh_workflow_deltas: List[Tuple[str, str, Optional[str], Optional[str]]] = []

    for f in commit.files:
        norm = f.path.replace("\\", "/").lower()
        if f.kind == "ci":
            if norm.startswith(".github/workflows/") and norm.endswith((".yml", ".yaml")):
                gh_workflow_deltas.append((f.status, f.path, f.before_text, f.after_text))
            else:
                if notes is not None and "unsupported_ci" not in notes:
                    notes.append("unsupported_ci")

        if f.kind == "gate_config" and f.status in ("M", "R"):
            events, gate_note = analyze_gate_config_change(f.path, f.before_text, f.after_text)
            if gate_note and notes is not None and gate_note not in notes:
                notes.append(gate_note)
            for ev in events:
                findings.append(
                    make_core_finding(
                        rule_id=ev.rule_id,
                        evidence_file=ev.path,
                        evidence_line=1,
                        confidence="high",
                        severity=ev.severity,
                        basis="PATTERN",
                        commit_sha=commit.sha,
                        match_key=f"{ev.path}:{ev.change}",
                        params={
                            "short": commit.short,
                            "change": ev.change,
                            "path": ev.path,
                        },
                    )
                )

    if gh_workflow_deltas:
        ci_events = analyze_github_workflow_changes(gh_workflow_deltas, after_all_workflows=after_all_workflows)
        for ev in ci_events:
            findings.append(
                make_core_finding(
                    rule_id=ev.rule_id,
                    evidence_file=ev.path,
                    evidence_line=1,
                    confidence="high",
                    severity=ev.severity,
                    basis="PATTERN",
                    commit_sha=commit.sha,
                    match_key=f"{ev.path}:{ev.step_class}:{ev.change}",
                    params={
                        "short": commit.short,
                        "step_class": ev.step_class,
                        "change": ev.change,
                        "path": ev.path,
                    },
                )
            )

    return findings
