"""
P0 Foundation tests (Gate G1):
- Zero module-level _ACTIVE* globals under backend/app
- Pure boundary enforcement on packages/codit_core
- Concurrent audit isolation (reports, graphs, findings)
- Stale job reaper (interrupted) & retention reaper (expired + staging + attestation FK null)
- Stable finding fingerprints across whitespace & line shifts
- Production SQLite refusal & graph_json 5 MB truncation cap
"""

from __future__ import annotations

import ast
import io
import json
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from codit_core.classify import is_test_file
from codit_core.fingerprint import compute_fingerprint
from codit_core.secrets import scan_text

from backend.app import create_app
from backend.app.config import Config
from backend.app.db.engine import init_db, resolve_database_url, session_scope
from backend.app.db.models import AttestationRow, AuditRow
from backend.app.jobs.runner import reap_expired_audits, reap_stale_running_jobs
from backend.app.services import audit_service, graph_service
from backend.app.services.demo_graph import serialize_graph


def _make_zip(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, content in files.items():
            zf.writestr(path, content)
    return buf.getvalue()


def test_no_module_level_active_globals_in_backend_app():
    """Static check: no module under backend/app may assign to module-level _ACTIVE* names."""
    app_dir = Path(__file__).resolve().parents[1] / "app"
    offenders: list[str] = []
    for py_file in app_dir.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8-sig"), filename=str(py_file))
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for tgt in node.targets:
                    if isinstance(tgt, ast.Name) and tgt.id.startswith("_ACTIVE"):
                        offenders.append(f"{py_file}:{node.lineno}:{tgt.id}")
            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name) and node.target.id.startswith("_ACTIVE"):
                    offenders.append(f"{py_file}:{node.lineno}:{node.target.id}")
    assert not offenders, f"Forbidden module-level _ACTIVE globals found: {offenders}"


def test_codit_core_purity_no_forbidden_imports():
    """codit_core must contain zero FastAPI, DB, network, LLM, or subprocess imports."""
    forbidden = {
        "fastapi",
        "starlette",
        "sqlalchemy",
        "psycopg",
        "neo4j",
        "httpx",
        "requests",
        "urllib.request",
        "socket",
        "anthropic",
        "subprocess",
        "onnxruntime",
        "shap",
    }
    core_dir = Path(__file__).resolve().parents[2] / "packages" / "codit_core" / "src" / "codit_core"
    violations: list[str] = []
    for py_file in core_dir.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root in forbidden or alias.name in forbidden:
                        violations.append(f"{py_file}:{alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                root = node.module.split(".")[0]
                if root in forbidden or node.module in forbidden:
                    violations.append(f"{py_file}:{node.module}")
    assert not violations, f"Forbidden imports in codit_core: {violations}"


def test_concurrent_audits_fully_isolated():
    """Two concurrent TestClient sessions produce isolated reports, graphs, and findings."""
    app = create_app({"GRAPH_BACKEND": "demo"})

    zip_alpha = _make_zip({
        "package.json": json.dumps({"name": "alpha-service", "version": "1.0.0", "dependencies": {"express": "4.18.2"}}),
        "src/alpha_unique.js": "const express = require('express');\nmodule.exports = {};\n",
        "tests/alpha_unique.test.js": "test('ok', () => { expect(1).toBe(1); });\n",
    })
    fake_aws = "AKIA" + "0123456789ABCDEF"
    zip_beta = _make_zip({
        "requirements.txt": "fastapi==0.110.0\n",
        "beta_secret_mod.py": f'AWS_KEY = "{fake_aws}"\n',
    })

    def run_flow(name: str, payload: bytes) -> tuple[dict, list]:
        c = TestClient(app)
        r_ing = c.post("/api/ingest/zip", files={"file": (f"{name}.zip", payload, "application/zip")})
        assert r_ing.status_code == 200
        r_ana = c.post("/api/analyze/run", json={"goal": "production"})
        assert r_ana.status_code == 200
        rep = c.get("/api/report")
        assert rep.status_code == 200
        comps = c.get("/api/components?limit=50")
        assert comps.status_code == 200
        return rep.json(), comps.json()

    with ThreadPoolExecutor(max_workers=2) as ex:
        fut_a = ex.submit(run_flow, "alpha", zip_alpha)
        fut_b = ex.submit(run_flow, "beta", zip_beta)
        rep_a, comps_a = fut_a.result()
        rep_b, comps_b = fut_b.result()

    assert rep_a["audit_id"] != rep_b["audit_id"]
    assert rep_a["target_name"] == "alpha.zip"
    assert rep_b["target_name"] == "beta.zip"

    comp_ids_a = {c["component"]["id"] for c in comps_a}
    comp_ids_b = {c["component"]["id"] for c in comps_b}
    assert "src/alpha_unique.js" in comp_ids_a
    assert "beta_secret_mod.py" not in comp_ids_a
    assert "beta_secret_mod.py" in comp_ids_b
    assert "src/alpha_unique.js" not in comp_ids_b

    rules_b = {f["rule_id"] for f in rep_b["findings"]}
    rules_a = {f["rule_id"] for f in rep_a["findings"]}
    assert "SECRET_AWS_KEY" in rules_b
    assert "SECRET_AWS_KEY" not in rules_a


def test_stale_running_job_and_expired_audit_reaper(tmp_path):
    """Stalled running jobs become failed(interrupted); expired audits purge data & staging cleanly."""
    init_db()
    now = datetime.now(timezone.utc)
    stale_id = audit_service.create_audit("zip", "stale.zip", status="running")
    expired_id = audit_service.create_audit("zip", "expired.zip", status="completed")

    # Stage a directory for expired_id to assert filesystem cleanup
    expired_stage = Path(Config.STAGING_DIR) / expired_id
    expired_stage.mkdir(parents=True, exist_ok=True)
    (expired_stage / "entries.json").write_text("[]", encoding="utf-8")

    att_id = "att_01TESTREAPPRESERVED00000"
    with session_scope() as session:
        stale_row = session.get(AuditRow, stale_id)
        stale_row.started_at = now - timedelta(seconds=Config.SANDBOX_WALLTIME_SECONDS + 120)

        exp_row = session.get(AuditRow, expired_id)
        exp_row.expires_at = now - timedelta(minutes=5)

        session.add(
            AttestationRow(
                id=att_id,
                audit_id=expired_id,
                issued_at=now - timedelta(hours=2),
                expires_at=now + timedelta(days=30),
                subject_json={"kind": "archive", "sha256": "0" * 64, "control_verified": False},
                payload_json={"schema": "codit.attestation.v1"},
                signature="sig",
                kid="kid-1",
                control_verified=False,
            )
        )

    reaped_stale = reap_stale_running_jobs(now=now)
    assert reaped_stale >= 1

    reaped_exp = reap_expired_audits(now=now)
    assert reaped_exp >= 1
    assert not expired_stage.exists()

    with session_scope() as session:
        stale_after = session.get(AuditRow, stale_id)
        assert stale_after.status == "failed"
        assert stale_after.error_code == "interrupted"

        assert session.get(AuditRow, expired_id) is None
        att_after = session.get(AttestationRow, att_id)
        assert att_after is not None
        assert att_after.audit_id is None  # attestation retained past audit TTL

        # Clean up test rows
        session.delete(att_after)
        session.delete(stale_after)


def test_stable_fingerprint_and_secret_hashing():
    """Fingerprints are invariant to whitespace/line shifts, differ across files, and redact secrets."""
    fp1 = compute_fingerprint("AGT-005", "tests/test_auth.py", "assert   True")
    fp2 = compute_fingerprint("AGT-005", "tests/test_auth.py", "  assert True\n")
    fp_other_file = compute_fingerprint("AGT-005", "tests/test_billing.py", "assert True")
    assert fp1 == fp2
    assert fp1 != fp_other_file
    assert len(fp1) == 32

    secret = "AKIA" + "ZZZZZZZZZZZZZZZZ"
    matches = scan_text("src/cfg.py", f"\n\nTOKEN = '{secret}'\n")
    assert len(matches) == 1
    assert secret not in str(matches[0])
    assert is_test_file("tests/test_auth.py") is True
    assert is_test_file("src/auth.py") is False


def test_production_refuses_sqlite():
    with pytest.raises(RuntimeError, match="SQLite"):
        resolve_database_url("sqlite:///./.data/codit.db", env="production")


def test_graph_json_5mb_cap_truncation():
    nodes = [{"id": f"mod/{i}.py", "type": "Module", "name": f"{i}.py", "pad": "x" * 200} for i in range(500)]
    edges = [{"source_id": f"mod/{i}.py", "rel_type": "IMPORTS", "target_id": "mod/0.py"} for i in range(1, 500)]
    graph_json, truncated, kept_nodes, _ = serialize_graph(nodes, edges, cap_bytes=20_000)
    assert truncated is True
    assert len(graph_json.encode("utf-8")) <= 20_000
    assert any(n["id"] == "mod/0.py" for n in kept_nodes)


def test_alembic_0001_pivot_migration(tmp_path):
    """Verify Alembic upgrade head creates all Section 9 tables on a fresh SQLite DB."""
    from alembic import command
    from alembic.config import Config as AlembicConfig
    from sqlalchemy import create_engine, inspect

    db_file = tmp_path / "alembic_test.db"
    backend_dir = Path(__file__).resolve().parents[1]
    cfg = AlembicConfig(str(backend_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_dir / "app" / "db" / "migrations"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_file.as_posix()}")

    command.upgrade(cfg, "head")

    eng = create_engine(f"sqlite:///{db_file.as_posix()}")
    tables = set(inspect(eng).get_table_names())
    expected = {
        "audits",
        "audit_events",
        "findings",
        "blob_metrics",
        "license_cache",
        "attestations",
        "attest_challenges",
    }
    assert expected <= tables
    eng.dispose()

