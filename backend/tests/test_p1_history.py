"""
P1 History Ingestion & Adversarial Security Tests (Gate G2):
- Bare history & private token passing strictly via env (no token in argv/URL)
- ZIP with .git allowlisted vs ZIP without .git (`assessed=false`)
- Shallow boundary handling, binary & LFS blobs, skipped_deep, CRLF, non-UTF-8
- Identity & commit message canary scrubbing
- Adversarial a1..a7 & a12
"""

from __future__ import annotations

import io
import json
import stat
import subprocess
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.app.config import Config
from backend.app.db.engine import resolve_database_url
from backend.app.history.acquire import (
    HistoryAcquisitionError,
    build_clone_command,
    build_hardened_git_env,
    validate_branch_name,
    validate_github_repo_input,
)
from backend.app.history.models import HistoryOptions
from backend.app.history.walker import _safe_decode_tree_path, walk_history
from backend.app.history.worker import run_history_worker
from backend.app.ingestion.git_clone import clone_private_repo
from backend.app.ingestion.zip_extract import extract_git_history_from_zip
from backend.tests.fixtures.history.make_repo import GitRepoBuilder


def _zip_directory_with_git(repo_dir: Path) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in repo_dir.rglob("*"):
            if item.is_file():
                rel = item.relative_to(repo_dir).as_posix()
                zf.write(item, rel)
    return buf.getvalue()


def test_zip_with_git_and_without_git(tmp_path):
    """ZIP with .git yields assessed=True HistoryResult; ZIP without .git yields assessed=False."""
    repo_dir = tmp_path / "repo"
    rb = GitRepoBuilder(repo_dir)
    rb.write("package.json", json.dumps({"name": "hist-demo", "version": "1.0.0"}))
    rb.write("src/app.py", "def ok():\n    return 1\n")
    rb.write("tests/test_app.py", "def test_ok():\n    assert True\n")
    rb.commit("Initial commit")
    rb.write("src/app.py", "def ok():\n    return 2\n")
    rb.commit("Update return value")

    zip_with_git = _zip_directory_with_git(repo_dir)
    buf_no_git = io.BytesIO()
    with zipfile.ZipFile(buf_no_git, "w") as zf:
        zf.writestr("package.json", '{"name":"nogit"}')
        zf.writestr("app.py", "print(1)")

    app = create_app({"GRAPH_BACKEND": "demo"})
    client = TestClient(app)

    r1 = client.post("/api/ingest/zip", files={"file": ("withgit.zip", zip_with_git, "application/zip")})
    assert r1.status_code == 200
    assert r1.json()["history"]["assessed"] is True
    assert r1.json()["history"]["commits_analyzed"] == 2

    r2 = client.post("/api/ingest/zip", files={"file": ("nogit.zip", buf_no_git.getvalue(), "application/zip")})
    assert r2.status_code == 200
    assert r2.json()["history"]["assessed"] is False
    assert r2.json()["history"]["reason"] == "no_history_in_archive"


def test_private_token_never_in_argv_or_url(tmp_path, monkeypatch):
    """Secret token MUST pass via GIT_CONFIG_COUNT env vars, never inside CLI argv or URL."""
    secret_tok = "ghs_SUPERSECRET_TOKEN_12345"
    captured = {}

    def fake_run(cmd, env=None, **kwargs):
        captured["cmd"] = cmd
        captured["env"] = env or {}
        return subprocess.CompletedProcess(cmd, 0, stdout=b"", stderr=b"")

    monkeypatch.setattr("backend.app.ingestion.git_clone.subprocess.run", fake_run)
    dest = tmp_path / "clone_dest"
    clone_private_repo("acme/widget", secret_tok, dest, branch="main")

    joined_cmd = " ".join(captured["cmd"])
    assert secret_tok not in joined_cmd
    assert "x-access-token" not in joined_cmd
    assert captured["env"]["GIT_CONFIG_COUNT"] == "1"
    assert captured["env"]["GIT_CONFIG_KEY_0"] == "http.extraHeader"
    assert "Authorization: Basic " in captured["env"]["GIT_CONFIG_VALUE_0"]

    bare_cmd = build_clone_command("acme", "widget", dest, depth=500, branch="main")
    assert secret_tok not in " ".join(bare_cmd)
    bare_env = build_hardened_git_env(secret_tok)
    assert bare_env["GIT_CONFIG_COUNT"] == "1"


def test_canary_messages_and_identities_scrubbed(tmp_path):
    """Plant canary author names, emails, and messages; confirm absent from result & DB."""
    repo_dir = tmp_path / "canary_repo"
    rb = GitRepoBuilder(repo_dir)
    canary_name = "CANARY_AUTHOR_NAME_992"
    canary_email = "canary993@evil.test"
    canary_msg = "CANARY_COMMIT_MSG_991 fix bug"
    rb.write("app.py", "print('hello')\n")
    rb.commit(canary_msg, author_name=canary_name, author_email=canary_email)

    zip_bytes = _zip_directory_with_git(repo_dir)
    app = create_app({"GRAPH_BACKEND": "demo"})
    client = TestClient(app)
    res = client.post("/api/ingest/zip", files={"file": ("canary.zip", zip_bytes, "application/zip")})
    assert res.status_code == 200
    assert canary_name not in res.text
    assert canary_email not in res.text
    assert canary_msg not in res.text

    rep = client.get("/api/report")
    assert canary_name not in rep.text
    assert canary_email not in rep.text
    assert canary_msg not in rep.text

    db_url = resolve_database_url()
    if db_url.startswith("sqlite:///"):
        raw_db = Path(db_url[len("sqlite:///"):]).read_bytes()
        for canary in (canary_name.encode(), canary_email.encode(), canary_msg.encode()):
            assert canary not in raw_db


def test_shallow_boundary_binary_lfs_and_edge_cases(tmp_path):
    """Shallow boundary, binary blobs, LFS pointers, CRLF, and skipped_deep behave safely."""
    repo_dir = tmp_path / "full"
    rb = GitRepoBuilder(repo_dir)
    for idx in range(4):
        rb.write(f"src/m{idx}.py", f"def fn_{idx}():\r\n    return {idx}\r\n")
        rb.write("bin.dat", b"\x00\x01\x02PNG_BINARY")
        rb.write("big.bin", "version https://git-lfs.github.com/spec/v1\noid sha256:abc\nsize 123\n")
        rb.commit(f"step {idx}")

    # Create shallow clone (--depth 2) via local file protocol for fixture creation ONLY
    shallow_dir = tmp_path / "shallow"
    url = repo_dir.as_uri()
    subprocess.run(
        ["git", "clone", "--depth", "2", url, str(shallow_dir)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    res = run_history_worker(shallow_dir, HistoryOptions(max_commits=10))
    assert res.coverage.assessed is True
    assert res.coverage.shallow_boundary is True
    assert any(c.shallow_baseline for c in res.commits)


def test_adversarial_a1_a2_a3_a5_zip_git_attacks(tmp_path):
    """a1 fsmonitor config, a2 hooks, a3 alternates, a5 symlink/gitdir .git never execute or extract."""
    canary_a1 = tmp_path / "CANARY_A1.txt"
    canary_a2 = tmp_path / "CANARY_A2.txt"

    repo_dir = tmp_path / "seed"
    rb = GitRepoBuilder(repo_dir)
    rb.write("main.py", "x = 1\n")
    rb.commit("init")

    # Build hostile ZIP injecting a1 (.git/config fsmonitor), a2 (.git/hooks), a3 (.git/objects/info/alternates)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for item in repo_dir.rglob("*"):
            if item.is_file():
                zf.write(item, item.relative_to(repo_dir).as_posix())
        zf.writestr(".git/config", f"[core]\n\tfsmonitor = touch {canary_a1.as_posix()}\n")
        zf.writestr(".git/hooks/post-checkout", f"#!/bin/sh\ntouch {canary_a2.as_posix()}\n")
        zf.writestr(".git/objects/info/alternates", "/etc/passwd\n")

    git_dest = tmp_path / "extracted_git"
    ok, reason = extract_git_history_from_zip(buf.getvalue(), git_dest)
    assert ok is True
    assert reason is None
    assert not (git_dest / ".git" / "hooks" / "post-checkout").exists()
    assert not (git_dest / ".git" / "objects" / "info" / "alternates").exists()
    cfg_txt = (git_dest / ".git" / "config").read_text(encoding="utf-8")
    assert "fsmonitor" not in cfg_txt

    result = run_history_worker(git_dest, HistoryOptions())
    assert result.coverage.assessed is True
    assert not canary_a1.exists()
    assert not canary_a2.exists()

    # a5: symlink .git entry & gitdir pointer file rejected cleanly
    buf_sym = io.BytesIO()
    with zipfile.ZipFile(buf_sym, "w") as zf:
        zi = zipfile.ZipInfo(".git")
        zi.external_attr = (stat.S_IFLNK | 0o777) << 16
        zf.writestr(zi, "/etc")
    ok_sym, r_sym = extract_git_history_from_zip(buf_sym.getvalue(), tmp_path / "sym_out")
    assert ok_sym is False and r_sym == "unsafe_git_symlink"

    buf_gitdir = io.BytesIO()
    with zipfile.ZipFile(buf_gitdir, "w") as zf:
        zf.writestr(".git", "gitdir: /etc/shadow\n")
    ok_gd, r_gd = extract_git_history_from_zip(buf_gitdir.getvalue(), tmp_path / "gd_out")
    assert ok_gd is False and r_gd == "unsafe_git_metadata"


def test_adversarial_a7_a12_path_and_url_injection():
    """a7 unsafe tree paths rejected; a12 URL/flag/protocol injection rejected."""
    for bad in (b"../escape", b"sub/../../etc", b"/abs/path", b"C:\\win\\path", b"bad\x00file"):
        with pytest.raises(ValueError):
            _safe_decode_tree_path(bad)

    for bad_repo in (
        "--upload-pack=touch /tmp/pwn",
        "file:///tmp/repo",
        "ext::sh -c id",
        "https://evil.com/org/repo",
        "https://user:pass@github.com/org/repo",
        "org/repo --config=foo",
    ):
        with pytest.raises(HistoryAcquisitionError):
            validate_github_repo_input(bad_repo)

    for bad_branch in ("--upload-pack=x", "../main", "a//b", "branch name"):
        with pytest.raises(HistoryAcquisitionError):
            validate_branch_name(bad_branch)


def test_worker_no_http_imports():
    """Worker module and walker must not import HTTP client libraries."""
    hist_dir = Path(__file__).resolve().parents[1] / "app" / "history"
    for fname in ("worker.py", "walker.py"):
        src = (hist_dir / fname).read_text(encoding="utf-8")
        for forbidden in ("import httpx", "import requests", "urllib.request"):
            assert forbidden not in src


def test_adversarial_a6_gitlink_symlink_and_skipped_deep(tmp_path, monkeypatch):
    """a6 gitlink (160000) & tree symlink (120000) skipped; skipped_deep triggers above cap."""
    from dulwich.objects import Blob, Commit, Tree
    from dulwich.repo import Repo

    repo_dir = tmp_path / "a6_repo"
    rb = GitRepoBuilder(repo_dir)
    rb.write("ok.py", "print(1)\n")
    base_sha = rb.commit("base")

    # Inject a commit whose tree contains a gitlink (0o160000) and a symlink (0o120000) via dulwich
    repo = Repo(str(repo_dir))
    try:
        sym_blob = Blob.from_string(b"/etc/passwd")
        repo.object_store.add_object(sym_blob)
        base_commit = repo.object_store[base_sha.encode("ascii")]
        base_tree = repo.object_store[base_commit.tree]
        new_tree = Tree()
        for entry in base_tree.items():
            new_tree.add(entry.path, entry.mode, entry.sha)
        new_tree.add(b"evil_link", 0o120000, sym_blob.id)
        new_tree.add(b"submod", 0o160000, base_sha.encode("ascii"))
        repo.object_store.add_object(new_tree)

        c2 = Commit()
        c2.tree = new_tree.id
        c2.parents = [base_commit.id]
        c2.author = c2.committer = b"Test <t@example.test>"
        c2.author_time = c2.commit_time = 1764001000
        c2.author_timezone = c2.commit_timezone = 0
        c2.encoding = b"UTF-8"
        c2.message = b"add symlink and submodule"
        repo.object_store.add_object(c2)
        repo.refs[b"refs/heads/main"] = c2.id
    finally:
        repo.close()

    res = walk_history(repo_dir, HistoryOptions(max_commits=10))
    assert res.coverage.assessed is True
    assert res.commits[-1].prod_lines_delta == 0
    dumped = res.model_dump_json()
    assert "evil_link" not in dumped
    assert "submod" not in dumped
    assert "/etc/passwd" not in dumped
    assert len(res.findings) == 0

    # Verify HISTORY_MAX_FILES_PER_COMMIT triggers skipped_deep
    deep_dir = tmp_path / "deep_repo"
    rb2 = GitRepoBuilder(deep_dir)
    for i in range(6):
        rb2.write(f"m{i}.py", f"x = {i}\n")
    rb2.commit("megacommit")
    monkeypatch.setattr(Config, "HISTORY_MAX_FILES_PER_COMMIT", 3)
    res_deep = walk_history(deep_dir, HistoryOptions(max_commits=10))
    assert res_deep.coverage.skipped_deep_commits >= 1
    assert res_deep.commits[0].skipped_deep is True


def test_compute_line_delta_linear_on_large_diffs():
    """Large diffs must finish quickly without quadratic difflib stalls and keep accurate added line numbers."""
    import time
    from backend.app.history.walker import _compute_line_delta

    before = "\n".join(f"old_line_{i}" for i in range(6000)) + "\n"
    after = "\n".join(f"new_line_{i}" for i in range(6000)) + "\n"
    t0 = time.perf_counter()
    added, removed, a_cnt, r_cnt = _compute_line_delta(before, after)
    elapsed = time.perf_counter() - t0
    assert elapsed < 1.0
    assert a_cnt == 6000 and r_cnt == 6000
    assert added[0].lineno == 1 and added[-1].lineno == 6000

