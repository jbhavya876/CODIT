"""Schema-validated `.codit.yml` configuration loader with base-commit trust support."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import jsonschema
import yaml

from codit_core.delta import PolicyThresholds

MAX_SUPPRESSION_DAYS = 180

_CONFIG_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "version": {"type": "integer", "enum": [1]},
        "project_license": {"type": ["string", "null"]},
        "paths": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "ignore": {"type": "array", "items": {"type": "string"}},
                "test_globs": {"type": "array", "items": {"type": "string"}},
            },
        },
        "policy": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "fail_on": {"enum": ["critical", "high", "medium", "never"]},
                "protect_policy": {"type": "boolean"},
                "thresholds": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "min_removed": {"type": "integer", "minimum": 1},
                        "suppression_burst": {"type": "integer", "minimum": 1},
                        "megacommit_lines": {"type": "integer", "minimum": 1},
                        "megacommit_files": {"type": "integer", "minimum": 1},
                    },
                },
            },
        },
        "hook": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "block_on": {"type": "array", "items": {"type": "string"}},
            },
        },
        "checks": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "advisories": {"enum": ["warn", "off"]},
                "licenses": {"enum": ["warn", "off"]},
            },
        },
        "suppressions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["fingerprint", "reason", "expires"],
                "properties": {
                    "fingerprint": {"type": "string", "minLength": 4},
                    "reason": {"type": "string", "minLength": 10},
                    "expires": {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"},
                },
            },
        },
    },
}

DEFAULT_BLOCK_ON = [
    "SEC-SECRET",
    "AGT-005",
    "AGT-007",
    "AGT-003",
    "AGT-002",
    "GRD-001",
    "GRD-002",
]


class GuardConfigError(ValueError):
    """Raised on invalid `.codit.yml` syntax, schema violation, or suppression policy error."""


@dataclass
class GuardConfig:
    version: int = 1
    project_license: Optional[str] = None
    ignore_paths: List[str] = field(default_factory=lambda: ["vendor/**", "dist/**"])
    test_globs: List[str] = field(default_factory=list)
    fail_on: str = "high"
    protect_policy: bool = True
    thresholds: PolicyThresholds = field(default_factory=PolicyThresholds)
    block_on: List[str] = field(default_factory=lambda: list(DEFAULT_BLOCK_ON))
    advisories: str = "warn"
    licenses: str = "warn"
    active_suppressions: Dict[str, str] = field(default_factory=dict)
    expired_suppressions: List[str] = field(default_factory=list)
    source: str = "default"


def parse_config_yaml(raw_yaml: str, *, source: str = "working", today: Optional[date] = None) -> GuardConfig:
    try:
        parsed = yaml.safe_load(raw_yaml)
    except yaml.YAMLError as exc:
        raise GuardConfigError(f"Invalid YAML in .codit.yml: {exc}") from exc
    if parsed is None:
        return GuardConfig(source=source)
    if not isinstance(parsed, dict):
        raise GuardConfigError(".codit.yml root must be a YAML mapping.")

    try:
        jsonschema.validate(instance=parsed, schema=_CONFIG_SCHEMA)
    except jsonschema.ValidationError as exc:
        raise GuardConfigError(f"Invalid .codit.yml schema: {exc.message}") from exc

    cur_date = today or date.today()
    max_expiry = cur_date + timedelta(days=MAX_SUPPRESSION_DAYS)

    active_supps: Dict[str, str] = {}
    expired_supps: List[str] = []
    for entry in parsed.get("suppressions", []):
        fp = entry["fingerprint"]
        reason = entry["reason"]
        if len(reason.strip()) < 10:
            raise GuardConfigError(f"Suppression for {fp} requires reason >= 10 characters.")
        try:
            exp_date = date.fromisoformat(entry["expires"])
        except ValueError as exc:
            raise GuardConfigError(f"Invalid expires date for suppression {fp}: {entry['expires']}") from exc
        if exp_date > max_expiry:
            raise GuardConfigError(
                f"Suppression for {fp} expires {exp_date}, exceeding max {MAX_SUPPRESSION_DAYS} days from today."
            )
        if exp_date < cur_date:
            expired_supps.append(fp)
        else:
            active_supps[fp] = reason

    paths_cfg = parsed.get("paths") or {}
    policy_cfg = parsed.get("policy") or {}
    thresh_cfg = policy_cfg.get("thresholds") or {}
    hook_cfg = parsed.get("hook") or {}
    checks_cfg = parsed.get("checks") or {}

    thresholds = PolicyThresholds(
        min_removed=thresh_cfg.get("min_removed", 3),
        suppression_burst=thresh_cfg.get("suppression_burst", 5),
        megacommit_lines=thresh_cfg.get("megacommit_lines", 800),
        megacommit_files=thresh_cfg.get("megacommit_files", 40),
    )

    return GuardConfig(
        version=parsed.get("version", 1),
        project_license=parsed.get("project_license"),
        ignore_paths=list(paths_cfg.get("ignore", ["vendor/**", "dist/**"])),
        test_globs=list(paths_cfg.get("test_globs", [])),
        fail_on=policy_cfg.get("fail_on", "high"),
        protect_policy=bool(policy_cfg.get("protect_policy", True)),
        thresholds=thresholds,
        block_on=list(hook_cfg.get("block_on", DEFAULT_BLOCK_ON)),
        advisories=checks_cfg.get("advisories", "warn"),
        licenses=checks_cfg.get("licenses", "warn"),
        active_suppressions=active_supps,
        expired_suppressions=expired_supps,
        source=source,
    )


def load_config_from_file(path: Optional[Path] = None, repo_root: Optional[Path] = None) -> GuardConfig:
    target = path or ((repo_root or Path.cwd()) / ".codit.yml")
    if not target.exists():
        return GuardConfig(source="default")
    return parse_config_yaml(target.read_text(encoding="utf-8-sig"), source="working")
