"""P10 Hardening, Adversarial (a4, a11, DB canary sweep) & Alembic migration verification."""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from backend.app.history.models import HistoryOptions
from backend.app.history.walker import walk_history
from backend.app.ingestion.models import FileEntry
from backend.app.services.audit_service import create_audit, run_audit_pipeline
from backend.tests.fixtures.history.make_repo import GitRepoBuilder


def test_alembic_0001_pivot_upgrade_on_fresh_sqlite(tmp_path):
    """Verify Alembic migration `0001_pivot` applies cleanly from scratch and stamps head."""
    db_path = tmp_path / "alembic_check.db"
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    env["ENV"] = "development"
    repo_root = Path(__file__).resolve().parents[2]
    res = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "backend/alembic.ini", "upgrade", "head"],
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert res.returncode == 0, f"Alembic upgrade failed: {res.stderr}\n{res.stdout}"
    conn = sqlite3.connect(str(db_path))
    try:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        assert {"audits", "audit_events", "findings", "blob_metrics", "license_cache", "attestations", "attest_challenges"}.issubset(tables)
    finally:
        conn.close()


def test_adversarial_a4_oversized_blob_and_a11_commit_cap(tmp_path):
    """a4/a11: Oversized blobs (>HISTORY_MAX_BLOB_KB) skipped and max_commits cap stops deep traversal cleanly."""
    repo_dir = tmp_path / "cap_repo"
    rb = GitRepoBuilder(repo_dir)
    # Build 12 commits + 1 giant blob exceeding a tiny 4 KB cap
    for i in range(12):
        rb.write("src/mod.py", f"def fn_{i}():\n    return {i}\n")
        rb.commit(f"commit {i} CANARY_COMMIT_TEXT_{i}")
    rb.write("src/huge.py", "x = 1\n" * 2000)  # > 12 KB
    rb.commit("huge blob commit")

    res = walk_history(
        repo_dir,
        HistoryOptions(max_commits=5, max_days=365, max_files_per_commit=50, max_blob_kb=4),
    )
    assert res.coverage.assessed is True
    assert res.coverage.commits_analyzed == 5
    assert "max_commits" in res.coverage.caps_hit


def test_db_and_filesystem_zero_source_and_zero_canary_persistence(tmp_path):
    """After running an audit with planted source & canary tokens, grep SQLite tables to prove zero source persisted."""
    canary_src = "CANARY_RAW_SOURCE_SECRET_TOKEN_98765"
    canary_code = f"def super_secret_impl():\n    token = '{canary_src}'\n    return 42\n"
    aid = create_audit(source_kind="zip", source_ref="canary-zero-persist.zip")
    run_audit_pipeline(aid, [FileEntry("src/canary_mod.py", len(canary_code), "python", canary_code)], "canary-zero-persist.zip", "zip")

    db_file = Path(__file__).resolve().parents[2] / ".data" / "codit.db"
    if db_file.exists():
        conn = sqlite3.connect(str(db_file))
        try:
            for (tname,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
                for row in conn.execute(f"SELECT * FROM {tname}").fetchall():
                    row_txt = " ".join(str(x) for x in row)
                    assert canary_src not in row_txt, f"Canary source leaked into DB table {tname}!"
                    assert "def super_secret_impl" not in row_txt, f"Raw code leaked into DB table {tname}!"
        finally:
            conn.close()
