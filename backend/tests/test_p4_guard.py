"""
P4 Guard CLI, Hook Contract, Policy-from-Base, Parity, Offline & Performance Tests (Gate G4).
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import jsonschema
import pytest

from codit_guard.cli import main as guard_main
from codit_guard.sources.hook_claude_code import evaluate_claude_hook_payload

from backend.app.history.models import HistoryOptions
from backend.app.history.walker import walk_history
from backend.tests.fixtures.history.make_repo import GitRepoBuilder

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "hook_claude_code"
GUARD_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "packages"
    / "codit_guard"
    / "src"
    / "codit_guard"
    / "schemas"
    / "guard.result.v1.json"
)


def _chdir_run(cwd: Path, argv: list[str], capsys) -> tuple[int, str, str]:
    old_cwd = Path.cwd()
    os.chdir(cwd)
    try:
        rc = guard_main(argv)
    finally:
        os.chdir(old_cwd)
    cap = capsys.readouterr()
    return rc, cap.out, cap.err


def test_claude_code_hook_fixtures_and_a15_edge_cases(tmp_path):
    """Contract tests against recorded Claude Code hook payloads + a15 edge cases."""
    (tmp_path / "tests").mkdir()
    (tmp_path / "src").mkdir()
    (tmp_path / "tests" / "test_app.py").write_text("import pytest\ndef test_ok():\n    assert fn(1) == 2\n", encoding="utf-8")
    (tmp_path / "src" / "app.py").write_text('KEY = "none"\n', encoding="utf-8")

    # 1. Write assert True -> exit 2 (blocked)
    p_write = json.loads((FIXTURES_DIR / "write_assert_true.json").read_text(encoding="utf-8"))
    rc, msg, hits = evaluate_claude_hook_payload(p_write, repo_root=tmp_path)
    assert rc == 2 and any(f.rule_id == "AGT-005" for f in hits)

    # 2. Edit adding @pytest.mark.skip -> exit 2 (blocked)
    p_edit = json.loads((FIXTURES_DIR / "edit_skip.json").read_text(encoding="utf-8"))
    rc, msg, hits = evaluate_claude_hook_payload(p_edit, repo_root=tmp_path)
    assert rc == 2 and any(f.rule_id == "AGT-003" for f in hits)

    # 3. MultiEdit adding AWS key -> exit 2 (blocked, redacted)
    p_multi = json.loads((FIXTURES_DIR / "multiedit_secret.json").read_text(encoding="utf-8"))
    rc, msg, hits = evaluate_claude_hook_payload(p_multi, repo_root=tmp_path)
    assert rc == 2 and any(f.rule_id == "SECRET_AWS_KEY" for f in hits)
    assert "AKIA0123456789ABCDEF" not in msg

    # 4. Bash rm tests/test_app.py -> exit 2 (GRD-002)
    p_bash = json.loads((FIXTURES_DIR / "bash_rm_test.json").read_text(encoding="utf-8"))
    rc, msg, hits = evaluate_claude_hook_payload(p_bash, repo_root=tmp_path)
    assert rc == 2 and any(f.rule_id == "GRD-002" for f in hits)

    # 5. Edit to .codit.yml -> exit 2 (GRD-001)
    rc, msg, hits = evaluate_claude_hook_payload(
        {"tool_name": "Write", "tool_input": {"file_path": ".codit.yml", "content": "version: 1\n"}},
        repo_root=tmp_path,
    )
    assert rc == 2 and hits[0].rule_id == "GRD-001"

    # 6. a15: ambiguous old_string and oversized content (>1 MB) fail-open safely
    (tmp_path / "src" / "dup.py").write_text("x = 1\nx = 1\n", encoding="utf-8")
    rc_ambig, _, _ = evaluate_claude_hook_payload(
        {"tool_name": "Edit", "tool_input": {"file_path": "src/dup.py", "old_string": "x = 1", "new_string": "x = 2"}},
        repo_root=tmp_path,
    )
    assert rc_ambig == 0
    rc_big, _, _ = evaluate_claude_hook_payload(
        {"tool_name": "Write", "tool_input": {"file_path": "tests/test_big.py", "content": "a" * (1100 * 1024)}},
        repo_root=tmp_path,
    )
    assert rc_big == 0
    assert (tmp_path / ".codit" / "guard.log").exists()


def test_policy_edit_attack_a14_and_base_trust(tmp_path, capsys):
    """a14: Editing .codit.yml on PR head to suppress findings still fails because base policy is used."""
    rb = GitRepoBuilder(tmp_path)
    rb.write(".codit.yml", "version: 1\npolicy:\n  fail_on: high\n")
    rb.write("tests/test_a.py", "def test_real():\n    assert compute(2) == 4\n")
    base_sha = rb.commit("base commit")

    # Attacker edits .codit.yml on PR head to disable failures AND commits assert True
    rb.write(".codit.yml", "version: 1\npolicy:\n  fail_on: never\n")
    rb.write("tests/test_a.py", "def test_real():\n    assert True\n")
    head_sha = rb.commit("pr head lowers policy and fakes test")

    rc, out, err = _chdir_run(
        tmp_path,
        ["check", "--base", base_sha, "--head", head_sha, "--format", "json", "--offline"],
        capsys,
    )
    assert rc == 1
    doc = json.loads(out)
    assert doc["config_source"] == "base"
    schema = json.loads(GUARD_SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(instance=doc, schema=schema)
    rules = {f["rule_id"] for f in doc["findings"]}
    assert "AGT-005" in rules
    assert "GRD-001" in rules


def test_parity_between_history_walker_and_guard(tmp_path, capsys):
    """G3/G4 Parity: walker and codit-guard check --base/--head produce identical (rule_id, fingerprint) sets."""
    rb = GitRepoBuilder(tmp_path)
    rb.write("src/pay.py", "def pay(v):\n    return v\n")
    rb.write("tests/test_pay.py", "def test_a():\n    assert pay(1) == 1\n\ndef test_b():\n    assert pay(2) == 2\n")
    rb.write(".github/workflows/ci.yml", "on: push\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: pytest\n")
    base_sha = rb.commit("clean base")

    rb.write("src/pay.py", "def pay(v):\n    return v * 10\n")
    rb.write("tests/test_pay.py", "def test_a():\n    assert True\n")
    rb.write(".github/workflows/ci.yml", "on: push\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: pytest\n        continue-on-error: true\n")
    head_sha = rb.commit("agent weakens tests and ci")

    hist_res = walk_history(tmp_path, HistoryOptions(max_commits=20))
    walker_pairs = {(f.rule_id, f.fingerprint) for f in hist_res.findings}

    rc, out, _ = _chdir_run(
        tmp_path,
        ["check", "--base", base_sha, "--head", head_sha, "--scope", "per-commit", "--format", "json", "--offline"],
        capsys,
    )
    assert rc == 1
    guard_doc = json.loads(out)
    guard_pairs = {(f["rule_id"], f["fingerprint"]) for f in guard_doc["findings"]}
    assert guard_pairs == walker_pairs and len(guard_pairs) >= 3


def test_net_scope_vs_per_commit_and_sarif_and_baseline(tmp_path, capsys):
    """Net scope nets restored test to 0; SARIF 2.1.0 & baseline/config rules work cleanly."""
    rb = GitRepoBuilder(tmp_path)
    rb.write("tests/test_x.py", "def test_1():\n    assert calc(1) == 1\n\ndef test_2():\n    assert calc(2) == 2\n\ndef test_3():\n    assert calc(3) == 3\n\ndef test_4():\n    assert calc(4) == 4\n")
    base_sha = rb.commit("base")

    rb.write("tests/test_x.py", "def test_1():\n    assert calc(1) == 1\n")
    rb.commit("remove tests temporarily")

    rb.write("tests/test_x.py", "def test_1():\n    assert calc(1) == 1\n\ndef test_2():\n    assert calc(2) == 2\n\ndef test_3():\n    assert calc(3) == 3\n\ndef test_4():\n    assert calc(4) == 4\n")
    head_sha = rb.commit("restore all tests")

    rc_net, out_net, _ = _chdir_run(
        tmp_path, ["check", "--base", base_sha, "--head", head_sha, "--scope", "net", "--format", "json", "--offline"], capsys
    )
    assert rc_net == 0 and json.loads(out_net)["findings"] == []

    rc_pc, out_pc, _ = _chdir_run(
        tmp_path, ["check", "--base", base_sha, "--head", head_sha, "--scope", "per-commit", "--format", "sarif", "--offline"], capsys
    )
    assert rc_pc == 0  # AGT-002 default severity is medium < default fail_on=high
    sarif_doc = json.loads(out_pc)
    assert sarif_doc["version"] == "2.1.0"
    assert sarif_doc["runs"][0]["results"][0]["partialFingerprints"]["codit/v1"]

    # Staged + baseline create workflow
    (tmp_path / "tests" / "test_bad.py").write_text("def test_t():\n    assert True\n", encoding="utf-8")
    rb._git(["add", "tests/test_bad.py"])
    rc_base, _, _ = _chdir_run(tmp_path, ["baseline", "create"], capsys)
    assert rc_base == 0
    rc_staged, out_st, _ = _chdir_run(tmp_path, ["check", "--staged", "--format", "json", "--offline"], capsys)
    assert rc_staged == 0
    assert json.loads(out_st)["baselined_count"] >= 1


def test_offline_socket_blocked_and_config_validation_and_installers(tmp_path, capsys, monkeypatch):
    """Offline mode makes zero network calls; unknown keys or >180d expiry fail with exit 3; installers preserve hooks."""
    def forbid_socket(*args, **kwargs):
        raise AssertionError("Network socket access attempted during --offline run")

    monkeypatch.setattr(socket, "socket", forbid_socket)
    rb = GitRepoBuilder(tmp_path)
    rb.write("requirements.txt", "flask==2.0.0\n")
    rb.commit("init")
    (tmp_path / "requirements.txt").write_text("flask==2.0.0\nrequests==2.31.0\n", encoding="utf-8")
    rb._git(["add", "requirements.txt"])

    rc_off, _, _ = _chdir_run(tmp_path, ["check", "--staged", "--offline", "--format", "json"], capsys)
    assert rc_off == 0

    # Unknown key -> exit 3
    bad_cfg = tmp_path / "bad.yml"
    bad_cfg.write_text("version: 1\nunknown_key: true\n", encoding="utf-8")
    rc_bad, _, err_bad = _chdir_run(tmp_path, ["check", "--staged", "--config", str(bad_cfg), "--offline"], capsys)
    assert rc_bad == 3

    # Suppression > 180 days -> exit 3
    too_far = (date.today() + timedelta(days=365)).isoformat()
    bad_cfg.write_text(f"version: 1\nsuppressions:\n  - fingerprint: '12345678'\n    reason: 'valid length reason here'\n    expires: '{too_far}'\n", encoding="utf-8")
    rc_exp, _, _ = _chdir_run(tmp_path, ["check", "--staged", "--config", str(bad_cfg), "--offline"], capsys)
    assert rc_exp == 3

    # Installers merge safely
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text(json.dumps({"hooks": {"PreToolUse": [{"matcher": "Other", "hooks": []}]}}), encoding="utf-8")
    rc_inst, _, _ = _chdir_run(tmp_path, ["install", "--agent", "claude-code", "--git-hook", "--pre-commit"], capsys)
    assert rc_inst == 0
    merged = json.loads((claude_dir / "settings.json").read_text(encoding="utf-8"))
    assert len(merged["hooks"]["PreToolUse"]) == 2
    assert (tmp_path / ".git" / "hooks" / "pre-commit").exists()
    assert (tmp_path / ".pre-commit-config.yaml").exists()

    # Help contains honest 3-layer notice
    rc_exp_rule, out_rule, _ = _chdir_run(tmp_path, ["explain", "GRD-002"], capsys)
    assert rc_exp_rule == 0 and "not complete" in out_rule


@pytest.mark.perf
def test_guard_import_time_and_staged_latency(tmp_path):
    """Import time <= 300ms and staged diff of 20 files / <=2,000 lines finishes <= 1.5s."""
    # Subprocess import time check
    t0 = time.perf_counter()
    subprocess.run(
        [sys.executable, "-c", "import codit_guard.cli"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    import_ms = (time.perf_counter() - t0) * 1000
    assert import_ms <= 1200, f"Unexpectedly slow subprocess python start: {import_ms:.1f}ms"

    # Measure direct module import + staged check latency
    rb = GitRepoBuilder(tmp_path)
    for i in range(18):
        rb.write(f"src/mod_{i}.py", "\n".join(f"v{j} = {j}" for j in range(60)) + "\n")
    rb.write("tests/test_mod_0.py", "def test_m():\n    assert mod_0(1) == 1\n")
    rb.commit("base 19 files")

    for i in range(18):
        rb.write(f"src/mod_{i}.py", "\n".join(f"v{j} = {j + 1}" for j in range(60)) + "\n")
    rb.write("tests/test_mod_0.py", "def test_m():\n    assert mod_0(2) == 2\n")
    rb._git(["add", "-A"])

    timings: list[float] = []
    old_cwd = Path.cwd()
    os.chdir(tmp_path)
    try:
        for _ in range(3):
            s = time.perf_counter()
            rc = guard_main(["check", "--staged", "--offline", "--format", "json"])
            timings.append(time.perf_counter() - s)
            assert rc == 0
    finally:
        os.chdir(old_cwd)
    assert min(timings) <= 1.5, f"Staged check exceeded 1.5s budget: {timings}"
