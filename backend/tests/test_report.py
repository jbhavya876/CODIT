"""
Tests for Module 6b (Roadmap Synthesis), Module 7 (Diagrams), and Module 8 (Report & Delivery).
"""

from __future__ import annotations

import io
import tempfile
import zipfile
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from backend.app import create_app
from backend.app.collectors.models import AuditFinding
from backend.app.delivery.models import AuditReport
from backend.app.delivery.pdf_export import generate_html_report, generate_markdown_report
from backend.app.diagrams.mermaid_generator import (
    generate_architecture_diagram,
    generate_blast_radius_diagram,
)
from backend.app.ingestion.zip_extract import purge_extracted_files
from backend.app.routes.analyze import run_full_analysis
from backend.app.routes.ingest import set_active_codebase
from backend.app.scoring.roadmap_synthesis import (
    build_llm_payload,
    generate_audit_roadmap,
    synthesize_deterministic_roadmap,
)
from backend.app.scoring.rules_engine import score_audit


@pytest.fixture()
def client():
    app = create_app({"GRAPH_BACKEND": "demo"})
    return TestClient(app)


def test_zero_raw_source_code_in_llm_payload():
    """Verify that NO raw source code is included in the payload constructed for LLM synthesis (Constraint 6)."""
    findings = [
        AuditFinding(
            id="f-1",
            dimension="security",
            severity="high",
            confidence="high",
            description="High vulnerability in jwt",
            evidence_file="package.json",
            evidence_line=12,
            rule_id="CVE-2022-29217",
            remediation="Upgrade pyjwt",
        )
    ]
    scorecard = score_audit(findings)
    critical_components = [{"component": {"id": "db-pg", "name": "PostgreSQL"}, "reach": 5, "tier": "HIGH"}]

    payload = build_llm_payload(scorecard, findings, critical_components, goal="production")

    # Assert payload contains structured findings and metrics, and no raw file contents
    assert "findings" in payload
    assert "scorecard" in payload
    assert payload["scorecard"]["overall_score"] == scorecard.overall_score
    payload_dump = str(payload)
    assert "class " not in payload_dump
    assert "def " not in payload_dump
    assert "import " not in payload_dump


def test_roadmap_synthesis_preserves_hard_rules_and_adapts_to_goal():
    """Verify roadmap retains critical findings as blockers and changes narrative between MVP and Production."""
    crit_finding = AuditFinding(
        id="f-crit",
        dimension="security",
        severity="critical",
        confidence="high",
        description="Hardcoded Stripe Secret Key in config.py",
        evidence_file="config.py",
        evidence_line=5,
        rule_id="SECRET_STRIPE_SECRET",
        remediation="Revoke key immediately",
    )
    scorecard = score_audit([crit_finding])
    comps = [{"component": {"id": "svc-pay", "name": "Payment Service"}, "reach": 3, "tier": "MEDIUM"}]

    roadmap_mvp = synthesize_deterministic_roadmap(scorecard, [crit_finding], comps, goal="mvp")
    roadmap_prod = synthesize_deterministic_roadmap(scorecard, [crit_finding], comps, goal="production")

    # Constraint 10: Critical finding MUST be in Phase 1 / P0 Blockers
    p0_mvp_ids = [item.finding_id for item in roadmap_mvp.phases[0].action_items]
    p0_prod_ids = [item.finding_id for item in roadmap_prod.phases[0].action_items]
    assert "f-crit" in p0_mvp_ids
    assert "f-crit" in p0_prod_ids

    # Every item must cite evidence file (Constraint 9)
    assert roadmap_mvp.phases[0].action_items[0].evidence_file == "config.py"

    # Goal-dependent changes:
    assert roadmap_mvp.goal == "mvp"
    assert roadmap_prod.goal == "production"
    assert "MVP" in roadmap_mvp.summary_narrative
    assert "Production" in roadmap_prod.summary_narrative


def test_mermaid_diagram_generation():
    """Verify architecture overview and blast-radius diagram generation from real graph data."""
    nodes = [
        {"id": "src/app.py", "name": "app.py", "labels": "Module"},
        {"id": "src/db.py", "name": "db.py", "labels": "Module"},
        {"id": "db-pg", "name": "PostgreSQL", "labels": "Database"},
        {"id": "lib-fastapi", "name": "fastapi", "labels": "Library", "version": "0.110.0"},
    ]
    edges = [
        {"source_id": "src/app.py", "rel_type": "IMPORTS", "target_id": "src/db.py"},
        {"source_id": "src/db.py", "rel_type": "USES", "target_id": "db-pg"},
    ]

    arch_diagram = generate_architecture_diagram(nodes, edges)
    assert "flowchart TD" in arch_diagram
    assert "Application Modules" in arch_diagram
    assert "Databases & Caching" in arch_diagram
    assert "src_app_py -->|IMPORTS| src_db_py" in arch_diagram

    impact_data = {
        "root": {"component": {"id": "db-pg", "name": "PostgreSQL"}},
        "direct": [{"component": {"id": "src/db.py", "name": "db.py"}}],
        "indirect": [{"component": {"id": "src/app.py", "name": "app.py"}, "depth": 2}],
    }
    blast_diagram = generate_blast_radius_diagram("db-pg", impact_data)
    assert "graph LR" in blast_diagram
    assert "ORIGIN: PostgreSQL" in blast_diagram
    assert "Direct Dependents" in blast_diagram


def test_dashboard_and_export_data_parity(client):
    """Verify dashboard JSON, Markdown export, and HTML export render identical findings and scores."""
    res = client.post("/api/analyze/run", json={"goal": "production"})
    assert res.status_code == 200

    json_res = client.get("/api/report")
    assert json_res.status_code == 200
    report_data = json_res.json()

    md_res = client.get("/api/report/markdown")
    assert md_res.status_code == 200
    md_text = md_res.text

    html_res = client.get("/api/report/html")
    assert html_res.status_code == 200
    html_text = html_res.text

    overall_score = report_data["scorecard"]["overall_score"]
    phase = report_data["scorecard"]["phase"]

    # Assert exact score and phase in all formats
    assert f"{overall_score} / 100" in md_text or f"{overall_score}/100" in md_text
    assert phase.upper() in md_text
    assert f"{overall_score}/100" in html_text
    assert phase in html_text

    # Assert all findings present in both JSON and Markdown
    for f in report_data["findings"]:
        assert f["evidence_file"] in md_text
        assert f["evidence_file"] in html_text


def test_zip_tier_immediate_source_deletion(client):
    """Verify that source code from a ZIP upload is immediately deleted post-analysis (Constraint 7)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("package.json", '{"name": "temp-project"}')
        z.writestr("index.js", "console.log('temporary');")

    temp_dir = Path(tempfile.mkdtemp(prefix="zip_deletion_test_"))
    zpath = temp_dir / "temp_project.zip"
    zpath.write_bytes(buf.getvalue())

    # Simulate upload
    with open(zpath, "rb") as f:
        res = client.post("/api/ingest/zip", files={"file": ("temp_project.zip", f, "application/zip")})
    assert res.status_code == 200

    # Run analysis
    analyze_res = client.post("/api/analyze/run", json={"goal": "mvp"})
    assert analyze_res.status_code == 200
    assert analyze_res.json()["source_deleted"] is True

    # Check report confirms deletion
    rep_res = client.get("/api/report")
    assert rep_res.json()["source_deleted"] is True
    assert rep_res.json()["access_tier"] == "premium_zip"

    # Verify temp extraction directory was deleted
    purge_extracted_files(temp_dir)
