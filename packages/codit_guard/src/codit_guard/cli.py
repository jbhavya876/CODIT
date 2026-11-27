"""
codit-guard CLI entrypoint (stdlib argparse for <= 300ms startup/import budget).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from codit_guard import __version__

_ENFORCEMENT_NOTICE = """
Enforcement layers (honest boundary disclosure):
  1. Agent hook (Claude Code PreToolUse): shortens feedback loop; an agent can use unmatched tools.
  2. Commit hook (git / pre-commit): blocks local commits; bypassable via `git commit --no-verify`.
  3. CI check (GitHub Action required check): AUTHORITATIVE gate on protected branches.
Only layer 3, configured as a required status check, is authoritative. Never claim an agent cannot bypass layers 1 or 2.

Network and privacy:
  The only network calls are optional advisory lookups (OSV querybatch for newly added/changed packages)
  carrying `(ecosystem, name, version)` only, with a 2 s budget that fails open. Use `--offline` for zero network calls.
"""

_SEV_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}


def _evaluate_findings_for_deltas(
    deltas: List[Any],
    *,
    cfg: Any,
    test_contents_by_commit: Dict[str, Dict[str, str]],
    after_workflows: Dict[str, str],
    offline: bool,
    not_assessed: List[Dict[str, Optional[str]]],
) -> List[Any]:
    from codit_core.detectors import run_detectors
    from codit_core.detectors.rules_catalog import make_core_finding
    from codit_core.findings import CoreFinding
    from codit_core.fingerprint import compute_fingerprint, normalize_path
    from codit_guard.advisories import lookup_added_advisories
    from codit_guard.sources.git_common import scan_added_secrets_from_deltas
    det_res = run_detectors(
        deltas,
        policy=cfg.thresholds,
        after_all_workflows=after_workflows,
        test_contents_by_commit=test_contents_by_commit,
        apply_head_rules=False,
    )
    all_findings: List[CoreFinding] = list(det_res.findings)

    # Check added secrets across deltas (redacted value only)
    for cd in deltas:
        for rule_id, kind, path, lineno, secret_hash in scan_added_secrets_from_deltas(list(cd.files)):
            fp = compute_fingerprint(rule_id, path, secret_hash=secret_hash)
            all_findings.append(
                CoreFinding(
                    id=f"secret-{fp[:8]}-{lineno}",
                    dimension="security",
                    severity="critical" if kind in ("AWS_KEY", "PRIVATE_KEY", "STRIPE_SECRET", "GITHUB_TOKEN") else "high",
                    confidence="high",
                    description=f"Potential leaked credential (<redacted:{kind}>) introduced in change.",
                    evidence_file=path,
                    evidence_line=lineno,
                    rule_id=rule_id,
                    remediation="Remove the secret and rotate it immediately.",
                    component_id=path,
                    fingerprint=fp,
                    basis="PATTERN",
                    commit_sha=cd.sha if cd.sha != "0" * 40 else None,
                    params={"kind": kind},
                )
            )

        # GRD-001 policy/baseline edits & AGT-012 focus markers in modified/added test files
        for fd in cd.files:
            norm = normalize_path(fd.path)
            if cfg.protect_policy and norm in (".codit.yml", ".codit/baseline.json"):
                all_findings.append(
                    make_core_finding(
                        rule_id="GRD-001",
                        evidence_file=fd.path,
                        evidence_line=1,
                        confidence="high",
                        severity="high",
                        basis="HISTORY PROOF",
                        commit_sha=cd.sha if cd.sha != "0" * 40 else None,
                        match_key=fd.path,
                        params={"path": fd.path},
                    )
                )
            if fd.kind == "test" and fd.after is not None:
                before_foc = {c.name for c in (fd.before.cases if fd.before else ()) if c.focused}
                for case in fd.after.cases:
                    if case.focused and case.name not in before_foc:
                        all_findings.append(
                            make_core_finding(
                                rule_id="AGT-012",
                                evidence_file=fd.path,
                                evidence_line=case.line,
                                confidence="high",
                                severity="medium",
                                basis="AST PROOF",
                                commit_sha=cd.sha if cd.sha != "0" * 40 else None,
                                match_key=f"{fd.path}:{case.name}",
                                params={"form": ".only/fit/fdescribe", "path": fd.path},
                            )
                        )

    # Optional advisory lookup (fail-open, coordinates only)
    if cfg.checks_advisories_enabled if hasattr(cfg, "checks_advisories_enabled") else cfg.advisories == "warn":
        adv_findings, adv_na = lookup_added_advisories(deltas, offline=offline)
        all_findings.extend(adv_findings)
        not_assessed.extend(adv_na)

    return all_findings


def _filter_suppressed_and_baselined(
    findings: List[Any],
    cfg: Any,
    baseline_fps: Set[str],
    *,
    use_baseline: bool,
) -> Tuple[List[Any], int, int]:
    kept: List[CoreFinding] = []
    baselined_count = 0
    suppressed_count = 0
    for f in findings:
        if f.fingerprint in cfg.active_suppressions:
            suppressed_count += 1
            continue
        if use_baseline and f.fingerprint in baseline_fps:
            baselined_count += 1
            continue
        kept.append(f)
    return kept, baselined_count, suppressed_count


def _should_fail(findings: List[Any], fail_on: str) -> bool:
    if fail_on == "never":
        return False
    min_rank = _SEV_RANK.get(fail_on, 3)
    return any(_SEV_RANK.get(f.severity, 0) >= min_rank for f in findings)


def _paths_to_delta(repo_root: Path, paths: List[str], test_globs: List[str]) -> Any:
    from codit_core.delta import CommitDelta
    from codit_guard.sources.git_common import build_file_delta
    fds = []
    for raw_p in paths:
        p = Path(raw_p)
        target = p if p.is_absolute() else (repo_root / p)
        if not target.is_file():
            continue
        try:
            rel = target.resolve().relative_to(repo_root.resolve()).as_posix()
        except ValueError:
            rel = target.as_posix()
        text = target.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
        fd, _ = build_file_delta(
            path=rel,
            old_path=None,
            status="A",
            before_text="",
            after_text=text,
            test_globs=test_globs,
        )
        fds.append(fd)
    return CommitDelta(
        sha="0" * 40,
        short="paths",
        date=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        files=tuple(fds),
        files_changed=len(fds),
        tree_paths=tuple(fd.path for fd in fds),
    )


def _cmd_check(args: argparse.Namespace) -> int:
    from codit_guard.baseline import load_baseline_from_disk
    from codit_guard.config import GuardConfigError, load_config_from_file
    from codit_guard.report_text import format_text_report
    from codit_guard.sarif import build_sarif
    from codit_guard.sources.git_common import GitSourceError
    from codit_guard.sources.git_range import (
        load_trusted_base_policy,
        read_range_commit_deltas,
        verify_range_refs,
    )
    from codit_guard.sources.git_staged import read_staged_commit_delta

    t0 = time.monotonic()
    repo_root = Path.cwd()
    not_assessed: List[Dict[str, Optional[str]]] = []

    if args.base and not args.head or args.head and not args.base:
        print("Error: --base and --head must be specified together.", file=sys.stderr)
        return 3

    base_ref: Optional[str] = args.base
    head_ref: Optional[str] = args.head

    try:
        if base_ref and head_ref:
            base_sha, head_sha = verify_range_refs(repo_root, base_ref, head_ref)
            if args.config:
                cfg = load_config_from_file(path=Path(args.config), repo_root=repo_root)
                baseline_fps = load_baseline_from_disk(repo_root)
            else:
                cfg, baseline_fps = load_trusted_base_policy(repo_root, base_sha)
            scope = args.scope or "net"
            deltas, tcbc, after_workflows = read_range_commit_deltas(
                repo_root,
                base_sha,
                head_sha,
                scope=scope,
                ignore_paths=cfg.ignore_paths,
                test_globs=cfg.test_globs,
                not_assessed=not_assessed,
            )
        elif args.paths:
            cfg = load_config_from_file(path=Path(args.config) if args.config else None, repo_root=repo_root)
            baseline_fps = load_baseline_from_disk(repo_root)
            scope = "paths"
            cd = _paths_to_delta(repo_root, args.paths, cfg.test_globs)
            deltas, tcbc, after_workflows = [cd], {}, {}
        else:
            # Default to staged diff (--staged)
            cfg = load_config_from_file(path=Path(args.config) if args.config else None, repo_root=repo_root)
            baseline_fps = load_baseline_from_disk(repo_root)
            scope = "staged"
            cd, tc, after_workflows = read_staged_commit_delta(
                repo_root,
                ignore_paths=cfg.ignore_paths,
                test_globs=cfg.test_globs,
                not_assessed=not_assessed,
            )
            deltas = [cd]
            tcbc = {cd.sha: tc} if tc else {}
    except (GuardConfigError, GitSourceError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 3
    except Exception as exc:
        print(f"Internal error: {exc}", file=sys.stderr)
        return 4

    raw_findings = _evaluate_findings_for_deltas(
        deltas,
        cfg=cfg,
        test_contents_by_commit=tcbc,
        after_workflows=after_workflows,
        offline=bool(args.offline),
        not_assessed=not_assessed,
    )
    kept_findings, baselined_cnt, suppressed_cnt = _filter_suppressed_and_baselined(
        raw_findings,
        cfg,
        baseline_fps,
        use_baseline=not args.no_baseline,
    )

    fail_threshold = args.fail_on or cfg.fail_on
    duration_ms = max(0, int((time.monotonic() - t0) * 1000))

    result_obj: Dict[str, Any] = {
        "schema": "codit.guard.result.v1",
        "tool": f"codit-guard/{__version__}",
        "scope": scope,
        "base": base_ref,
        "head": head_ref,
        "config_source": cfg.source,
        "findings": [
            {
                "id": f.id,
                "rule_id": f.rule_id,
                "dimension": f.dimension,
                "severity": f.severity,
                "confidence": f.confidence,
                "basis": f.basis,
                "evidence_file": f.evidence_file,
                "evidence_line": f.evidence_line,
                "commit_sha": f.commit_sha,
                "fingerprint": f.fingerprint,
                "description": f.description,
                "remediation": f.remediation,
            }
            for f in kept_findings
        ],
        "baselined_count": baselined_cnt,
        "suppressed_count": suppressed_cnt,
        "expired_suppressions": cfg.expired_suppressions,
        "not_assessed": not_assessed,
        "duration_ms": duration_ms,
    }

    if args.format == "json":
        rendered = json.dumps(result_obj, indent=2) + "\n"
    elif args.format == "sarif":
        rendered = json.dumps(build_sarif(kept_findings), indent=2) + "\n"
    else:
        rendered = format_text_report(result_obj) + "\n"

    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)

    return 1 if _should_fail(kept_findings, fail_threshold) else 0


def _cmd_hook(args: argparse.Namespace) -> int:
    from codit_guard.sources.hook_claude_code import _log_hook_note, evaluate_claude_hook_payload

    repo_root = Path.cwd()
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
        if not isinstance(payload, dict):
            return 0
        code, stderr_msg, _ = evaluate_claude_hook_payload(payload, repo_root=repo_root)
        if code == 2 and stderr_msg:
            sys.stderr.write(stderr_msg + "\n")
        return code
    except Exception as exc:
        _log_hook_note(repo_root, f"Internal hook error: {exc}")
        if getattr(args, "strict", False):
            sys.stderr.write(f"codit-guard hook internal error: {exc}\n")
            return 4
        return 0


def _cmd_install(args: argparse.Namespace) -> int:
    from codit_guard.install import (
        install_claude_code_hook,
        install_git_pre_commit_hook,
        install_pre_commit_config,
    )

    repo_root = Path.cwd()
    if not args.agent and not args.git_hook and not args.pre_commit:
        print("Specify at least one target: --agent claude-code, --git-hook, or --pre-commit.", file=sys.stderr)
        return 3
    if args.agent == "claude-code":
        p = install_claude_code_hook(repo_root)
        print(f"Installed Claude Code PreToolUse hook in {p}")
    elif args.agent:
        print(f"Unsupported agent: {args.agent}", file=sys.stderr)
        return 3
    if args.git_hook:
        p = install_git_pre_commit_hook(repo_root)
        print(f"Installed git pre-commit hook in {p}")
    if args.pre_commit:
        p = install_pre_commit_config(repo_root)
        print(f"Updated pre-commit configuration in {p}")
    return 0


def _cmd_baseline(args: argparse.Namespace) -> int:
    from codit_guard.baseline import save_baseline
    from codit_guard.config import load_config_from_file
    from codit_guard.sources.git_staged import read_staged_commit_delta

    repo_root = Path.cwd()
    try:
        cfg = load_config_from_file(repo_root=repo_root)
        not_assessed: List[Dict[str, Optional[str]]] = []
        cd, tc, wf = read_staged_commit_delta(
            repo_root,
            ignore_paths=cfg.ignore_paths,
            test_globs=cfg.test_globs,
            not_assessed=not_assessed,
        )
        findings = _evaluate_findings_for_deltas(
            [cd],
            cfg=cfg,
            test_contents_by_commit={cd.sha: tc} if tc else {},
            after_workflows=wf,
            offline=True,
            not_assessed=not_assessed,
        )
        merge = args.baseline_action == "update"
        bp = save_baseline(repo_root, findings, merge_existing=merge)
        print(f"Baseline {'updated' if merge else 'created'} at {bp} ({len(findings)} staged finding(s)).")
        return 0
    except Exception as exc:
        print(f"Error creating baseline: {exc}", file=sys.stderr)
        return 3


def _cmd_explain(args: argparse.Namespace) -> int:
    from codit_guard.report_text import format_rule_explanation

    text = format_rule_explanation(args.rule_id)
    if not text:
        print(f"Unknown rule ID: {args.rule_id}", file=sys.stderr)
        return 3
    print(text)
    return 0


def _cmd_attest(args: argparse.Namespace) -> int:
    from codit_guard.verify_attestation import verify_attestation_file

    if args.attest_action != "verify":
        return 3
    att_file = Path(args.file)
    if not att_file.is_file():
        print(f"Attestation file not found: {att_file}", file=sys.stderr)
        return 3
    ok, msg = verify_attestation_file(
        att_file,
        keys_source=args.keys,
        revocations_source=args.revocations,
    )
    print(msg)
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codit-guard",
        description="Local-first diff-level assurance gate for AI-written code.",
        epilog=_ENFORCEMENT_NOTICE,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_check = sub.add_parser("check", help="Evaluate staged, range, or file changes.")
    p_check.add_argument("--staged", action="store_true", help="Inspect staged git diff.")
    p_check.add_argument("--base", help="Base git ref for PR/range check.")
    p_check.add_argument("--head", help="Head git ref for PR/range check.")
    p_check.add_argument("--paths", nargs="+", help="Explicit file paths to inspect.")
    p_check.add_argument("--scope", choices=["net", "per-commit"], default="net")
    p_check.add_argument("--format", choices=["text", "json", "sarif"], default="text")
    p_check.add_argument("--output", help="Write report to FILE instead of stdout.")
    p_check.add_argument("--config", help="Path to .codit.yml (ignored when --base/--head trusts base).")
    p_check.add_argument("--offline", action="store_true", help="Disable all optional advisory network calls.")
    p_check.add_argument("--fail-on", choices=["critical", "high", "medium", "never"], default=None)
    p_check.add_argument("--no-baseline", action="store_true", help="Ignore .codit/baseline.json.")
    p_check.set_defaults(func=_cmd_check)

    p_hook = sub.add_parser("hook", help="Agent PreToolUse hook adapter.")
    p_hook.add_argument("agent_name", choices=["claude-code"])
    p_hook.add_argument("--strict", action="store_true", help="Exit 4 instead of failing open on internal error.")
    p_hook.set_defaults(func=_cmd_hook)

    p_install = sub.add_parser("install", help="Install agent or git hooks cleanly.")
    p_install.add_argument("--agent", choices=["claude-code"])
    p_install.add_argument("--git-hook", action="store_true")
    p_install.add_argument("--pre-commit", action="store_true")
    p_install.set_defaults(func=_cmd_install)

    p_base = sub.add_parser("baseline", help="Create or update .codit/baseline.json.")
    p_base.add_argument("baseline_action", choices=["create", "update"])
    p_base.set_defaults(func=_cmd_baseline)

    p_exp = sub.add_parser("explain", help="Print rationale, example, and remediation for RULE_ID.")
    p_exp.add_argument("rule_id")
    p_exp.set_defaults(func=_cmd_explain)

    p_att = sub.add_parser("attest", help="Verify signed codit.attestation.v1 files.")
    att_sub = p_att.add_subparsers(dest="attest_action", required=True)
    p_ver = att_sub.add_parser("verify", help="Verify an attestation JSON offline or online.")
    p_ver.add_argument("file", help="Path to signed attestation JSON file.")
    p_ver.add_argument("--keys", required=True, help="URL or local path to codit-keys.json.")
    p_ver.add_argument("--revocations", default=None, help="Optional URL or file to codit-revocations.json.")
    p_att.set_defaults(func=_cmd_attest)

    p_ver_cmd = sub.add_parser("version", help="Print codit-guard version.")
    p_ver_cmd.set_defaults(func=lambda _a: (print(f"codit-guard {__version__}"), 0)[1])

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = int(exc.code) if exc.code is not None else 0
        # Argparse usage errors return 2; normalize to CLI contract 3
        return 0 if code == 0 else 3
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
