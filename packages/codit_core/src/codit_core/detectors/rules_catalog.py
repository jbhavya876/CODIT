"""Loader and template renderer for codit_core/rules.yaml (Section 8)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

import yaml

from codit_core.findings import CoreFinding
from codit_core.fingerprint import compute_fingerprint


@lru_cache(maxsize=1)
def load_rules_catalog() -> Dict[str, Dict[str, Any]]:
    rules_path = Path(__file__).resolve().parents[1] / "rules.yaml"
    data = yaml.safe_load(rules_path.read_text(encoding="utf-8")) or {}
    return dict(data.get("rules", {}))


def get_rule_meta(rule_id: str) -> Dict[str, Any]:
    return load_rules_catalog().get(rule_id, {})


def render_finding_description(rule_id: str, params: Dict[str, Any]) -> str:
    meta = get_rule_meta(rule_id)
    template = meta.get("template", "{rule_id} triggered at {path}.")
    safe_params = {"rule_id": rule_id, "path": "", "short": "", **params}
    try:
        return template.format(**safe_params)
    except Exception:
        return template


def make_core_finding(
    *,
    rule_id: str,
    evidence_file: str,
    evidence_line: int | None,
    confidence: str,
    params: Dict[str, Any],
    match_key: str,
    severity: str | None = None,
    basis: str | None = None,
    commit_sha: str | None = None,
    secret_hash: str | None = None,
) -> CoreFinding:
    meta = get_rule_meta(rule_id)
    sev = severity or meta.get("default_severity", "medium")
    dim = meta.get("dimension", "agent_integrity")
    eff_basis = basis or meta.get("basis", "HISTORY PROOF")
    remediation = meta.get("remediation", "")
    fp = compute_fingerprint(
        rule_id,
        evidence_file,
        match_key,
        commit_sha=commit_sha,
        secret_hash=secret_hash,
    )
    uid = f"{rule_id.lower()}-{fp[:8]}"
    if evidence_line is not None:
        uid = f"{uid}-{evidence_line}"

    desc = render_finding_description(rule_id, {"path": evidence_file, **params})
    return CoreFinding(
        id=uid,
        dimension=dim,
        severity=sev,
        confidence=confidence,
        description=desc,
        evidence_file=evidence_file,
        evidence_line=evidence_line,
        rule_id=rule_id,
        remediation=remediation,
        component_id=evidence_file,
        fingerprint=fp,
        basis=eff_basis,
        commit_sha=commit_sha,
        params=dict(params),
    )
