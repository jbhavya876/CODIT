"""
P2 Attribution & P3 Process-Integrity Detectors Corpus (s01-s27) and Property Tests (Gate G3).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Dict, List, Set

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from codit_core.attribution import ATTRIBUTION_LIMITATION, attribute_commit
from codit_core.detectors.rules_catalog import load_rules_catalog
from codit_core.testmetrics import extract_test_file_metrics

from backend.app.history.models import HistoryOptions
from backend.app.history.walker import walk_history
from backend.tests.fixtures.history.make_repo import GitRepoBuilder


def test_attribution_signals_and_anti_accusation_rules():
    """Trailer, footer, bot account, quoted-fake rejection, and zero banned wording."""
    att_claude = attribute_commit("Fix auth check\n\nCo-Authored-By: Claude Sonnet 4 <noreply@anthropic.com>", "Dev <dev@ex.com>")
    assert att_claude.agent_id == "claude-code"
    assert att_claude.basis == "trailer"
    assert att_claude.confidence == "high"

    att_footer = attribute_commit("Refactor billing\n\nGenerated with Claude Code", "Dev <dev@ex.com>")
    assert att_footer.agent_id == "claude-code"
    assert att_footer.basis == "footer"

    att_bot = attribute_commit("Bump lockfile", "devin-ai-integration[bot] <devin@example.com>")
    assert att_bot.agent_id == "devin"
    assert att_bot.basis == "bot_account"

    att_copilot = attribute_commit("Add tests", "github-copilot[bot] <copilot@github.com>")
    assert att_copilot.agent_id == "github-copilot"
    assert att_copilot.basis == "bot_account"

    # Quoted fake trailer or non-final paragraph must NOT trigger attribution
    fake_quoted = "PR notes:\n> Co-Authored-By: Claude <noreply@anthropic.com>\n\nPlain body"
    att_fake = attribute_commit(fake_quoted, "Alice <alice@example.test>")
    assert att_fake.agent_id is None
    assert att_fake.basis == "none"
    assert att_fake.status == "unknown"
    assert "human" not in att_fake.status

    # Verify zero accusation words in all rule templates and attribution limitation
    catalog = load_rules_catalog()
    for rule_id, meta in catalog.items():
        tpl = (meta.get("template") or "").lower()
        assert "wrote" not in tpl, rule_id
        assert "deleted your" not in tpl, rule_id
        assert " did " not in f" {tpl} ", rule_id
        assert "human" not in tpl, rule_id
    assert "unknown, not human-authored" in ATTRIBUTION_LIMITATION


def _build_and_walk(tmp_path: Path, name: str, builder_fn) -> tuple:
    repo_dir = tmp_path / name
    rb = GitRepoBuilder(repo_dir)
    builder_fn(rb, repo_dir)
    res = walk_history(repo_dir, HistoryOptions(max_commits=200))
    return res, {(f.rule_id, f.commit_sha) for f in res.findings}


def test_scenario_corpus_s01_to_s27_and_metrics(tmp_path):
    """Run all corpus scenarios s01-s27 and verify precision >= 0.95 / recall >= 0.85."""
    high_value_rules = {"AGT-001", "AGT-003", "AGT-005", "AGT-007"}

    tp_hv = fp_hv = fn_hv = 0
    tp_other = fp_other = 0

    def record_eval(actual_rules: Set[str], expected_rules: Set[str], scenario: str):
        nonlocal tp_hv, fp_hv, fn_hv, tp_other, fp_other
        assert actual_rules == expected_rules, f"Scenario {scenario}: got {actual_rules}, expected {expected_rules}"
        for r in high_value_rules:
            if r in actual_rules and r in expected_rules:
                tp_hv += 1
            elif r in actual_rules:
                fp_hv += 1
            elif r in expected_rules:
                fn_hv += 1
        for r in actual_rules | expected_rules:
            if r not in high_value_rules:
                if r in actual_rules and r in expected_rules:
                    tp_other += 1
                elif r in actual_rules:
                    fp_other += 1

    # s01: Clean history with growing tests -> {}
    def s01(rb: GitRepoBuilder, _):
        rb.write("src/math.py", "def add(a, b):\n    return a + b\n")
        rb.write("tests/test_math.py", "def test_add():\n    assert 1 + 1 == 2\n")
        rb.commit("init")
        rb.write("src/math.py", "def add(a, b):\n    return a + b\n\ndef sub(a, b):\n    return a - b\n")
        rb.write("tests/test_math.py", "def test_add():\n    assert 1 + 1 == 2\n\ndef test_sub():\n    assert 2 - 1 == 1\n")
        rb.commit("add sub")
    res, _ = _build_and_walk(tmp_path, "s01", s01)
    record_eval({f.rule_id for f in res.findings}, set(), "s01")
    assert len(res.series) == 2 and res.series[-1]["tests"] == 2

    # s02: Test deleted in commit changing covered code -> AGT-001 high
    def s02(rb: GitRepoBuilder, _):
        rb.write("src/billing.py", "def charge(x):\n    return x\n")
        rb.write("tests/test_billing.py", "def test_charge():\n    assert charge(10) == 10\n\ndef test_refund():\n    assert refund(5) == 5\n")
        rb.commit("init")
        rb.write("src/billing.py", "def charge(x):\n    return x * 2\n")
        rb.write("tests/test_billing.py", "def test_charge():\n    assert charge(10) == 10\n")
        rb.commit("update billing")
    res, _ = _build_and_walk(tmp_path, "s02", s02)
    record_eval({f.rule_id for f in res.findings}, {"AGT-001"}, "s02")
    assert res.findings[0].confidence == "high"

    # s03: Pure test removal without production change -> AGT-002
    def s03(rb: GitRepoBuilder, _):
        rb.write("tests/test_suite.py", "".join(f"def test_case_{i}():\n    assert calc({i}) == {i * 2}\n\n" for i in range(5)))
        rb.commit("init tests")
        rb.write("tests/test_suite.py", "def test_case_0():\n    assert calc(0) == 0\n")
        rb.commit("drop four tests")
    res, _ = _build_and_walk(tmp_path, "s03", s03)
    record_eval({f.rule_id for f in res.findings}, {"AGT-002"}, "s03")

    # s04: Three tests newly skipped -> AGT-003
    def s04(rb: GitRepoBuilder, _):
        rb.write("tests/test_skips.py", "import pytest\n\ndef test_a():\n    assert fn(1) == 2\n\ndef test_b():\n    assert fn(2) == 3\n\ndef test_c():\n    assert fn(3) == 4\n\ndef test_d():\n    assert fn(4) == 5\n")
        rb.commit("init")
        rb.write("tests/test_skips.py", "import pytest\n\n@pytest.mark.skip\ndef test_a():\n    assert fn(1) == 2\n\n@pytest.mark.skip\ndef test_b():\n    assert fn(2) == 3\n\n@pytest.mark.skip\ndef test_c():\n    assert fn(3) == 4\n\ndef test_d():\n    assert fn(4) == 5\n")
        rb.commit("skip three")
    res, _ = _build_and_walk(tmp_path, "s04", s04)
    record_eval({f.rule_id for f in res.findings}, {"AGT-003"}, "s04")

    # s05: assert True introduced -> AGT-005
    def s05(rb: GitRepoBuilder, _):
        rb.write("tests/test_taut.py", "def test_x():\n    assert fn(2) == 4\n")
        rb.commit("init")
        rb.write("tests/test_taut.py", "def test_x():\n    assert fn(2) == 4\n\ndef test_fake():\n    assert True\n")
        rb.commit("add tautology")
    res, _ = _build_and_walk(tmp_path, "s05", s05)
    record_eval({f.rule_id for f in res.findings}, {"AGT-005"}, "s05")

    # s06: assertEqual -> is not None -> AGT-006 (low)
    def s06(rb: GitRepoBuilder, _):
        rb.write("tests/test_loose.py", "def test_x():\n    res = 42\n    assert res == 42\n")
        rb.commit("init")
        rb.write("tests/test_loose.py", "def test_x():\n    res = 42\n    assert res is not None\n")
        rb.commit("loosen assert")
    res, _ = _build_and_walk(tmp_path, "s06", s06)
    record_eval({f.rule_id for f in res.findings}, {"AGT-006"}, "s06")
    assert res.findings[0].severity == "low"

    # s07: CI step gains continue-on-error: true -> AGT-007
    def s07(rb: GitRepoBuilder, _):
        rb.write(".github/workflows/ci.yml", "on: push\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: pytest\n")
        rb.commit("init ci")
        rb.write(".github/workflows/ci.yml", "on: push\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: pytest\n        continue-on-error: true\n")
        rb.commit("weaken ci")
    res, _ = _build_and_walk(tmp_path, "s07", s07)
    record_eval({f.rule_id for f in res.findings}, {"AGT-007"}, "s07")

    # s08: Coverage threshold 85 -> 40 -> AGT-008
    def s08(rb: GitRepoBuilder, _):
        rb.write("pyproject.toml", "[tool.coverage.report]\nfail_under = 85\n")
        rb.commit("init cov")
        rb.write("pyproject.toml", "[tool.coverage.report]\nfail_under = 40\n")
        rb.commit("lower cov")
    res, _ = _build_and_walk(tmp_path, "s08", s08)
    record_eval({f.rule_id for f in res.findings}, {"AGT-008"}, "s08")

    # s09: Six # noqa added in one commit -> AGT-009 low (and exclude @ts-expect-error)
    def s09(rb: GitRepoBuilder, _):
        rb.write("src/app.py", "x = 1\n")
        rb.commit("init")
        rb.write("src/app.py", "\n".join(f"v{i} = {i}  # noqa: E501" for i in range(6)) + "\n")
        rb.commit("add noqa burst")
    res, _ = _build_and_walk(tmp_path, "s09", s09)
    record_eval({f.rule_id for f in res.findings}, {"AGT-009"}, "s09")
    assert res.findings[0].severity == "low"

    # s10: Secret added in commit 2, removed in commit 3 -> AGT-010, value absent from all outputs
    leaked_secret = "AKIA" + "TESTHIST12345678"
    def s10(rb: GitRepoBuilder, _):
        rb.write("src/cfg.py", "ENV = 'prod'\n")
        rb.commit("init")
        rb.write("src/cfg.py", f"KEY = '{leaked_secret}'\n")
        rb.commit("add secret oops")
        rb.write("src/cfg.py", "ENV = 'prod'\n")
        rb.commit("remove secret")
    res, _ = _build_and_walk(tmp_path, "s10", s10)
    record_eval({f.rule_id for f in res.findings}, {"AGT-010"}, "s10")
    assert leaked_secret not in res.model_dump_json()

    # s11: 1,200-line change, no tests -> AGT-011
    def s11(rb: GitRepoBuilder, _):
        rb.write("src/big.py", "x = 0\n")
        rb.commit("init")
        rb.write("src/big.py", "".join(f"val_{i} = {i}\n" for i in range(1200)))
        rb.commit("huge refactor without tests")
    res, _ = _build_and_walk(tmp_path, "s11", s11)
    record_eval({f.rule_id for f in res.findings}, {"AGT-011"}, "s11")

    # s12: it.only committed and present at HEAD -> AGT-012
    def s12(rb: GitRepoBuilder, _):
        rb.write("tests/ui.test.ts", "it.only('renders', () => { expect(renderApp()).toBe('ok'); });\n")
        rb.commit("focus marker")
    res, _ = _build_and_walk(tmp_path, "s12", s12)
    record_eval({f.rule_id for f in res.findings}, {"AGT-012"}, "s12")

    # s13: Test file MOVED to a new directory -> NO FINDINGS
    def s13(rb: GitRepoBuilder, _):
        rb.write("tests/test_old_loc.py", "def test_feature():\n    val = 10 + 5\n    assert val == 15\n")
        rb.commit("init")
        rb.remove("tests/test_old_loc.py")
        rb.write("tests/unit/test_new_loc.py", "def test_feature():\n    val = 10 + 5\n    assert val == 15\n")
        rb.commit("move test file")
    res, _ = _build_and_walk(tmp_path, "s13", s13)
    record_eval({f.rule_id for f in res.findings}, set(), "s13")

    # s14: Test function RENAMED, same body -> NO FINDINGS
    def s14(rb: GitRepoBuilder, _):
        rb.write("tests/test_ren.py", "def test_old_name():\n    x = 2 * 3\n    assert x == 6\n")
        rb.commit("init")
        rb.write("tests/test_ren.py", "def test_much_better_name():\n    x = 2 * 3\n    assert x == 6\n")
        rb.commit("rename test")
    res, _ = _build_and_walk(tmp_path, "s14", s14)
    record_eval({f.rule_id for f in res.findings}, set(), "s14")

    # s15: Production file and its mapped test both deleted -> NO FINDINGS
    def s15(rb: GitRepoBuilder, _):
        rb.write("src/legacy.py", "def run():\n    return 1\n")
        rb.write("tests/test_legacy.py", "def test_run():\n    assert run() == 1\n")
        rb.commit("init")
        rb.remove("src/legacy.py")
        rb.remove("tests/test_legacy.py")
        rb.commit("retire legacy feature and its tests")
    res, _ = _build_and_walk(tmp_path, "s15", s15)
    record_eval({f.rule_id for f in res.findings}, set(), "s15")

    # s16: Large squash-merge (>40 files) removing tests -> AGT-001/002 confidence capped at medium
    def s16(rb: GitRepoBuilder, _):
        rb.write("src/core.py", "def f():\n    return 1\n")
        rb.write("tests/test_core.py", "def test_f():\n    assert f() == 1\n\ndef test_g():\n    assert g() == 2\n")
        for i in range(42):
            rb.write(f"src/extra_{i}.py", "x = 1\n")
        rb.commit("init many files")
        rb.write("src/core.py", "def f():\n    return 2\n")
        rb.write("tests/test_core.py", "def test_f():\n    assert f() == 1\n")
        for i in range(42):
            rb.write(f"src/extra_{i}.py", "x = 2\n")
        rb.commit("large squash merge")
    res, _ = _build_and_walk(tmp_path, "s16", s16)
    record_eval({f.rule_id for f in res.findings}, {"AGT-001"}, "s16")
    assert res.findings[0].confidence == "medium"

    # s17: Co-Authored-By agent trailer -> attribution trailer/high
    def s17(rb: GitRepoBuilder, _):
        rb.write("a.py", "x = 1\n")
        rb.commit("feat: thing\n\nCo-Authored-By: Claude Sonnet 4 <noreply@anthropic.com>")
    res, _ = _build_and_walk(tmp_path, "s17", s17)
    assert res.commits[0].attribution_basis == "trailer"
    assert res.commits[0].attribution_confidence == "high"
    assert res.attribution["agent_declared_fraction"] == 1.0

    # s18: Bot-account author -> bot_account
    def s18(rb: GitRepoBuilder, _):
        rb.write("a.py", "x = 1\n")
        rb.commit("fix: patch", author_name="devin-ai-integration[bot]", author_email="bot@ex.com")
    res, _ = _build_and_walk(tmp_path, "s18", s18)
    assert res.commits[0].attribution_basis == "bot_account"
    assert res.commits[0].agent_id == "devin"

    # s19: No attribution signals -> unknown, never 'human'
    def s19(rb: GitRepoBuilder, _):
        rb.write("a.py", "x = 1\n")
        rb.commit("plain commit", author_name="Pat", author_email="pat@example.test")
    res, _ = _build_and_walk(tmp_path, "s19", s19)
    assert res.commits[0].agent_id is None
    assert res.commits[0].attribution_basis == "none"
    assert "human" not in json.dumps([c.model_dump() for c in res.commits]).lower()

    # s24: CRLF line endings throughout -> ZERO spurious findings
    def s24(rb: GitRepoBuilder, _):
        rb.write("src/app.py", "def f():\r\n    return 1\r\n")
        rb.write("tests/test_app.py", "def test_f():\r\n    assert f() == 1\r\n")
        rb.commit("init crlf")
        rb.write("src/app.py", "def f():\r\n    return 2\r\n")
        rb.commit("edit prod crlf")
    res, _ = _build_and_walk(tmp_path, "s24", s24)
    record_eval({f.rule_id for f in res.findings}, set(), "s24")

    # s25: Unicode paths and test names -> NO findings
    def s25(rb: GitRepoBuilder, _):
        rb.write("tests/café.test.ts", "test('calculates € total', () => { expect(calcTotal(5)).toBe(5); });\n")
        rb.commit("unicode test")
    res, _ = _build_and_walk(tmp_path, "s25", s25)
    record_eval({f.rule_id for f in res.findings}, set(), "s25")

    # s26: Commit message "fix tests, all passing" removing tests (Modifier M-1 bumps confidence)
    def s26(rb: GitRepoBuilder, _):
        rb.write("src/unrelated.py", "a = 1\n")
        rb.write("tests/test_a.py", "def test_one():\n    assert helper(1) == 2\n\ndef test_two():\n    assert helper(2) == 3\n")
        rb.commit("init")
        rb.write("src/unrelated.py", "a = 2\n")
        rb.write("tests/test_a.py", "def test_one():\n    assert helper(1) == 2\n")
        rb.commit("fix tests, all passing")
    res, _ = _build_and_walk(tmp_path, "s26", s26)
    record_eval({f.rule_id for f in res.findings}, {"AGT-001"}, "s26")
    # Unmapped prod change -> base confidence medium, bumped to high by M-1 claim contradiction!
    assert res.findings[0].confidence == "high"
    assert res.findings[0].params.get("claim_contradiction") is True

    # s27: Agent config files present, zero declared commits
    def s27(rb: GitRepoBuilder, _):
        rb.write("CLAUDE.md", "# instructions\n")
        rb.commit("add repo config")
    res, _ = _build_and_walk(tmp_path, "s27", s27)
    assert res.attribution["tooling_present"] is True
    assert res.attribution["agent_declared_fraction"] == 0.0

    # Assert precision / recall targets
    precision_hv = tp_hv / max(1, tp_hv + fp_hv)
    recall_hv = tp_hv / max(1, tp_hv + fn_hv)
    precision_other = tp_other / max(1, tp_other + fp_other)
    assert precision_hv >= 0.95
    assert recall_hv >= 0.85
    assert precision_other >= 0.90


@given(
    pad=st.integers(min_value=1, max_value=4),
    comment=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789 ", min_size=1, max_size=24),
)
@settings(max_examples=20)
def test_property_body_hash_invariant_under_whitespace_and_comments(pad: int, comment: str):
    """Test metrics & body_hash stay identical across whitespace & comment changes."""
    base_py = "def test_calc():\n    x = 2 + 3\n    assert x == 5\n"
    ind = " " * (pad * 2)
    mod_py = f"def test_calc():\n{ind}# {comment}\n{ind}x  =  2  +  3\n\n{ind}assert  x == 5  # {comment}\n"
    fm1 = extract_test_file_metrics("tests/test_calc.py", base_py)
    fm2 = extract_test_file_metrics("tests/test_calc.py", mod_py)
    assert len(fm1.cases) == 1 and len(fm2.cases) == 1
    assert fm1.cases[0].body_hash == fm2.cases[0].body_hash
    assert fm1.cases[0].assertions == fm2.cases[0].assertions == 1

    base_js = "it('calc', () => {\n  const x = 2 + 3;\n  expect(x).toBe(5);\n});\n"
    mod_js = f"it('calc', () => {{\n{' ' * pad}// {comment}\n  const x = 2 + 3;\n  expect(x).toBe(5);\n}});\n"
    jm1 = extract_test_file_metrics("tests/calc.test.ts", base_js)
    jm2 = extract_test_file_metrics("tests/calc.test.ts", mod_js)
    assert len(jm1.cases) == 1 and len(jm2.cases) == 1
    assert jm1.cases[0].body_hash == jm2.cases[0].body_hash
    assert jm1.cases[0].assertions == jm2.cases[0].assertions == 1
