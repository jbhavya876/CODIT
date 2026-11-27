"""Versioned scoring rubric definitions (`1.0.0` legacy immutable + `2.0.0` pivot)."""

from __future__ import annotations

from decimal import Decimal
from typing import Dict

RUBRIC_VERSION = "2.0.0"

RUBRIC_1_0_0 = {
    "version": "1.0.0",
    "severity_deductions": {
        "critical": 35,
        "high": 18,
        "medium": 8,
        "low": 3,
        "info": 0,
    },
    "weights": {
        "security": 0.35,
        "tests": 0.25,
        "scalability": 0.20,
        "duplication": 0.10,
        "maintainability": 0.10,
    },
    "security_critical_cap": 25,
}

WEIGHTS_2_0_0_DECIMAL: Dict[str, Decimal] = {
    "security": Decimal("0.30"),
    "tests": Decimal("0.20"),
    "agent_integrity": Decimal("0.15"),
    "scalability": Decimal("0.12"),
    "licenses": Decimal("0.10"),
    "duplication": Decimal("0.07"),
    "maintainability": Decimal("0.06"),
}

assert sum(WEIGHTS_2_0_0_DECIMAL.values()) == Decimal("1.00"), "Rubric 2.0.0 weights must sum exactly to 1.00"

RUBRIC_2_0_0 = {
    "version": "2.0.0",
    "dimensions_order": (
        "security",
        "tests",
        "agent_integrity",
        "scalability",
        "licenses",
        "duplication",
        "maintainability",
    ),
    "existing_dimensions": frozenset({"security", "tests", "scalability", "duplication", "maintainability"}),
    "new_dimensions": frozenset({"agent_integrity", "licenses"}),
    "severity_deductions": {
        "critical": 35,
        "high": 18,
        "medium": 8,
        "low": 3,
        "info": 0,
    },
    "confidence_multipliers": {
        "high": 1.0,
        "medium": 0.75,
        "low": 0.5,
    },
    "weights": {k: float(v) for k, v in WEIGHTS_2_0_0_DECIMAL.items()},
    "caps": {
        "security_critical": 25,
        "licenses_critical": 30,
        "licenses_high": 70,
        "agent_integrity_recent_90d": 60,
        "agent_integrity_three_commits_90d": 40,
    },
    "phase_thresholds": {
        "Production-track": {
            "overall": 80,
            "security": 75,
            "tests": 70,
            "agent_integrity": 60,
            "licenses": 60,
            "requires_all_assessed_or_na": True,
            "requires_no_critical": True,
        },
        "MVP": {
            "overall": 55,
            "security": 50,
            "requires_no_critical": True,
        },
    },
    "blocker_codes": (
        "critical_security",
        "copyleft_conflict",
        "history_secret_unrotated",
        "high_confidence_test_integrity_event",
    ),
    "qualifier_descriptions": {
        "process_integrity_not_assessed": "Process integrity (agent history) was not assessed; Production-track requires git history assessment.",
        "license_coverage_partial": "Fewer than 90% of production dependencies had resolved licenses; Production-track requires >= 90% license coverage.",
        "license_coverage_missing": "Dependency license resolution data was unavailable for this audit.",
        "history_partial": "Git history inspection hit depth, commit, or shallow-clone boundaries.",
        "licenses_not_applicable": "Repository declared no pinned or unpinned package dependencies; license dimension marked not applicable.",
    },
}
