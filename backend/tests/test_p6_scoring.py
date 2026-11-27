"""P6 Scoring v2 & Effort Model tests (Gate G6)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import itertools
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from scripts.gen_rubric_doc import render_rubric_markdown

from backend.app import create_app
from backend.app.collectors.models import AuditFinding
from backend.app.db.engine import session_scope
from backend.app.db.models import AuditRow
from backend.app.scoring.effort_model import compute_effort_estimate
from backend.app.scoring.rubric import WEIGHTS_2_0_0_DECIMAL
from backend.app.scoring.rules_engine import score_audit
from backend.app.scoring.rules_engine_v2 import round_half_up, score_audit_v2
from backend.app.services.audit_service import create_audit, get_report_for_audit


def test_weights_sum_to_one_point_zero():
    assert sum(WEIGHTS_2_0_0_DECIMAL.values()) == Decimal("1.00")


def test_half_up_rounding_table():
    assert round_half_up(0.0) == 0
    assert round_half_up(0.5) == 1
    assert round_half_up(2.5) == 3  # Python round(2.5) would be 2 (banker's rounding)
    assert round_half_up(3.5) == 4
    assert round_half_up(84.499) == 84
    assert round_half_up(84.500) == 85


def test_v1_scoring_unchanged_and_confidence_unscaled_on_existing_dims():
    findings = [
        AuditFinding(
            id="s1",
            dimension="security",
            severity="medium",
            confidence="low",
            description="Low-confidence security finding",
            evidence_file="a.py",
            evidence_line=1,
            rule_id="SEC-1",
        ),
        AuditFinding(
            id="a1",
            dimension="agent_integrity",
            severity="high",
            confidence="medium",
            description="Medium-confidence AGT-004 finding",
            evidence_file="a.py",
            evidence_line=2,
            rule_id="AGT-004",
        ),
    ]
    v1 = score_audit(findings)
    assert v1.dimensions["security"].score == 92  # 100 - 8 (unscaled)
    assert v1.overall_score == 97  # 100 - 0.35*8 = 97.2 -> 97

    cov = {
        "history": {"assessed": True},
        "licenses": {"not_applicable": True, "total": 0, "prod_total": 0, "prod_resolved_pct": 100},
    }
    v2 = score_audit_v2(findings, coverage=cov)
    # Existing dimension unscaled (`security` == 92); new dimension scaled (`high` 18 * 0.75 = 13.5 -> 86.5 -> 87)
    assert v2.dimensions["security"].score == 92
    assert v2.dimensions["agent_integrity"].score == 87
    # Determinism check
    assert v2.to_v2_dict() == score_audit_v2(findings, coverage=cov).to_v2_dict()


def test_golden_scorecards_caps_and_blockers():
    now = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
    process_data = {
        "commits": [
            {"sha": "c1" * 20, "date": (now - timedelta(days=5)).isoformat()},
            {"sha": "c2" * 20, "date": (now - timedelta(days=15)).isoformat()},
            {"sha": "c3" * 20, "date": (now - timedelta(days=25)).isoformat()},
        ]
    }
    cov_full = {
        "history": {"assessed": True},
        "licenses": {"not_applicable": False, "total": 10, "prod_total": 10, "prod_resolved_pct": 100},
    }

    # 1. Single high-conf high-sev AGT within 90d caps agent_integrity <= 60
    one_recent = [
        AuditFinding(
            id="agt1",
            dimension="agent_integrity",
            severity="high",
            confidence="high",
            description="Deleted tests",
            evidence_file="tests/test_a.py",
            evidence_line=1,
            rule_id="AGT-001",
            commit_sha="c1" * 20,
        )
    ]
    sc_one = score_audit_v2(one_recent, coverage=cov_full, process_data=process_data)
    assert sc_one.dimensions["agent_integrity"].score <= 60
    assert "high_confidence_test_integrity_event" in sc_one.blockers

    # 2. Three distinct commits with high-conf high-sev AGT caps agent_integrity <= 40
    three_recent = [
        AuditFinding(
            id=f"agt-{i}",
            dimension="agent_integrity",
            severity="high",
            confidence="high",
            description="Deleted tests",
            evidence_file="tests/test_a.py",
            evidence_line=1,
            rule_id="AGT-001",
            commit_sha=sha,
        )
        for i, sha in enumerate(("c1" * 20, "c2" * 20, "c3" * 20))
    ]
    sc_three = score_audit_v2(three_recent, coverage=cov_full, process_data=process_data)
    assert sc_three.dimensions["agent_integrity"].score <= 40

    # 3. License caps + AGT-010 secret blocker
    lic_crit = [
        AuditFinding(
            id="lic1",
            dimension="licenses",
            severity="critical",
            confidence="high",
            description="AGPL dep",
            evidence_file="package-lock.json",
            evidence_line=4,
            rule_id="LIC-002",
        ),
        AuditFinding(
            id="agt10",
            dimension="security",
            severity="critical",
            confidence="high",
            description="Secret in history",
            evidence_file="src/cfg.py",
            evidence_line=3,
            rule_id="AGT-010",
        ),
    ]
    sc_lic = score_audit_v2(lic_crit, coverage=cov_full, process_data=process_data)
    assert sc_lic.dimensions["licenses"].score <= 30
    assert sc_lic.dimensions["security"].score <= 25
    assert set(["critical_security", "copyleft_conflict", "history_secret_unrotated"]).issubset(set(sc_lic.blockers))
    assert sc_lic.phase == "Prototype"


def test_exhaustive_not_assessed_never_yields_production_track():
    """Exhaustively test history & license availability combinations with zero findings."""
    history_states = [
        {"assessed": False, "reason": "zip_without_git"},
        {"assessed": False, "reason": "disabled"},
        {"assessed": True},
    ]
    license_states = [
        {},  # missing
        {"not_applicable": False, "total": 10, "prod_total": 10, "prod_resolved_pct": 89},
        {"not_applicable": False, "total": 10, "prod_total": 10, "prod_resolved_pct": 90},
        {"not_applicable": True, "total": 0, "prod_total": 0, "prod_resolved_pct": 100},
    ]

    for h_cov, l_cov in itertools.product(history_states, license_states):
        sc = score_audit_v2([], coverage={"history": h_cov, "licenses": l_cov})
        hist_ok = bool(h_cov.get("assessed"))
        lic_ok = bool(l_cov) and (
            bool(l_cov.get("not_applicable")) or int(l_cov.get("prod_resolved_pct", 100)) >= 90
        )
        if hist_ok and lic_ok:
            assert sc.phase == "Production-track"
        else:
            assert sc.phase != "Production-track"
            assert sc.overall_score == 100  # zero findings renormalized over assessed dims, yet gated!


def test_effort_model_hand_computed_three_fixtures_and_hourly_rate():
    # Fixture 1: 1 SEC secret (2/4/8h) + 1 CVE (1/2/6h) -> hours 3/6/14, days 0.38/0.75/1.75
    f1 = [
        AuditFinding("1", "security", "critical", "high", "sec", "a.py", 1, "SECRET_AWS_KEY"),
        AuditFinding("2", "security", "high", "high", "cve", "package.json", 5, "CVE-2020-8203"),
    ]
    e1 = compute_effort_estimate(f1)
    assert e1["hours"] == {"min": 3.0, "likely": 6.0, "max": 14.0}
    assert e1["person_days"] == {"min": 0.38, "likely": 0.75, "max": 1.75}
    assert "monetary_range" not in e1

    # Fixture 2: AGT-001 (2/4/12h) + LIC-002 (8/24/120h) with hourly_rate=100
    f2 = [
        AuditFinding("3", "agent_integrity", "high", "high", "agt", "tests/a.py", 1, "AGT-001"),
        AuditFinding("4", "licenses", "critical", "high", "lic", "package-lock.json", 2, "LIC-002"),
    ]
    e2 = compute_effort_estimate(f2, hourly_rate=100)
    assert e2["hours"] == {"min": 10.0, "likely": 28.0, "max": 132.0}
    assert e2["person_days"] == {"min": 1.25, "likely": 3.5, "max": 16.5}
    assert e2["monetary_range"] == {
        "min": 1000.0,
        "likely": 2800.0,
        "max": 13200.0,
        "rate_supplied": 100.0,
        "unit": "per hour, same currency as supplied",
    }

    # Fixture 3: Unknown rule medium fallback (2/6/16h) + AGT-012 (0.25/0.5/1h)
    f3 = [
        AuditFinding("5", "scalability", "medium", "high", "n+1", "app.py", 9, "N_PLUS_ONE"),
        AuditFinding("6", "agent_integrity", "medium", "high", "only", "test_x.js", 3, "AGT-012"),
    ]
    e3 = compute_effort_estimate(f3)
    assert e3["hours"] == {"min": 2.25, "likely": 6.5, "max": 17.0}
    assert e3["person_days"] == {"min": 0.28, "likely": 0.81, "max": 2.12}

    # Invalid hourly_rate rejected cleanly
    with pytest.raises(ValueError):
        compute_effort_estimate(f1, hourly_rate=0)
    with pytest.raises(ValueError):
        compute_effort_estimate(f1, hourly_rate=2500)


def test_persisted_v1_audit_never_recomputed_under_v2():
    """An issued 1.0.0 scorecard persisted in DB loads strictly as 1.0.0 without re-scoring."""
    audit_id = create_audit(source_kind="zip", source_ref="legacy-v1-test")
    legacy_sc = score_audit([])
    with session_scope() as session:
        row = session.get(AuditRow, audit_id)
        assert row is not None
        row.status = "completed"
        row.rubric_version = "1.0.0"
        row.scorecard_json = {
            "rubric_version": "1.0.0",
            "overall_score": legacy_sc.overall_score,
            "phase": legacy_sc.phase,
            "has_critical_blocker": legacy_sc.has_critical_blocker,
            "findings_summary": legacy_sc.findings_summary,
            "dimensions": {
                k: {
                    "dimension": v.dimension,
                    "score": v.score,
                    "findings_count": v.findings_count,
                    "critical_count": v.critical_count,
                    "high_count": v.high_count,
                    "medium_count": v.medium_count,
                    "low_count": v.low_count,
                }
                for k, v in legacy_sc.dimensions.items()
            },
        }
        row.report_meta_json = {
            "report_id": "audit-legacy1",
            "access_tier": "premium_zip",
            "created_at": 1700000000.0,
            "roadmap": {"goal": "production", "summary_narrative": "ok", "blockers_summary": "none", "phases": []},
            "architecture_diagram_mermaid": "flowchart TD\n",
            "criticality_leaderboard": [],
            "stats": {},
            "source_deleted": True,
            "ml_insights": {},
        }

    loaded = get_report_for_audit(audit_id)
    assert loaded is not None
    assert loaded.rubric_version == "1.0.0"
    assert set(loaded.scorecard.dimensions.keys()) == {"security", "tests", "scalability", "duplication", "maintainability"}


def test_rubric_docs_drift_and_static_endpoint():
    rubric_md = Path(__file__).resolve().parents[2] / "docs" / "RUBRIC.md"
    assert rubric_md.exists()
    assert rubric_md.read_text(encoding="utf-8") == render_rubric_markdown()

    client = TestClient(create_app({"GRAPH_BACKEND": "demo"}))
    resp = client.get("/rubric/2.0.0")
    assert resp.status_code == 200
    assert "<script" not in resp.text.lower()
    assert "2.0.0" in resp.text
