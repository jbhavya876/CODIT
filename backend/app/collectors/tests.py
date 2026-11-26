"""
Tests Audit Collector:
Evaluates test file ratios, test framework configurations, and test suite health.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Set

from codit_core.classify import is_test_file  # noqa: F401 - extracted to codit_core
from codit_core.fingerprint import compute_fingerprint

from backend.app.collectors.models import AuditFinding
from backend.app.ingestion.models import FileEntry

log = logging.getLogger(__name__)

TEST_FRAMEWORK_CONFIGS = {
    "pytest.ini",
    "setup.cfg",
    "tox.ini",
    ".pytest.ini",
    "jest.config.js",
    "jest.config.ts",
    "jest.config.mjs",
    "vitest.config.ts",
    "vitest.config.js",
    ".mocharc.json",
    ".mocharc.yml",
    "cypress.config.js",
    "cypress.config.ts",
}

CRITICAL_MODULE_KEYWORDS = {"auth", "payment", "crypto", "database", "order", "security", "token"}


def run_tests_collector(files: List[FileEntry]) -> List[AuditFinding]:
    """
    Evaluates test presence, ratio, and framework configuration across the codebase.
    """
    findings: List[AuditFinding] = []

    source_files: List[FileEntry] = []
    test_files: List[FileEntry] = []
    config_files: List[FileEntry] = []

    primary_manifest = "package.json"

    for f in files:
        fname = Path(f.path).name.lower()
        if fname in ("package.json", "pyproject.toml", "requirements.txt"):
            primary_manifest = f.path

        if fname in TEST_FRAMEWORK_CONFIGS:
            config_files.append(f)

        if is_test_file(f.path):
            test_files.append(f)
        elif f.language in ("python", "javascript", "typescript"):
            source_files.append(f)

    # 1. Check for absence of test framework configuration
    if not config_files:
        has_test_script_in_manifest = False
        for f in files:
            if "package.json" in f.path.lower() and '"test"' in f.content:
                has_test_script_in_manifest = True
                break

        if not has_test_script_in_manifest:
            fp = compute_fingerprint("TEST_FRAMEWORK_MISSING", primary_manifest, "no_test_config")
            findings.append(AuditFinding(
                id=f"test-no-config-{fp[:8]}",
                dimension="tests",
                severity="medium",
                confidence="high",
                description="No automated test configuration detected (missing pytest.ini, jest.config, or test script).",
                evidence_file=primary_manifest,
                evidence_line=1,
                rule_id="TEST_FRAMEWORK_MISSING",
                remediation="Configure a test framework runner (e.g. pytest or Vitest/Jest) and add test targets to CI.",
                fingerprint=fp,
                basis="AST PROOF",
            ))

    # 2. Check test file ratio
    source_count = len(source_files)
    test_count = len(test_files)
    ratio = test_count / max(source_count, 1)

    if test_count == 0 and source_count > 0:
        fp = compute_fingerprint("TEST_ZERO_COVERAGE", primary_manifest, "zero_test_files")
        findings.append(AuditFinding(
            id=f"test-zero-coverage-{fp[:8]}",
            dimension="tests",
            severity="high",
            confidence="high",
            description=f"Zero automated test files detected across {source_count} application source files.",
            evidence_file=primary_manifest,
            evidence_line=1,
            rule_id="TEST_ZERO_COVERAGE",
            remediation="Establish a baseline unit test suite for critical application workflows.",
            fingerprint=fp,
            basis="AST PROOF",
        ))
    elif ratio < 0.20 and source_count >= 5:
        fp = compute_fingerprint("TEST_LOW_RATIO", primary_manifest, "low_test_ratio")
        findings.append(AuditFinding(
            id=f"test-low-ratio-{fp[:8]}",
            dimension="tests",
            severity="medium",
            confidence="high",
            description=f"Low test coverage ratio: {test_count} test files for {source_count} source files ({ratio:.1%}).",
            evidence_file=primary_manifest,
            evidence_line=1,
            rule_id="TEST_LOW_RATIO",
            remediation="Increase unit and integration test coverage to at least 1 test file per 3 production modules.",
            fingerprint=fp,
            basis="AST PROOF",
        ))

    # 3. Check for untested critical business logic modules
    test_stems: Set[str] = {
        Path(t.path).stem.lower().replace("test_", "").replace("_test", "").replace(".test", "").replace(".spec", "")
        for t in test_files
    }

    for sf in source_files:
        p_lower = sf.path.lower()
        fname = Path(sf.path).name
        stem = Path(sf.path).stem.lower()

        is_critical = any(kw in p_lower for kw in CRITICAL_MODULE_KEYWORDS)
        has_tests = stem in test_stems or any(stem in t for t in test_stems)

        if is_critical and not has_tests and sf.size > 200:
            fp = compute_fingerprint("TEST_UNTESTED_CRITICAL", sf.path, fname)
            findings.append(AuditFinding(
                id=f"test-untested-critical-{fp[:8]}",
                dimension="tests",
                severity="medium",
                confidence="medium",
                description=f"High-impact module '{fname}' contains critical business logic but lacks corresponding test coverage.",
                evidence_file=sf.path,
                evidence_line=1,
                rule_id="TEST_UNTESTED_CRITICAL",
                remediation=f"Add targeted unit tests for {sf.path} validating edge cases and failure scenarios.",
                component_id=sf.path,
                fingerprint=fp,
                basis="GRAPH HEUR",
            ))

    return findings
