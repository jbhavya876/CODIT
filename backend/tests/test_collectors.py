"""
Tests for Module 5 (Audit Signal Collectors) and Module 6a (Deterministic Scoring).
"""

from __future__ import annotations

import pytest

from backend.app.collectors import run_all_collectors
from backend.app.collectors.duplication import detect_code_duplication
from backend.app.collectors.models import AuditFinding
from backend.app.collectors.scalability import detect_scalability_antipatterns
from backend.app.collectors.security import run_security_collector, scan_for_committed_secrets
from backend.app.collectors.tests import run_tests_collector
from backend.app.ingestion.models import FileEntry
from backend.app.parsers.models import DependencyEntry
from backend.app.scoring.rules_engine import score_audit


def test_osv_vulnerability_flags_cve():
    """Verify that a dependency with a known CVE is correctly flagged with CVE identifier."""
    deps = [
        DependencyEntry(
            name="lodash",
            raw_version="4.17.15",
            normalized_version="4.17.15",
            ecosystem="npm",
            dep_type="dependency",
            evidence_file="package.json",
            evidence_line=10,
        )
    ]
    findings = run_security_collector(files=[], dependencies=deps)
    cve_findings = [f for f in findings if "CVE-2020-8203" in f.rule_id or "CVE-2020-8203" in f.description]
    assert len(cve_findings) >= 1
    f = cve_findings[0]
    assert f.dimension == "security"
    assert f.severity in ("critical", "high")
    assert f.evidence_file == "package.json"
    assert f.evidence_line == 10
    assert f.confidence == "high"


def test_planted_credential_is_caught():
    """Verify that deliberately planted API keys / credentials are caught with line attribution."""
    planted_content = """# Config settings
API_HOST = "api.prod.company.com"
AWS_ACCESS_KEY_ID = "your_aws_key_here"
STRIPE_SECRET_KEY = "your_stripe_test_key_here"
"""
    files = [
        FileEntry(path="src/config.py", size=len(planted_content), language="python", content=planted_content),
    ]

    findings = scan_for_committed_secrets(files)
    assert len(findings) >= 2

    rule_ids = {f.rule_id for f in findings}
    assert "SECRET_AWS_KEY" in rule_ids
    assert "SECRET_STRIPE_SECRET" in rule_ids

    for f in findings:
        assert f.evidence_file == "src/config.py"
        assert f.evidence_line in (3, 4)
        assert f.severity == "critical"


def test_code_duplication_block_is_caught():
    """Verify that a deliberately duplicated code block across two files is detected."""
    dup_block = """    let total = 0;
    for (let i = 0; i < items.length; i++) {
        total += items[i].price * items[i].quantity;
        total -= items[i].discount;
    }
    return total;"""

    file1 = f"function calculateCart(items) {{\n{dup_block}\n}}\nmodule.exports = {{ calculateCart }};"
    file2 = f"function calculateInvoice(items) {{\n{dup_block}\n}}\nmodule.exports = {{ calculateInvoice }};"

    files = [
        FileEntry(path="src/cart.js", size=len(file1), language="javascript", content=file1),
        FileEntry(path="src/invoice.js", size=len(file2), language="javascript", content=file2),
    ]

    findings = detect_code_duplication(files)
    assert len(findings) >= 1
    f = findings[0]
    assert f.dimension == "duplication"
    assert f.evidence_file in ("src/cart.js", "src/invoice.js")
    assert f.evidence_line is not None


def test_scalability_n_plus_1_and_sync_in_async():
    """Verify detection of N+1 loop queries and sync blocking calls in async def."""
    async_code = """import requests

async def get_user_dashboard(user_ids, db):
    # Blocking call in async path
    raw_info = requests.get("https://auth.internal/info")
    
    results = []
    for uid in user_ids:
        # N+1 query pattern inside loop
        data = db.query(f"SELECT * FROM users WHERE id = {uid}")
        results.append(data)
    return results
"""
    files = [
        FileEntry(path="backend/routes.py", size=len(async_code), language="python", content=async_code),
    ]

    findings = detect_scalability_antipatterns(files, {})
    rule_ids = {f.rule_id for f in findings}

    assert "SYNC_IN_ASYNC_PATH" in rule_ids
    assert "N_PLUS_ONE_QUERY_SHAPE" in rule_ids

    for f in findings:
        assert f.dimension == "scalability"
        assert f.evidence_file == "backend/routes.py"
        assert f.evidence_line is not None


def test_collectors_fault_isolation_and_evidence_integrity():
    """Verify that every finding has non-null evidence and collectors run with fault isolation."""
    files = [
        FileEntry(path="app.py", size=50, language="python", content="print('hello')"),
    ]
    findings = run_all_collectors(files, [], {})
    for f in findings:
        assert f.evidence_file is not None
        assert len(f.evidence_file) > 0
        assert f.confidence in ("high", "medium", "low")


def test_deterministic_scoring_and_critical_security_cap():
    """
    Verify:
    1. Scoring is strictly deterministic (same findings -> exact same scores).
    2. A critical vulnerability or leaked credential caps security score at <= 25.
    """
    clean_findings = [
        AuditFinding(
            id="test-1",
            dimension="tests",
            severity="low",
            confidence="high",
            description="Minor test notice",
            evidence_file="tests/test_app.py",
            evidence_line=1,
        )
    ]

    scorecard1 = score_audit(clean_findings)
    scorecard2 = score_audit(clean_findings)

    # Determinism
    assert scorecard1.overall_score == scorecard2.overall_score
    assert scorecard1.phase == scorecard2.phase
    assert scorecard1.dimensions["security"].score == 100
    assert scorecard1.phase == "Production-track"

    # Now add a critical leaked credential
    compromised_findings = list(clean_findings) + [
        AuditFinding(
            id="crit-sec-1",
            dimension="security",
            severity="critical",
            confidence="high",
            description="Leaked AWS Access Key",
            evidence_file="config.py",
            evidence_line=5,
        )
    ]

    compromised_scorecard = score_audit(compromised_findings)
    # Hard cap rule: security score MUST NOT exceed 25!
    assert compromised_scorecard.dimensions["security"].score <= 25
    # Phase must be capped at Prototype
    assert compromised_scorecard.phase == "Prototype"
    assert compromised_scorecard.has_critical_blocker is True
