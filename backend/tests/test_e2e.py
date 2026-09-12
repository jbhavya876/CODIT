"""End-to-end integration tests for Codebase Audit Platform."""

import io
import json
from pathlib import Path
import sys
import zipfile

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root

from backend.app import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


def create_sample_zip() -> bytes:
    """Create an in-memory ZIP of a sample Node/Python app."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # package.json
        zf.writestr(
            "package.json",
            json.dumps({
                "name": "sample-microservice",
                "version": "1.0.0",
                "dependencies": {"express": "^4.18.2"},
                "devDependencies": {"jest": "^29.5.0"}
            })
        )
        # index.js
        zf.writestr(
            "src/index.js",
            """
            const express = require('express');
            const auth = require('./auth');
            const app = express();
            app.get('/api', (req, res) => res.send('OK'));
            app.listen(3000);
            """
        )
        # auth.js
        zf.writestr(
            "src/auth.js",
            """
            function authenticate(token) {
                return token === 'secret';
            }
            module.exports = { authenticate };
            """
        )
        # test file
        zf.writestr(
            "tests/auth.test.js",
            """
            const { authenticate } = require('../src/auth');
            test('auth', () => {
                expect(authenticate('secret')).toBe(true);
            });
            """
        )
    return buf.getvalue()


def test_static_frontend_serving(client):
    """Test that FastAPI correctly serves index.html and SPA routes."""
    res = client.get("/")
    assert res.status_code == 200
    assert "<!doctype html>" in res.text.lower() or "<html" in res.text.lower()

    # Any non-API route should serve index.html (SPA routing)
    res_spa = client.get("/audit/test-job-123")
    assert res_spa.status_code == 200
    assert "<!doctype html>" in res_spa.text.lower() or "<html" in res_spa.text.lower()


def test_full_pipeline_zip_ingest_analyze_report(client):
    """Test complete pipeline from ZIP upload to analyze to report retrieval."""
    zip_bytes = create_sample_zip()

    # 1. Ingest ZIP
    ingest_res = client.post(
        "/api/ingest/zip",
        files={"file": ("sample.zip", zip_bytes, "application/zip")},
    )
    assert ingest_res.status_code == 200
    data = ingest_res.json()
    assert data["status"] == "ok"
    assert data["file_count"] >= 3

    # 2. Trigger analysis via POST /api/analyze/run
    analyze_res = client.post(
        "/api/analyze/run",
        json={"goal": "production"}
    )
    assert analyze_res.status_code == 200
    analyze_data = analyze_res.json()
    assert analyze_data["status"] == "ok"
    report_id = analyze_data["report_id"]
    assert report_id
    assert analyze_data["score"] > 0
    assert analyze_data["phase"] in ["Prototype", "MVP", "Production-track"]
    assert analyze_data["source_deleted"] is True

    # 3. Retrieve report via GET /api/report
    get_report_res = client.get("/api/report")
    assert get_report_res.status_code == 200
    fetched_report = get_report_res.json()
    assert fetched_report["report_id"] == report_id
    assert fetched_report["scorecard"]["overall_score"] == analyze_data["score"]
    assert len(fetched_report["roadmap"]["phases"]) > 0
    assert "flowchart" in fetched_report["architecture_diagram_mermaid"] or "graph" in fetched_report["architecture_diagram_mermaid"]

    # 4. Retrieve Markdown export
    md_res = client.get("/api/report/markdown")
    assert md_res.status_code == 200
    assert "Audit Report" in md_res.text
    assert f"{analyze_data['score']} / 100" in md_res.text

    # 5. Retrieve HTML/PDF export
    html_res = client.get("/api/report/html")
    assert html_res.status_code == 200
    assert "<!DOCTYPE html>" in html_res.text
    assert f"{analyze_data['score']}/100" in html_res.text

    # 6. Test component blast radius diagram endpoint
    diagram_res = client.get("/api/report/diagram/impact/sample-microservice")
    assert diagram_res.status_code == 200
    diagram_data = diagram_res.json()
    assert "mermaid" in diagram_data
    assert "flowchart" in diagram_data["mermaid"] or "graph" in diagram_data["mermaid"]
