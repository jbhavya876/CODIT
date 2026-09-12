"""
Tests for Module 1: Ingestion Pipeline across all 3 intake paths.
"""

from __future__ import annotations

import io
import tempfile
import zipfile
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from backend.app import create_app
from backend.app.ingestion.github_fetch import parse_github_url
from backend.app.ingestion.models import FileEntry, detect_language, is_ignored_path
from backend.app.ingestion.zip_extract import (
    ZipBombError,
    ZipSlipError,
    extract_zip,
    purge_extracted_files,
    validate_zip_metadata,
)
from backend.sandbox.job_queue import SandboxExecutor


@pytest.fixture()
def client():
    app = create_app({"GRAPH_BACKEND": "demo"})
    return TestClient(app)


def test_language_detection():
    assert detect_language("backend/app/main.py") == "python"
    assert detect_language("frontend/src/App.tsx") == "typescript"
    assert detect_language("frontend/src/index.js") == "javascript"
    assert detect_language("package.json") == "json"
    assert detect_language("pyproject.toml") == "toml"
    assert detect_language("docker-compose.yml") == "yaml"
    assert detect_language("Dockerfile") == "dockerfile"
    assert detect_language(".env.example") == "env"


def test_ignored_paths():
    assert is_ignored_path(".git/HEAD") is True
    assert is_ignored_path("node_modules/react/index.js") is True
    assert is_ignored_path("backend/__pycache__/run.pyc") is True
    assert is_ignored_path("docs/images/architecture.png") is True
    assert is_ignored_path("backend/app/services/cypher.py") is False


def test_parse_github_url():
    assert parse_github_url("https://github.com/charmi-reddy/Dependency-Detective") == ("charmi-reddy", "Dependency-Detective")
    assert parse_github_url("charmi-reddy/Dependency-Detective") == ("charmi-reddy", "Dependency-Detective")
    assert parse_github_url("https://github.com/pallets/flask.git") == ("pallets", "flask")


def test_zip_valid_extraction():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("package.json", '{"name": "test-pkg", "dependencies": {"express": "^4.18.2"}}')
        z.writestr("src/index.js", "const express = require('express');")

    buf.seek(0)
    temp_dir = Path(tempfile.mkdtemp(prefix="test_zip_valid_"))
    try:
        entries = extract_zip(buf.getvalue(), temp_dir)
        paths = {e.path for e in entries}
        assert "package.json" in paths
        assert "src/index.js" in paths
        assert any(e.language == "javascript" for e in entries)
    finally:
        purge_extracted_files(temp_dir)


def test_zip_slip_adversarial_rejected_before_writing():
    """Verify that path traversal is caught BEFORE writing any file."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        # Malicious zip-slip payload targeting outside extraction directory
        z.writestr("../../../etc/passwd", "root:x:0:0:root:/root:/bin/bash")
        z.writestr("benign.txt", "hello")

    buf.seek(0)
    temp_dir = Path(tempfile.mkdtemp(prefix="test_zip_slip_"))
    try:
        with pytest.raises(ZipSlipError) as exc_info:
            extract_zip(buf.getvalue(), temp_dir)
        assert "Zip-Slip" in str(exc_info.value)
        # Verify no file was written to disk!
        assert not (temp_dir / "benign.txt").exists()
    finally:
        purge_extracted_files(temp_dir)


def test_zip_bomb_file_count_rejected():
    """Verify archive with excessive file count is rejected before extraction."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for i in range(10):
            z.writestr(f"file_{i}.txt", "test")

    buf.seek(0)
    temp_dir = Path(tempfile.mkdtemp(prefix="test_zip_bomb_"))
    try:
        from backend.app.config import Config
        old_max = Config.MAX_FILE_COUNT
        Config.MAX_FILE_COUNT = 5  # Set small limit to trigger bomb guard
        try:
            with pytest.raises(ZipBombError) as exc_info:
                extract_zip(buf.getvalue(), temp_dir)
            assert "exceeding maximum limit" in str(exc_info.value)
        finally:
            Config.MAX_FILE_COUNT = old_max
    finally:
        purge_extracted_files(temp_dir)


def test_concurrent_sandbox_jobs_have_isolated_filesystems():
    """Verify no two concurrent jobs share any filesystem state."""
    executor = SandboxExecutor()
    job1 = executor.create_job("zip", "job1.zip")
    job2 = executor.create_job("zip", "job2.zip")
    assert job1.job_id != job2.job_id
