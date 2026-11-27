"""Conservative license compatibility matrix and rule severity evaluator (LIC-001..005)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import yaml

_SEV_DOWNGRADE = {
    "critical": "high",
    "high": "medium",
    "medium": "low",
    "low": "low",
    "info": "info",
}


@lru_cache(maxsize=1)
def load_compatibility_matrix() -> Dict[str, Any]:
    return yaml.safe_load(Path(__file__).with_name("matrix.yaml").read_text(encoding="utf-8")) or {}


def is_explicitly_incompatible(project_spdx: str, project_class: str, dep_spdx: str, dep_class: str) -> bool:
    mat = load_compatibility_matrix()
    bad_classes = (mat.get("incompatible_class_pairs") or {}).get(project_class, [])
    if dep_class in bad_classes:
        return True
    for pair in mat.get("incompatible_spdx_pairs") or []:
        if pair.get("project") == project_spdx and pair.get("dependency") == dep_spdx:
            return True
    return False


def evaluate_dependency_license_rule(
    *,
    spdx_id: str,
    license_class: str,
    scope: str,
    project_spdx: str,
    project_class: str,
) -> Optional[Tuple[str, str]]:
    """
    Determine (rule_id, severity) for a dependency license given project posture and scope.
    Returns None if permissive / non-finding.
    """
    rule_id: Optional[str] = None
    severity: Optional[str] = None

    if license_class == "strong_copyleft":
        rule_id = "LIC-001"
        severity = "critical" if project_class == "proprietary" else "high"
    elif license_class == "network_copyleft":
        rule_id = "LIC-002"
        severity = "critical" if project_class == "proprietary" else "high"
    elif license_class == "weak_copyleft":
        rule_id = "LIC-003"
        severity = "low"
    elif license_class == "source_available":
        rule_id = "LIC-005"
        severity = "high"
    elif license_class == "unknown":
        if scope == "prod":
            rule_id = "LIC-004"
            severity = "medium"

    if rule_id is None or severity is None:
        return None

    # Downgrade one severity level for devDependencies / dev scope (P5 rule)
    if scope == "dev":
        severity = _SEV_DOWNGRADE.get(severity, "low")

    return rule_id, severity
