"""SARIF 2.1.0 serializer for codit-guard."""

from __future__ import annotations

import os
from typing import Any, Dict, List

from codit_core.detectors.rules_catalog import load_rules_catalog
from codit_core.findings import CoreFinding

SARIF_SCHEMA = "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json"

_LEVEL_MAP = {
    "critical": "error",
    "high": "error",
    "medium": "warning",
    "low": "note",
    "info": "note",
}


def build_sarif(findings: List[CoreFinding], *, base_url: str | None = None) -> Dict[str, Any]:
    pub_base = (base_url or os.getenv("PUBLIC_BASE_URL") or "https://coditt.xyz").rstrip("/")
    catalog = load_rules_catalog()

    seen_rules: Dict[str, Dict[str, Any]] = {}
    results: List[Dict[str, Any]] = []

    for f in findings:
        rid = f.rule_id or "CODIT-FINDING"
        if rid not in seen_rules:
            meta = catalog.get(rid, {})
            title = meta.get("title") or rid
            rationale = meta.get("rationale") or f.description
            seen_rules[rid] = {
                "id": rid,
                "name": rid,
                "shortDescription": {"text": title},
                "fullDescription": {"text": rationale},
                "helpUri": f"{pub_base}/rubric/2.0.0#{rid}",
                "defaultConfiguration": {"level": _LEVEL_MAP.get(meta.get("default_severity", "medium"), "warning")},
            }

        results.append({
            "ruleId": rid,
            "level": _LEVEL_MAP.get(f.severity, "warning"),
            "message": {"text": f.description},
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {"uri": f.evidence_file},
                        "region": {"startLine": max(1, int(f.evidence_line or 1))},
                    }
                }
            ],
            "partialFingerprints": {
                "codit/v1": f.fingerprint or f.id,
            },
        })

    return {
        "version": "2.1.0",
        "$schema": SARIF_SCHEMA,
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "codit-guard",
                        "version": "3.0.0",
                        "informationUri": pub_base,
                        "rules": list(seen_rules.values()),
                    }
                },
                "results": results,
            }
        ],
    }
