"""Trusted local git CLI helpers and shared CommitDelta builder (never shell=True)."""

from __future__ import annotations

import difflib
import fnmatch
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from codit_core.classify import (
    is_ci_path,
    is_gate_config_path,
    is_generated_path,
    is_test_path,
    language_of,
)
from codit_core.delta import AddedLine, CommitDelta, FileDelta, FileMetrics
from codit_core.secrets import scan_text

from codit_guard.cache import cached_test_metrics

MAX_BLOB_BYTES = 1024 * 1024
MAX_CI_GATE_BYTES = 128 * 1024
MAX_DIFF_LINES_PER_FILE = 20_000
_LFS_PREFIX = b"version https://git-lfs.github.com/spec/v1"


class GitSourceError(RuntimeError):
    """Raised when git revision validation or diff execution fails (exit 3)."""


@dataclass
class ChangedEntry:
    status: str  # A, M, D, R
    path: str
    old_path: Optional[str] = None


def run_git(repo_root: Path, args: List[str], *, check: bool = True) -> bytes:
    env = os.environ.copy()
    env["GIT_OPTIONAL_LOCKS"] = "0"
    cmd = ["git", "-c", "core.quotepath=off", *args]
    proc = subprocess.run(
        cmd,
        cwd=str(repo_root),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        check=False,
    )
    if check and proc.returncode != 0:
        err = proc.stderr.decode("utf-8", errors="replace").strip()
        raise GitSourceError(f"git {' '.join(args)} failed: {err}")
    return proc.stdout


def parse_name_status_z(raw: bytes) -> List[ChangedEntry]:
    """Parse `git diff --name-status -M -z` output handling renames and arbitrary filenames."""
    if not raw:
        return []
    tokens = [t.decode("utf-8", errors="surrogateescape") for t in raw.split(b"\x00") if t]
    entries: List[ChangedEntry] = []
    i = 0
    while i < len(tokens):
        code = tokens[i]
        i += 1
        if not code:
            continue
        op = code[0]
        if op in ("R", "C") and i + 1 < len(tokens):
            old_p = tokens[i]
            new_p = tokens[i + 1]
            i += 2
            entries.append(ChangedEntry(status="R" if op == "R" else "A", path=new_p, old_path=old_p if op == "R" else None))
        elif op in ("A", "M", "D", "T") and i < len(tokens):
            p = tokens[i]
            i += 1
            norm_status = "M" if op == "T" else op
            entries.append(ChangedEntry(status=norm_status, path=p))
    return entries


def git_show_bytes(repo_root: Path, spec: str) -> Optional[bytes]:
    res = git_cat_file_batch(repo_root, [spec]).get(spec)
    return res[1] if res else None


def git_cat_file_batch(repo_root: Path, specs: List[str]) -> Dict[str, Tuple[Optional[str], Optional[bytes]]]:
    """
    Fetch `(object_sha, blob_bytes)` for many git object specs in ONE subprocess call.
    Returns `{spec: (sha, data)}` where missing specs or non-blobs map to `(None, None)`.
    """
    if not specs:
        return {}
    env = os.environ.copy()
    env["GIT_OPTIONAL_LOCKS"] = "0"
    stdin_payload = ("\n".join(specs) + "\n").encode("utf-8", errors="surrogateescape")
    proc = subprocess.run(
        ["git", "-c", "core.quotepath=off", "cat-file", "--batch"],
        cwd=str(repo_root),
        env=env,
        input=stdin_payload,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        check=False,
    )
    out: Dict[str, Tuple[Optional[str], Optional[bytes]]] = {}
    buf = proc.stdout
    pos = 0
    for spec in specs:
        nl = buf.find(b"\n", pos)
        if nl == -1:
            out[spec] = (None, None)
            continue
        header = buf[pos:nl].decode("utf-8", errors="replace")
        pos = nl + 1
        if header.endswith(" missing"):
            out[spec] = (None, None)
            continue
        parts = header.split()
        if len(parts) < 3:
            out[spec] = (None, None)
            continue
        obj_sha, obj_type, size_str = parts[0], parts[1], parts[2]
        try:
            size = int(size_str)
        except ValueError:
            out[spec] = (None, None)
            continue
        content = buf[pos : pos + size]
        pos += size
        if pos < len(buf) and buf[pos : pos + 1] == b"\n":
            pos += 1
        if obj_type != "blob":
            out[spec] = (obj_sha, None)
        else:
            out[spec] = (obj_sha, content)
    return out


def git_obj_sha(repo_root: Path, spec: str) -> Optional[str]:
    env = os.environ.copy()
    env["GIT_OPTIONAL_LOCKS"] = "0"
    proc = subprocess.run(
        ["git", "-c", "core.quotepath=off", "rev-parse", "--verify", spec],
        cwd=str(repo_root),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        check=False,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout.decode("utf-8", errors="replace").strip()


def decode_safe_blob(raw: Optional[bytes], path: str, not_assessed: List[Dict[str, Optional[str]]]) -> Optional[str]:
    if raw is None:
        return ""
    if len(raw) > MAX_BLOB_BYTES:
        not_assessed.append({"check": "file_size_cap", "reason": "blob_exceeds_1mb", "path": path})
        return None
    if b"\x00" in raw[:8192]:
        return None
    first_line = raw.split(b"\n", 1)[0].strip()
    if first_line.startswith(_LFS_PREFIX):
        return None
    txt = raw.decode("utf-8", errors="replace")
    if txt.startswith("\ufeff"):
        txt = txt[1:]
    return txt.replace("\r\n", "\n")


def compute_line_delta(before_text: str, after_text: str) -> Tuple[Tuple[AddedLine, ...], Tuple[str, ...], int, int]:
    b_lines = before_text.splitlines()[:MAX_DIFF_LINES_PER_FILE]
    a_lines = after_text.splitlines()[:MAX_DIFF_LINES_PER_FILE]
    matcher = difflib.SequenceMatcher(None, b_lines, a_lines, autojunk=False)
    added_lines: List[AddedLine] = []
    removed_lines: List[str] = []
    added_cnt = 0
    removed_cnt = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in ("replace", "delete"):
            removed_cnt += i2 - i1
            removed_lines.extend(b_lines[i1:i2])
        if tag in ("replace", "insert"):
            added_cnt += j2 - j1
            for offset, text in enumerate(a_lines[j1:j2], start=j1 + 1):
                added_lines.append(AddedLine(lineno=offset, text=text))
    return tuple(added_lines), tuple(removed_lines), added_cnt, removed_cnt


def classify_path(path: str, test_globs: Optional[List[str]] = None) -> str:
    if is_ci_path(path):
        return "ci"
    if is_gate_config_path(path):
        return "gate_config"
    if is_generated_path(path):
        return "generated"
    if is_test_path(path, test_globs=test_globs):
        return "test"
    name = path.replace("\\", "/").lower().rsplit("/", 1)[-1]
    if name in {"package.json", "pyproject.toml", "requirements.txt", "pipfile", "setup.py", "setup.cfg"}:
        return "manifest"
    if language_of(path) is not None:
        return "source"
    return "other"


def is_ignored_by_policy(path: str, ignore_patterns: List[str]) -> bool:
    norm = path.replace("\\", "/")
    for pat in ignore_patterns:
        if fnmatch.fnmatch(norm, pat):
            return True
    return False


def build_file_delta(
    *,
    path: str,
    old_path: Optional[str],
    status: str,
    before_text: str,
    after_text: str,
    before_sha: Optional[str] = None,
    after_sha: Optional[str] = None,
    test_globs: Optional[List[str]] = None,
) -> Tuple[FileDelta, Optional[str]]:
    """Build pure FileDelta + optional test file content for import mapping."""
    kind = classify_path(path, test_globs=test_globs)
    lang = language_of(path)
    added_lines, removed_lines, added_cnt, removed_cnt = compute_line_delta(before_text, after_text)

    before_fm: Optional[FileMetrics] = None
    after_fm: Optional[FileMetrics] = None
    test_content_for_map: Optional[str] = None

    if kind == "test":
        if status in ("M", "D", "R") and before_text:
            before_fm = cached_test_metrics(old_path or path, before_text, blob_sha=before_sha)
            test_content_for_map = before_text
        if status in ("A", "M", "R") and after_text:
            after_fm = cached_test_metrics(path, after_text, blob_sha=after_sha)

    ci_before = before_text if kind in ("ci", "gate_config") and len(before_text.encode("utf-8", "ignore")) <= MAX_CI_GATE_BYTES else None
    ci_after = after_text if kind in ("ci", "gate_config") and len(after_text.encode("utf-8", "ignore")) <= MAX_CI_GATE_BYTES else None

    fd = FileDelta(
        path=path,
        old_path=old_path,
        status=status,  # type: ignore[arg-type]
        kind=kind,      # type: ignore[arg-type]
        language=lang,
        added=added_lines,
        removed_count=removed_cnt,
        added_count=added_cnt,
        removed_lines=removed_lines,
        before=before_fm,
        after=after_fm,
        before_text=ci_before,
        after_text=ci_after,
    )
    return fd, test_content_for_map


def scan_added_secrets_from_deltas(deltas: List[FileDelta]) -> List[Tuple[str, str, str, int, str]]:
    """Return list of (rule_id, kind, path, real_lineno, secret_hash) on added lines."""
    hits: List[Tuple[str, str, str, int, str]] = []
    for fd in deltas:
        if not fd.added:
            continue
        snippet = "\n".join(al.text for al in fd.added)
        for sm in scan_text(fd.path, snippet):
            real_line = fd.added[sm.line - 1].lineno if 0 < sm.line <= len(fd.added) else sm.line
            hits.append((sm.rule_id, sm.kind, fd.path, real_line, sm.secret_hash))
    return hits
