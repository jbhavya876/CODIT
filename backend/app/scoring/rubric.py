"""Versioned scoring rubric definitions (v1.0.0 scaffold; v2.0.0 added in P6)."""

from __future__ import annotations

RUBRIC_VERSION = "1.0.0"

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
