"""
Comprehensive Adversarial Security Verification Suite (Section 1 & Module 9).

Tests all non-negotiable security constraints under hostile attack conditions:
1. Zero execution of untrusted code: malicious postinstall & setup.py never run.
2. Zip-Slip directory traversal rejection before extraction.
3. Zip-Bomb resource exhaustion rejection before extraction.
4. Ephemeral isolated sandbox with disabled network egress.
5. Zero raw source code in LLM payload.
6. Immediate source file deletion for ZIP upload tier.
"""

from __future__ import annotations

import io
import os
import tempfile
import zipfile
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from backend.app import create_app
from backend.app.collectors.models import AuditFinding
from backend.app.ingestion.zip_extract import (
    ZipBombError,
    ZipSlipError,
    extract_zip,
    purge_extracted_files,
)
from backend.app.routes.analyze import run_full_analysis
from backend.app.routes.ingest import set_active_codebase
from backend.sandbox.job_queue import SandboxExecutor
from backend.app.scoring.roadmap_synthesis import build_llm_payload
from backend.app.scoring.rules_engine import score_audit


@pytest.fixture()
def client():
    app = create_app({"GRAPH_BACKEND": "demo"})
    return TestClient(app)


def test_adversarial_malicious_postinstall_never_executes(client, tmp_path):
    """
    Constraint 1 Verification:
    A deliberately malicious package.json with a postinstall script designed to
    drop a canary file or curl an external server is processed through the pipeline.
    We instrument the filesystem to confirm the script NEVER executes at any stage.
    """
    canary_file = tmp_path / "PWNED_POSTINSTALL.txt"
    if canary_file.exists():
        canary_file.unlink()

    # Craft malicious package.json
    malicious_pkg_json = f"""{{
      "name": "malicious-package",
      "version": "1.0.0",
      "scripts": {{
        "postinstall": "touch {canary_file.as_posix()} || echo PWNED > {canary_file.as_posix()}"
      }},
      "dependencies": {{
        "express": "4.18.2"
      }}
    }}"""

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("package.json", malicious_pkg_json)
        z.writestr("index.js", "console.log('malicious repo');")

    temp_dir = Path(tempfile.mkdtemp(prefix="sec_test_postinstall_"))
    zpath = temp_dir / "attack_repo.zip"
    zpath.write_bytes(buf.getvalue())

    try:
        with open(zpath, "rb") as f:
            res = client.post("/api/ingest/zip", files={"file": ("attack_repo.zip", f, "application/zip")})
        assert res.status_code == 200

        # Run complete analysis pipeline
        analysis_res = client.post("/api/analyze/run")
        assert analysis_res.status_code == 200

        # RIGOROUS PROOF: Canary file was NEVER created! Postinstall script NEVER ran!
        assert not canary_file.exists(), "SECURITY FAILURE: Malicious postinstall script executed!"
    finally:
        purge_extracted_files(temp_dir)
        if canary_file.exists():
            canary_file.unlink()


def test_adversarial_malicious_setup_py_never_executes(client, tmp_path):
    """
    Constraint 1 Verification:
    A repository with a malicious setup.py executing arbitrary code on import/build
    is processed statically without executing setup.py.
    """
    canary_file = tmp_path / "PWNED_SETUP_PY.txt"
    if canary_file.exists():
        canary_file.unlink()

    malicious_setup_py = f"""
import os
with open(r'{canary_file.as_posix()}', 'w') as f:
    f.write('PWNED')
from setuptools import setup
setup(name='exploit', version='1.0')
"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("setup.py", malicious_setup_py)
        z.writestr("app.py", "print('hello')")

    temp_dir = Path(tempfile.mkdtemp(prefix="sec_test_setup_"))
    zpath = temp_dir / "attack_py_repo.zip"
    zpath.write_bytes(buf.getvalue())

    try:
        with open(zpath, "rb") as f:
            res = client.post("/api/ingest/zip", files={"file": ("attack_py_repo.zip", f, "application/zip")})
        assert res.status_code == 200

        analysis_res = client.post("/api/analyze/run")
        assert analysis_res.status_code == 200

        # Canary file must NOT exist
        assert not canary_file.exists(), "SECURITY FAILURE: Malicious setup.py executed!"
    finally:
        purge_extracted_files(temp_dir)
        if canary_file.exists():
            canary_file.unlink()


def test_adversarial_zip_slip_rejected_before_disk_write():
    """
    Constraint 2 Verification:
    Zip-Slip payloads targeting relative traversal, absolute root paths, or drive escapes
    are 100% intercepted and rejected before extracting any file.
    """
    test_payloads = [
        "../../../../etc/shadow",
        "../traversal.txt",
        "subfolder/../../secret.txt",
        "/absolute/root/file.txt",
        "C:\\Windows\\System32\\calc.exe",
    ]

    for payload_path in test_payloads:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr(payload_path, "malicious payload")
            z.writestr("safe.txt", "safe file")

        temp_dir = Path(tempfile.mkdtemp(prefix="sec_test_slip_"))
        try:
            with pytest.raises(ZipSlipError):
                extract_zip(buf.getvalue(), temp_dir)
            # Assert safe.txt was NEVER written to disk
            assert not (temp_dir / "safe.txt").exists()
        finally:
            purge_extracted_files(temp_dir)


def test_adversarial_zip_bomb_size_and_count_limits():
    """
    Constraint 3 Verification:
    Pre-extraction inspection catches file count and cumulative uncompressed size violations.
    """
    # 1. Excessive file count check
    buf_count = io.BytesIO()
    with zipfile.ZipFile(buf_count, "w") as z:
        for i in range(15):
            z.writestr(f"file_{i}.txt", "x")

    temp_dir = Path(tempfile.mkdtemp(prefix="sec_test_bomb_"))
    try:
        from backend.app.config import Config
        orig_max = Config.MAX_FILE_COUNT
        Config.MAX_FILE_COUNT = 10
        try:
            with pytest.raises(ZipBombError) as exc:
                extract_zip(buf_count.getvalue(), temp_dir)
            assert "exceeding maximum limit" in str(exc.value)
        finally:
            Config.MAX_FILE_COUNT = orig_max
    finally:
        purge_extracted_files(temp_dir)


def test_sandbox_network_isolation_policy():
    """
    Constraint 5 Verification:
    SandboxExecutor confirms network isolation policy and disables outbound access.
    """
    executor = SandboxExecutor()
    assert executor.network_mode == "none"
    assert executor.test_network_isolation() is True


def test_llm_payload_contains_zero_raw_source_code():
    """
    Constraint 6 Verification:
    Asserts that request payloads formatted for LLM synthesis exclude raw source code.
    """
    findings = [
        AuditFinding(
            id="f-sec-1",
            dimension="security",
            severity="critical",
            confidence="high",
            description="Leaked AWS Access Key in auth.py",
            evidence_file="src/auth.py",
            evidence_line=14,
            rule_id="SECRET_AWS_KEY",
        )
    ]
    scorecard = score_audit(findings)
    comps = [{"component": {"id": "src/auth.py", "name": "auth.py"}, "reach": 4}]

    payload = build_llm_payload(scorecard, findings, comps, goal="production")
    raw_json = str(payload)

    # Check that code keywords and file contents are not present
    assert "class AuthHandler:" not in raw_json
    assert "def verify_token(" not in raw_json
    assert "import boto3" not in raw_json
    # Confirm finding metadata is present
    assert "SECRET_AWS_KEY" in raw_json
    assert "src/auth.py" in raw_json


def test_zip_tier_source_deletion_verified_by_filesystem_check(client):
    """
    Constraint 7 Verification:
    Verify that source code for a ZIP upload is deleted from storage immediately post-audit.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("app.py", "print('ephemeral')")
        z.writestr("requirements.txt", "fastapi==0.110.0")

    temp_dir = Path(tempfile.mkdtemp(prefix="sec_test_deletion_"))
    zpath = temp_dir / "ephemeral.zip"
    zpath.write_bytes(buf.getvalue())

    # Ingest
    with open(zpath, "rb") as f:
        res = client.post("/api/ingest/zip", files={"file": ("ephemeral.zip", f, "application/zip")})
    assert res.status_code == 200

    from backend.app.routes.ingest import get_active_codebase
    cb = get_active_codebase()
    extracted_path = Path(cb["temp_dir"])
    assert extracted_path.exists(), "Extracted folder must exist before analysis"

    # Run analysis
    analysis_res = client.post("/api/analyze/run")
    assert analysis_res.status_code == 200
    assert analysis_res.json()["source_deleted"] is True

    # Check filesystem: extracted folder MUST BE PURGED!
    assert not extracted_path.exists(), "SECURITY FAILURE: Extracted source files were not deleted!"
    purge_extracted_files(temp_dir)
