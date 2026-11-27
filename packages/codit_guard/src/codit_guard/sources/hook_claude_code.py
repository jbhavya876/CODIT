"""
Claude Code PreToolUse hook adapter (P4).

Reads stdin JSON: `tool_name` (`Write`, `Edit`, `MultiEdit`, `Bash`) and `tool_input`.
Returns exit code 2 (with concise explanation on stderr) when a finding matches `hook.block_on`,
exit code 0 to allow, and fails open (exit 0 + log to `.codit/guard.log`) on internal error unless `--strict`.
"""

from __future__ import annotations

import json
import shlex
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from codit_core.classify import is_ci_path, is_test_path
from codit_core.delta import CommitDelta, FileDelta, PolicyThresholds
from codit_core.detectors import run_detectors
from codit_core.detectors.rules_catalog import make_core_finding
from codit_core.findings import CoreFinding
from codit_core.fingerprint import compute_fingerprint, normalize_path
from codit_core.secrets import scan_text

from codit_guard.config import GuardConfig, load_config_from_file
from codit_guard.sources.git_common import build_file_delta

MAX_HOOK_CONTENT_BYTES = 1024 * 1024
_DESTRUCTIVE_VERBS = {"rm", "unlink", "truncate", "mv"}


def _log_hook_note(repo_root: Path, msg: str) -> None:
    try:
        log_dir = repo_root / ".codit"
        log_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with open(log_dir / "guard.log", "a", encoding="utf-8") as fh:
            fh.write(f"[{ts}] {msg}\n")
    except OSError:
        pass


def _is_policy_path(rel_path: str) -> bool:
    norm = normalize_path(rel_path)
    return norm in (".codit.yml", ".codit/baseline.json")


def _rel_to_repo(file_path: str, repo_root: Path) -> str:
    p = Path(file_path)
    if p.is_absolute():
        try:
            return p.resolve().relative_to(repo_root.resolve()).as_posix()
        except ValueError:
            return p.as_posix()
    return normalize_path(file_path)


def _rule_matches_block_on(rule_id: str, block_on: List[str]) -> bool:
    if rule_id in block_on:
        return True
    if rule_id.startswith("SECRET_") and "SEC-SECRET" in block_on:
        return True
    return False


def _apply_edit_text(
    current_text: str,
    old_str: str,
    new_str: str,
    replace_all: bool,
    repo_root: Path,
) -> Optional[str]:
    count = current_text.count(old_str)
    if count == 0:
        _log_hook_note(repo_root, "Edit old_string not found on disk; allowing.")
        return None
    if count > 1 and not replace_all:
        _log_hook_note(repo_root, "Edit old_string matched multiple locations without replace_all; allowing.")
        return None
    if replace_all:
        return current_text.replace(old_str, new_str)
    return current_text.replace(old_str, new_str, 1)


def _check_bash_command(command: str, test_globs: List[str]) -> List[CoreFinding]:
    """
    Best-effort tokenization checking destructive shell commands or redirects
    targeting test/CI/policy paths. Documented as incomplete in `explain GRD-002`.
    """
    if not command or not command.strip():
        return []
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        tokens = command.split()

    targets_found: List[Tuple[str, str]] = []
    # 1. Redirections (> / >> path)
    for idx, tok in enumerate(tokens):
        if tok in (">", ">>", "1>", "1>>") and idx + 1 < len(tokens):
            targets_found.append(("redirect", tokens[idx + 1]))
        elif tok.startswith((">", ">>")) and len(tok) > 1:
            t_path = tok.lstrip(">")
            if t_path:
                targets_found.append(("redirect", t_path))

    # 2. Destructive command verbs (rm, git rm, mv, unlink, truncate, sed -i)
    for idx, tok in enumerate(tokens):
        base_tok = tok.rsplit("/", 1)[-1]
        is_destructive = False
        verb = base_tok
        if base_tok in _DESTRUCTIVE_VERBS:
            is_destructive = True
        elif base_tok == "git" and idx + 1 < len(tokens) and tokens[idx + 1] == "rm":
            is_destructive = True
            verb = "git rm"
        elif base_tok == "sed" and any(t == "-i" or t.startswith("-i") for t in tokens[idx + 1 : idx + 4]):
            is_destructive = True
            verb = "sed -i"

        if is_destructive:
            for arg in tokens[idx + 1 :]:
                if arg in ("&&", "||", ";", "|"):
                    break
                if arg.startswith("-"):
                    continue
                targets_found.append((verb, arg))

    findings: List[CoreFinding] = []
    for verb, raw_target in targets_found:
        norm = normalize_path(raw_target)
        if is_test_path(norm, test_globs=test_globs) or is_ci_path(norm) or _is_policy_path(norm):
            findings.append(
                make_core_finding(
                    rule_id="GRD-002",
                    evidence_file=norm,
                    evidence_line=1,
                    confidence="high",
                    severity="high",
                    basis="PATTERN",
                    match_key=f"{verb}:{norm}",
                    params={"command": verb, "path": norm},
                )
            )
            break
    return findings


def evaluate_claude_hook_payload(
    payload: Dict[str, Any],
    *,
    repo_root: Optional[Path] = None,
    config: Optional[GuardConfig] = None,
) -> Tuple[int, str, List[CoreFinding]]:
    """
    Evaluate a Claude Code PreToolUse JSON payload.
    Returns (exit_code, stderr_message, blocking_findings).
    """
    root = repo_root or Path.cwd()
    cfg = config or load_config_from_file(repo_root=root)
    tool_name = str(payload.get("tool_name") or "")
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return 0, "", []

    if tool_name == "Bash":
        cmd = str(tool_input.get("command") or "")
        hits = _check_bash_command(cmd, cfg.test_globs)
        blocking = [f for f in hits if _rule_matches_block_on(f.rule_id, cfg.block_on)]
        if blocking:
            lines = [f"[codit-guard] BLOCKED {f.rule_id} at {f.evidence_file}: {f.description}" for f in blocking]
            return 2, "\n".join(lines), blocking
        return 0, "", []

    if tool_name not in ("Write", "Edit", "MultiEdit"):
        return 0, "", []

    raw_path = str(tool_input.get("file_path") or "")
    if not raw_path:
        return 0, "", []
    rel_path = _rel_to_repo(raw_path, root)

    # Layer-1 self-protection: block unauthorized policy/baseline edits when enabled
    if cfg.protect_policy and _is_policy_path(rel_path):
        grd = make_core_finding(
            rule_id="GRD-001",
            evidence_file=rel_path,
            evidence_line=1,
            confidence="high",
            severity="high",
            basis="HISTORY PROOF",
            match_key=rel_path,
            params={"path": rel_path},
        )
        if _rule_matches_block_on("GRD-001", cfg.block_on):
            return 2, f"[codit-guard] BLOCKED GRD-001 at {rel_path}: {grd.description}", [grd]

    target_abs = Path(raw_path) if Path(raw_path).is_absolute() else (root / rel_path)
    before_text = ""
    existed = target_abs.is_file()
    if existed:
        try:
            raw_disk = target_abs.read_bytes()
            if len(raw_disk) > MAX_HOOK_CONTENT_BYTES:
                _log_hook_note(root, f"File {rel_path} >1MB; not_assessed, allowing.")
                return 0, "", []
            before_text = raw_disk.decode("utf-8", errors="replace").replace("\r\n", "\n")
        except OSError:
            before_text = ""

    if tool_name == "Write":
        proposed = str(tool_input.get("content") or "")
        if len(proposed.encode("utf-8", errors="replace")) > MAX_HOOK_CONTENT_BYTES:
            _log_hook_note(root, f"Proposed Write content for {rel_path} >1MB; not_assessed, allowing.")
            return 0, "", []
        after_text = proposed.replace("\r\n", "\n")
    elif tool_name == "Edit":
        old_s = str(tool_input.get("old_string") or "").replace("\r\n", "\n")
        new_s = str(tool_input.get("new_string") or "").replace("\r\n", "\n")
        rep_all = bool(tool_input.get("replace_all", False))
        applied = _apply_edit_text(before_text, old_s, new_s, rep_all, root)
        if applied is None:
            return 0, "", []
        after_text = applied
    else:  # MultiEdit
        edits = tool_input.get("edits") or []
        cur_txt = before_text
        for ed in edits:
            if not isinstance(ed, dict):
                continue
            applied = _apply_edit_text(
                cur_txt,
                str(ed.get("old_string") or "").replace("\r\n", "\n"),
                str(ed.get("new_string") or "").replace("\r\n", "\n"),
                bool(ed.get("replace_all", False)),
                root,
            )
            if applied is None:
                return 0, "", []
            cur_txt = applied
        after_text = cur_txt

    status = "M" if existed else "A"
    fd, _tc = build_file_delta(
        path=rel_path,
        old_path=None,
        status=status,
        before_text=before_text,
        after_text=after_text,
        test_globs=cfg.test_globs,
    )

    candidate_findings: List[CoreFinding] = []
    # Check added lines for high-confidence secrets (never printing secret value)
    if fd.added:
        added_snippet = "\n".join(al.text for al in fd.added)
        for sm in scan_text(rel_path, added_snippet):
            real_line = fd.added[sm.line - 1].lineno if 0 < sm.line <= len(fd.added) else sm.line
            fp = compute_fingerprint(sm.rule_id, rel_path, secret_hash=sm.secret_hash)
            candidate_findings.append(
                CoreFinding(
                    id=f"secret-{fp[:8]}-{real_line}",
                    dimension="security",
                    severity=sm.severity,
                    confidence="high",
                    description=f"Potential leaked {sm.secret_type} detected in proposed edit (<redacted:{sm.kind}>).",
                    evidence_file=rel_path,
                    evidence_line=real_line,
                    rule_id=sm.rule_id,
                    remediation="Load credentials from environment variables or a secret manager.",
                    component_id=rel_path,
                    fingerprint=fp,
                    basis="PATTERN",
                    params={"kind": sm.kind},
                )
            )

    cd = CommitDelta(
        sha="0" * 40,
        short="edit",
        date=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        files=(fd,),
        files_changed=1,
        tree_paths=(rel_path,),
    )
    wf_map = {rel_path: after_text} if fd.kind == "ci" else {}
    det_res = run_detectors(
        [cd],
        policy=cfg.thresholds,
        after_all_workflows=wf_map,
        apply_head_rules=False,
    )
    candidate_findings.extend(det_res.findings)

    blocking = [f for f in candidate_findings if _rule_matches_block_on(f.rule_id, cfg.block_on)]
    if blocking:
        msgs = [
            f"[codit-guard] BLOCKED {f.rule_id} ({f.evidence_file}:{f.evidence_line or 1}): {f.description}"
            for f in blocking
        ]
        return 2, "\n".join(msgs), blocking

    return 0, "", []
