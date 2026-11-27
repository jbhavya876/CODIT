"""Grouped plain-text output and `explain RULE_ID` formatter."""

from __future__ import annotations

from typing import Any, Dict, List

from codit_core.detectors.rules_catalog import load_rules_catalog
from codit_core.findings import CoreFinding

_SEVERITY_ORDER = ("critical", "high", "medium", "low", "info")
_GLYPHS = {
    "critical": "[CRIT]",
    "high": "[HIGH]",
    "medium": "[MED]",
    "low": "[LOW]",
    "info": "[INFO]",
}


def format_text_report(result_dict: Dict[str, Any]) -> str:
    findings = result_dict.get("findings", [])
    lines: List[str] = [
        f"codit-guard ({result_dict.get('scope')}) — {len(findings)} finding(s), "
        f"baselined: {result_dict.get('baselined_count', 0)}, "
        f"suppressed: {result_dict.get('suppressed_count', 0)}, "
        f"config: {result_dict.get('config_source')}",
    ]

    if findings:
        grouped: Dict[str, List[Dict[str, Any]]] = {s: [] for s in _SEVERITY_ORDER}
        for f in findings:
            grouped.setdefault(f.get("severity", "low"), []).append(f)
        for sev in _SEVERITY_ORDER:
            bucket = grouped.get(sev) or []
            if not bucket:
                continue
            lines.append("")
            lines.append(f"{_GLYPHS.get(sev, sev.upper())} ({len(bucket)})")
            for f in bucket:
                ln = f.get("evidence_line") or 1
                rid = f.get("rule_id")
                fp = (f.get("fingerprint") or "")[:12]
                lines.append(
                    f"  {rid} {f.get('evidence_file')}:{ln} [{fp}] — {f.get('description')}"
                )
                lines.append(f"    hint: run `codit-guard explain {rid}`")

    expired = result_dict.get("expired_suppressions") or []
    if expired:
        lines.append("")
        lines.append(f"Expired suppressions ignored: {', '.join(expired)}")

    not_assessed = result_dict.get("not_assessed") or []
    if not_assessed:
        lines.append("")
        lines.append("Not assessed:")
        for item in not_assessed:
            lines.append(f"  - {item.get('check')}: {item.get('reason')}")

    return "\n".join(lines)


def format_rule_explanation(rule_id: str) -> str:
    catalog = load_rules_catalog()
    key = rule_id.strip().upper()
    meta = catalog.get(key)
    if meta is None:
        return ""

    lines = [
        f"{key} — {meta.get('title', key)}",
        f"Dimension: {meta.get('dimension')} | Default severity: {meta.get('default_severity')} | Basis: {meta.get('basis')}",
        "",
        f"Rationale:   {meta.get('rationale', '')}",
        f"Example:     {meta.get('example', '')}",
        f"Remediation: {meta.get('remediation', '')}",
    ]
    if key == "GRD-002":
        lines.append("Note:        Shell command inspection is best-effort and not complete.")
    return "\n".join(lines)
