"""
Pure-Python git history walker using `dulwich` + `codit_core` detectors (P1-P3).

NEVER invokes the `git` CLI on target directories.
Decodes paths safely without filesystem path joins, evaluates attribution &
process-integrity detectors inside the isolated worker, and strips all commit
messages, author names, emails, and source text before emitting JSON.
"""

from __future__ import annotations

import difflib
import hashlib
import hmac
import logging
import os
import re
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from dulwich.diff_tree import RenameDetector, TreeChange, tree_changes
from dulwich.errors import NotCommitError
from dulwich.objects import Blob, Commit, Tree
from dulwich.repo import Repo

from codit_core.attribution import (
    ATTRIBUTION_LIMITATION,
    attribute_commit,
    load_signatures_config,
)
from codit_core.classify import (
    is_ci_path,
    is_gate_config_path,
    is_generated_path,
    is_test_path,
    language_of,
)
from codit_core.delta import AddedLine, CommitDelta, FileDelta, FileMetrics, PolicyThresholds, TestCaseMetric
from codit_core.detectors import run_detectors
from codit_core.secrets import scan_text
from codit_core.testmetrics import ANALYZER_VERSION, extract_test_file_metrics

from backend.app.config import Config
from backend.app.history.blob_cache import get_cached_blob_metrics, put_cached_blob_metrics
from backend.app.history.models import (
    CommitRecord,
    HistoryCoverage,
    HistoryFindingRecord,
    HistoryOptions,
    HistoryResult,
)

log = logging.getLogger(__name__)

_GITLINK_MODE = 0o160000
_SYMLINK_MODE = 0o120000
_MAX_DIFF_LINES_PER_FILE = 20_000
_MAX_CI_GATE_BYTES = 128 * 1024
_LFS_PREFIX = b"version https://git-lfs.github.com/spec/v1"

_CLAIM_PATTERNS = [
    re.compile(
        r"\b(fix(e[sd])?|make|made|get|got|ensure[sd]?|all)\b[^.\n]{0,40}\btests?\b[^.\n]{0,20}\b(pass(ing|es|ed)?|green)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\btests? (now )?pass(ing)?\b", re.IGNORECASE),
    re.compile(r"\bci (is )?(now )?(green|passing)\b", re.IGNORECASE),
]

_EMAIL_RE = re.compile(rb"<([^<>]+)>")


def _safe_decode_tree_path(raw: Optional[bytes]) -> Optional[str]:
    """Decode raw git tree path bytes safely, rejecting '..', NUL, and absolute prefixes."""
    if raw is None:
        return None
    if b"\x00" in raw:
        raise ValueError("NUL byte in tree entry path")
    decoded = raw.decode("utf-8", errors="surrogateescape")
    if decoded.startswith(("/", "\\")):
        raise ValueError("Absolute path in tree entry")
    if len(decoded) >= 2 and decoded[1] == ":" and decoded[0].isalpha():
        raise ValueError("Drive-prefixed path in tree entry")
    norm = decoded.replace("\\", "/")
    if ".." in norm.split("/"):
        raise ValueError("Traversal segment '..' in tree entry")
    out_chars: list[str] = []
    for ch in norm:
        cp = ord(ch)
        if 0xD800 <= cp <= 0xDFFF or cp < 32 or cp == 127:
            out_chars.append(f"\\x{cp & 0xFF:02x}")
        else:
            out_chars.append(ch)
    return "".join(out_chars)


def _classify_path(path: str, test_globs: Optional[List[str]] = None) -> str:
    if is_ci_path(path):
        return "ci"
    if is_gate_config_path(path):
        return "gate_config"
    if is_generated_path(path):
        return "generated"
    if is_test_path(path, test_globs=test_globs):
        return "test"
    norm = path.lower()
    name = norm.rsplit("/", 1)[-1]
    if name in {"package.json", "pyproject.toml", "requirements.txt", "pipfile", "setup.py", "setup.cfg"}:
        return "manifest"
    if language_of(path) is not None:
        return "source"
    return "other"


def _extract_email_bytes(author_field: bytes) -> bytes:
    m = _EMAIL_RE.search(author_field or b"")
    if m:
        return m.group(1).strip().lower()
    return (author_field or b"unknown").strip().lower()


def _claims_tests_pass(message_text: str) -> bool:
    head = (message_text or "")[:500]
    return any(p.search(head) for p in _CLAIM_PATTERNS)


def _format_iso_utc(timestamp: int) -> str:
    return datetime.fromtimestamp(int(timestamp), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_shallow_shas(repo: Repo) -> Set[bytes]:
    shallow_set: Set[bytes] = set()
    dot_git = Path(repo.path)
    for p in (dot_git / "shallow", dot_git / ".git" / "shallow"):
        if p.is_file():
            for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                h = line.strip()
                if len(h) == 40:
                    shallow_set.add(h.encode("ascii"))
    return shallow_set


def _read_blob_text(
    store,
    obj_id: Optional[bytes],
    max_blob_bytes: int,
    stats_counters: Dict[str, Any],
) -> Optional[str]:
    if not obj_id:
        return ""
    try:
        obj = store[obj_id]
    except KeyError:
        stats_counters["blobs_unavailable"] += 1
        return None
    if not isinstance(obj, Blob):
        return None
    data = obj.data
    if len(data) > max_blob_bytes:
        stats_counters["caps_hit"].add("blob_size_cap")
        return None
    if b"\x00" in data[:8192]:
        return None
    first_line = data.split(b"\n", 1)[0].strip()
    if first_line.startswith(_LFS_PREFIX):
        return None
    return data.decode("utf-8", errors="replace").replace("\r\n", "\n")


def _cached_test_metrics(path: str, blob_sha: Optional[str], text: Optional[str]) -> Optional[FileMetrics]:
    if text is None:
        return FileMetrics(metrics_unavailable=True)
    if blob_sha:
        cached = get_cached_blob_metrics(blob_sha, ANALYZER_VERSION)
        if cached is not None:
            return FileMetrics(
                cases=tuple(TestCaseMetric(**c) for c in cached.get("cases", [])),
                unsupported_framework=bool(cached.get("unsupported_framework", False)),
                metrics_unavailable=bool(cached.get("metrics_unavailable", False)),
            )
    fm = extract_test_file_metrics(path, text)
    if blob_sha:
        put_cached_blob_metrics(
            blob_sha,
            ANALYZER_VERSION,
            {
                "cases": [asdict(c) for c in fm.cases],
                "unsupported_framework": fm.unsupported_framework,
                "metrics_unavailable": fm.metrics_unavailable,
            },
        )
    return fm


def _compute_line_delta(before_text: str, after_text: str) -> Tuple[Tuple[AddedLine, ...], Tuple[str, ...], int, int]:
    b_lines = before_text.splitlines()[:_MAX_DIFF_LINES_PER_FILE]
    a_lines = after_text.splitlines()[:_MAX_DIFF_LINES_PER_FILE]

    # Fast O(N) common prefix/suffix trim before difflib to avoid quadratic SequenceMatcher stalls.
    prefix = 0
    min_len = min(len(b_lines), len(a_lines))
    while prefix < min_len and b_lines[prefix] == a_lines[prefix]:
        prefix += 1

    b_end = len(b_lines)
    a_end = len(a_lines)
    while b_end > prefix and a_end > prefix and b_lines[b_end - 1] == a_lines[a_end - 1]:
        b_end -= 1
        a_end -= 1

    mid_b = b_lines[prefix:b_end]
    mid_a = a_lines[prefix:a_end]
    if not mid_b and not mid_a:
        return (), (), 0, 0

    added_lines: List[AddedLine] = []
    removed_lines: List[str] = []
    added_count = 0
    removed_count = 0

    if len(mid_b) * len(mid_a) <= 1_000_000 and (len(mid_b) + len(mid_a)) <= 4_000:
        matcher = difflib.SequenceMatcher(None, mid_b, mid_a, autojunk=False)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag in ("replace", "delete"):
                removed_count += i2 - i1
                removed_lines.extend(mid_b[i1:i2])
            if tag in ("replace", "insert"):
                added_count += j2 - j1
                for offset, text in enumerate(mid_a[j1:j2], start=prefix + j1 + 1):
                    added_lines.append(AddedLine(lineno=offset, text=text))
    else:
        from collections import Counter

        a_counts = Counter(mid_a)
        b_counts = Counter(mid_b)
        for line in mid_b:
            if a_counts[line] > 0:
                a_counts[line] -= 1
            else:
                removed_count += 1
                removed_lines.append(line)
        for offset, line in enumerate(mid_a, start=prefix + 1):
            if b_counts[line] > 0:
                b_counts[line] -= 1
            else:
                added_count += 1
                added_lines.append(AddedLine(lineno=offset, text=line))

    return tuple(added_lines), tuple(removed_lines), added_count, removed_count


def _scan_head_tree(
    store,
    tree_id: Optional[bytes],
    max_blob_bytes: int,
    test_globs: Optional[List[str]] = None,
) -> Tuple[
    Dict[str, bool],
    List[Dict[str, Any]],
    Dict[str, FileMetrics],
    Dict[str, str],
    Tuple[str, ...],
]:
    sig_cfg = load_signatures_config()
    tooling: Dict[str, bool] = {t: False for t in sig_cfg["tooling_files"]}
    secrets_at_head: List[Dict[str, Any]] = []
    head_test_metrics: Dict[str, FileMetrics] = {}
    head_workflows: Dict[str, str] = {}
    all_paths: List[str] = []

    if not tree_id:
        return tooling, secrets_at_head, head_test_metrics, head_workflows, ()

    try:
        stack: List[Tuple[str, bytes]] = [("", tree_id)]
        visited: Set[bytes] = set()
        while stack:
            prefix, tid = stack.pop()
            if tid in visited:
                continue
            visited.add(tid)
            try:
                tree_obj = store[tid]
            except KeyError:
                continue
            if not isinstance(tree_obj, Tree):
                continue
            for entry in tree_obj.items():
                if (entry.mode or 0) in (_GITLINK_MODE, _SYMLINK_MODE):
                    continue
                try:
                    name = _safe_decode_tree_path(entry.path)
                except ValueError:
                    continue
                if not name:
                    continue
                full_path = f"{prefix}/{name}" if prefix else name
                if entry.mode == 0o040000:
                    if full_path in tooling:
                        tooling[full_path] = True
                    stack.append((full_path, entry.sha))
                else:
                    all_paths.append(full_path)
                    if full_path in tooling:
                        tooling[full_path] = True
                    elif full_path.startswith(".cursor/rules/") and ".cursor/rules" in tooling:
                        tooling[".cursor/rules"] = True

                    try:
                        blob = store[entry.sha]
                    except KeyError:
                        continue
                    if not isinstance(blob, Blob) or len(blob.data) > max_blob_bytes or b"\x00" in blob.data[:8192]:
                        continue
                    text = blob.data.decode("utf-8", errors="replace").replace("\r\n", "\n")

                    for m in scan_text(full_path, text):
                        secrets_at_head.append({
                            "path": full_path,
                            "kind": m.kind,
                            "rule_id": m.rule_id,
                            "secret_hash": m.secret_hash,
                            "line": m.line,
                        })

                    if is_test_path(full_path, test_globs=test_globs):
                        blob_hex = entry.sha.decode("ascii")
                        fm = _cached_test_metrics(full_path, blob_hex, text)
                        if fm is not None:
                            head_test_metrics[full_path] = fm

                    lower_p = full_path.lower()
                    if lower_p.startswith(".github/workflows/") and lower_p.endswith((".yml", ".yaml")):
                        if len(blob.data) <= _MAX_CI_GATE_BYTES:
                            head_workflows[full_path] = text
    except Exception as exc:
        log.debug("HEAD tree scan error: %s", exc)

    return tooling, secrets_at_head, head_test_metrics, head_workflows, tuple(all_paths)


def _walk_tree_paths(store, tree_id: Optional[bytes]) -> Tuple[str, ...]:
    if not tree_id:
        return ()
    paths: List[str] = []
    stack: List[Tuple[str, bytes]] = [("", tree_id)]
    visited: Set[bytes] = set()
    while stack:
        prefix, tid = stack.pop()
        if tid in visited:
            continue
        visited.add(tid)
        try:
            tree_obj = store[tid]
        except KeyError:
            continue
        if not isinstance(tree_obj, Tree):
            continue
        for entry in tree_obj.items():
            if (entry.mode or 0) in (_GITLINK_MODE, _SYMLINK_MODE):
                continue
            try:
                name = _safe_decode_tree_path(entry.path)
            except ValueError:
                continue
            if not name:
                continue
            full_path = f"{prefix}/{name}" if prefix else name
            if entry.mode == 0o040000:
                stack.append((full_path, entry.sha))
            else:
                paths.append(full_path)
    return tuple(paths)


def walk_history(
    repo_path: Path,
    options: Optional[HistoryOptions] = None,
    *,
    test_globs: Optional[List[str]] = None,
    policy: Optional[PolicyThresholds] = None,
) -> HistoryResult:
    """
    Walk first-parent git history using `dulwich`, execute attribution and `codit_core`
    process-integrity detectors, and emit a sanitized HistoryResult.
    """
    opts = options or HistoryOptions()
    if not opts.enabled:
        return HistoryResult(coverage=HistoryCoverage(assessed=False, reason="history_disabled"))

    max_commits = max(1, min(opts.max_commits, Config.HISTORY_MAX_COMMITS))
    max_days = max(1, min(opts.max_days, Config.HISTORY_MAX_DAYS))
    max_files_per_commit = Config.HISTORY_MAX_FILES_PER_COMMIT
    max_blob_bytes = Config.HISTORY_MAX_BLOB_KB * 1024

    try:
        repo = Repo(str(repo_path))
    except Exception as exc:
        log.warning("Could not open git repository via dulwich: %s", exc)
        return HistoryResult(coverage=HistoryCoverage(assessed=False, reason="invalid_git_repository"))

    try:
        try:
            head_sha = repo.head()
            head_obj = repo.object_store[head_sha]
            if not isinstance(head_obj, Commit):
                return HistoryResult(coverage=HistoryCoverage(assessed=False, reason="invalid_head"))
        except (KeyError, NotCommitError):
            return HistoryResult(coverage=HistoryCoverage(assessed=False, reason="no_commits"))

        store = repo.object_store
        shallow_shas = _load_shallow_shas(repo)
        head_time = int(head_obj.commit_time)
        min_commit_time = head_time - (max_days * 86400)
        head_commit_hex = head_sha.decode("ascii")
        head_tree_hex = head_obj.tree.decode("ascii")

        chain: List[Commit] = []
        cur: Optional[Commit] = head_obj
        caps_hit: Set[str] = set()
        shallow_boundary = False
        visible_count = 0

        while cur is not None:
            visible_count += 1
            if int(cur.commit_time) < min_commit_time and len(chain) > 0:
                caps_hit.add("max_days")
                break
            chain.append(cur)
            if len(chain) >= max_commits:
                if cur.parents:
                    caps_hit.add("max_commits")
                break
            if not cur.parents:
                break
            parent_sha = cur.parents[0]
            try:
                parent_obj = store[parent_sha]
                if not isinstance(parent_obj, Commit):
                    shallow_boundary = True
                    break
                cur = parent_obj
            except KeyError:
                shallow_boundary = True
                break

        if head_sha in shallow_shas:
            shallow_boundary = True

        chain.reverse()

        per_audit_salt = os.urandom(32)
        stats_counters: Dict[str, Any] = {
            "blobs_unavailable": 0,
            "caps_hit": caps_hit,
        }
        skipped_deep_commits = 0
        commit_records: List[CommitRecord] = []
        commit_deltas: List[CommitDelta] = []
        test_contents_by_commit: Dict[str, Dict[str, str]] = {}
        author_counts: Dict[str, int] = {}
        dir_authors: Dict[str, Set[str]] = {}
        declared_commits = 0

        rename_detector = RenameDetector(store, rename_threshold=60, max_files=max(max_files_per_commit, 200))

        for commit in chain:
            sha_hex = commit.id.decode("ascii")
            short_hex = sha_hex[:7]
            iso_date = _format_iso_utc(commit.commit_time)
            author_raw = (commit.author or b"").decode("utf-8", errors="replace")
            email_bytes = _extract_email_bytes(commit.author)
            author_key = hmac.new(per_audit_salt, email_bytes, hashlib.sha256).hexdigest()[:12]
            author_counts[author_key] = author_counts.get(author_key, 0) + 1

            msg_text = (commit.message or b"").decode("utf-8", errors="replace")
            claims_pass = _claims_tests_pass(msg_text)
            att = attribute_commit(msg_text, author_raw)
            del msg_text, author_raw
            if att.agent_id is not None:
                declared_commits += 1

            is_shallow_commit = False
            prev_tree_id: Optional[bytes] = None
            if commit.id in shallow_shas and commit.parents:
                is_shallow_commit = True
                shallow_boundary = True
            elif commit.parents:
                try:
                    p_obj = store[commit.parents[0]]
                    if isinstance(p_obj, Commit):
                        prev_tree_id = p_obj.tree
                    else:
                        is_shallow_commit = True
                        shallow_boundary = True
                except KeyError:
                    is_shallow_commit = True
                    shallow_boundary = True

            if is_shallow_commit:
                commit_records.append(
                    CommitRecord(
                        sha=sha_hex,
                        short=short_hex,
                        date=iso_date,
                        author_key=author_key,
                        has_agent_trailer=att.has_agent_trailer,
                        agent_id=att.agent_id,
                        attribution_basis=att.basis,
                        attribution_confidence=att.confidence,
                        claims_tests_pass=claims_pass,
                        skipped_deep=False,
                        files_changed=0,
                        shallow_baseline=True,
                    )
                )
                commit_deltas.append(
                    CommitDelta(
                        sha=sha_hex,
                        short=short_hex,
                        date=iso_date,
                        files=(),
                        has_agent_trailer=att.has_agent_trailer,
                        agent_id=att.agent_id,
                        claims_tests_pass=claims_pass,
                        skipped_deep=False,
                        files_changed=0,
                        shallow_baseline=True,
                    )
                )
                continue

            try:
                changes: List[TreeChange] = list(
                    tree_changes(
                        store,
                        prev_tree_id,
                        commit.tree,
                        want_unchanged=False,
                        rename_detector=rename_detector,
                    )
                )
            except KeyError:
                # Partial clones (`--filter=blob:limit=...`) omit oversized blobs cleanly;
                # fall back to non-rename tree diff so missing promisor blobs never crash walk.
                stats_counters["blobs_unavailable"] += 1
                try:
                    changes = list(
                        tree_changes(
                            store,
                            prev_tree_id,
                            commit.tree,
                            want_unchanged=False,
                            rename_detector=None,
                        )
                    )
                except KeyError:
                    skipped_deep_commits += 1
                    stats_counters["blobs_unavailable"] += 1
                    changes = []
            files_changed = len(changes)
            if files_changed > max_files_per_commit:
                skipped_deep_commits += 1
                caps_hit.add("max_files_per_commit")
                commit_records.append(
                    CommitRecord(
                        sha=sha_hex,
                        short=short_hex,
                        date=iso_date,
                        author_key=author_key,
                        has_agent_trailer=att.has_agent_trailer,
                        agent_id=att.agent_id,
                        attribution_basis=att.basis,
                        attribution_confidence=att.confidence,
                        claims_tests_pass=claims_pass,
                        skipped_deep=True,
                        files_changed=files_changed,
                    )
                )
                commit_deltas.append(
                    CommitDelta(
                        sha=sha_hex,
                        short=short_hex,
                        date=iso_date,
                        files=(),
                        has_agent_trailer=att.has_agent_trailer,
                        agent_id=att.agent_id,
                        claims_tests_pass=claims_pass,
                        skipped_deep=True,
                        files_changed=files_changed,
                    )
                )
                continue

            delta_objects: List[FileDelta] = []
            commit_test_contents: Dict[str, str] = {}
            added_secrets: List[Tuple[str, str, int, str]] = []
            prod_delta = 0
            test_delta = 0

            for ch in changes:
                old_entry = ch.old
                new_entry = ch.new
                if old_entry and (old_entry.mode or 0) in (_GITLINK_MODE, _SYMLINK_MODE):
                    continue
                if new_entry and (new_entry.mode or 0) in (_GITLINK_MODE, _SYMLINK_MODE):
                    continue

                raw_path = new_entry.path if (new_entry and new_entry.path) else (old_entry.path if old_entry else None)
                raw_old_path = old_entry.path if old_entry else None
                try:
                    safe_path = _safe_decode_tree_path(raw_path)
                    safe_old_path = _safe_decode_tree_path(raw_old_path) if raw_old_path != raw_path else None
                except ValueError:
                    stats_counters["blobs_unavailable"] += 1
                    continue

                if not safe_path:
                    continue

                top_dir = safe_path.split("/", 1)[0] if "/" in safe_path else "."
                dir_authors.setdefault(top_dir, set()).add(author_key)

                status_map = {"add": "A", "modify": "M", "delete": "D", "rename": "R", "copy": "A"}
                status = status_map.get(ch.type, "M")
                kind = _classify_path(safe_path, test_globs=test_globs)
                lang = language_of(safe_path)

                old_text = _read_blob_text(store, old_entry.sha if old_entry else None, max_blob_bytes, stats_counters)
                new_text = _read_blob_text(store, new_entry.sha if new_entry else None, max_blob_bytes, stats_counters)
                if old_text is None or new_text is None:
                    continue

                added_lines, removed_lines, added_cnt, removed_cnt = _compute_line_delta(old_text, new_text)
                if kind in ("source", "manifest"):
                    prod_delta += added_cnt - removed_cnt
                elif kind == "test":
                    test_delta += added_cnt - removed_cnt

                # Scan ONLY added lines for AGT-010 history secrets
                if added_lines:
                    added_snippet = "\n".join(al.text for al in added_lines)
                    for sm in scan_text(safe_path, added_snippet):
                        real_lineno = added_lines[sm.line - 1].lineno if 0 < sm.line <= len(added_lines) else sm.line
                        added_secrets.append((safe_path, sm.kind, real_lineno, sm.secret_hash))

                before_fm: Optional[FileMetrics] = None
                after_fm: Optional[FileMetrics] = None
                if kind == "test":
                    old_sha = old_entry.sha.decode("ascii") if old_entry and old_entry.sha else None
                    new_sha = new_entry.sha.decode("ascii") if new_entry and new_entry.sha else None
                    if status in ("M", "D", "R") and old_text:
                        before_fm = _cached_test_metrics(safe_old_path or safe_path, old_sha, old_text)
                    if status in ("A", "M", "R") and new_text:
                        after_fm = _cached_test_metrics(safe_path, new_sha, new_text)
                    if old_text:
                        commit_test_contents[safe_path] = old_text

                ci_before = old_text if kind in ("ci", "gate_config") and len(old_text.encode("utf-8", "ignore")) <= _MAX_CI_GATE_BYTES else None
                ci_after = new_text if kind in ("ci", "gate_config") and len(new_text.encode("utf-8", "ignore")) <= _MAX_CI_GATE_BYTES else None

                delta_objects.append(
                    FileDelta(
                        path=safe_path,
                        old_path=safe_old_path,
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
                )

            if commit_test_contents:
                test_contents_by_commit[sha_hex] = commit_test_contents

            prev_tree_paths = _walk_tree_paths(store, prev_tree_id) if prev_tree_id else ()
            curr_tree_paths = _walk_tree_paths(store, commit.tree)
            all_tree_paths = tuple(sorted(set(prev_tree_paths) | set(curr_tree_paths)))

            commit_records.append(
                CommitRecord(
                    sha=sha_hex,
                    short=short_hex,
                    date=iso_date,
                    author_key=author_key,
                    has_agent_trailer=att.has_agent_trailer,
                    agent_id=att.agent_id,
                    attribution_basis=att.basis,
                    attribution_confidence=att.confidence,
                    claims_tests_pass=claims_pass,
                    skipped_deep=False,
                    files_changed=files_changed,
                    prod_lines_delta=prod_delta,
                    test_lines_delta=test_delta,
                )
            )
            commit_deltas.append(
                CommitDelta(
                    sha=sha_hex,
                    short=short_hex,
                    date=iso_date,
                    files=tuple(delta_objects),
                    has_agent_trailer=att.has_agent_trailer,
                    agent_id=att.agent_id,
                    claims_tests_pass=claims_pass,
                    skipped_deep=False,
                    files_changed=files_changed,
                    tree_paths=all_tree_paths,
                    added_secrets=tuple(added_secrets),
                )
            )

        tooling, head_secrets, head_test_metrics, head_workflows, _ = _scan_head_tree(
            store, head_obj.tree, max_blob_bytes, test_globs=test_globs
        )
        head_secret_hashes = {s["secret_hash"] for s in head_secrets}

        det_result = run_detectors(
            commit_deltas,
            policy=policy or PolicyThresholds(),
            head_secret_hashes=head_secret_hashes,
            head_test_metrics=head_test_metrics,
            after_all_workflows=head_workflows,
            test_contents_by_commit=test_contents_by_commit,
            apply_head_rules=True,
        )

        # Link agent_id onto findings if its introducing commit carried an attribution signal
        commit_att_map = {c.sha: (c.agent_id, c.attribution_basis) for c in commit_records}
        finding_records: List[HistoryFindingRecord] = []
        for cf in det_result.findings:
            params = dict(cf.params)
            if cf.commit_sha and cf.commit_sha in commit_att_map:
                aid, abasis = commit_att_map[cf.commit_sha]
                if aid and "agent_id" not in params:
                    params["agent_id"] = aid
                    params["attribution_basis"] = abasis
            finding_records.append(
                HistoryFindingRecord(
                    id=cf.id,
                    dimension=cf.dimension,
                    severity=cf.severity,
                    confidence=cf.confidence,
                    description=cf.description,
                    evidence_file=cf.evidence_file,
                    evidence_line=cf.evidence_line,
                    rule_id=cf.rule_id,
                    remediation=cf.remediation,
                    component_id=cf.component_id,
                    fingerprint=cf.fingerprint,
                    basis=cf.basis,
                    commit_sha=cf.commit_sha,
                    params=params,
                )
            )

        total_commits = len(commit_records)
        sorted_authors = sorted(author_counts.items(), key=lambda kv: (-kv[1], kv[0]))
        top_share = round(sorted_authors[0][1] / total_commits, 4) if (sorted_authors and total_commits) else 0.0
        single_owner_dirs = sum(1 for authors in dir_authors.values() if len(authors) == 1)
        masked_contributors = [
            {
                "label": f"Contributor {chr(65 + idx)}" if idx < 26 else f"Contributor #{idx + 1}",
                "commits": count,
            }
            for idx, (_ak, count) in enumerate(sorted_authors[:10])
        ]

        declared_fraction = round(declared_commits / total_commits, 4) if total_commits else 0.0
        attribution_summary = {
            "declared_commits": declared_commits,
            "analyzed_commits": total_commits,
            "agent_declared_fraction": declared_fraction,
            "tooling_present": any(tooling.values()),
            "tooling_files": tooling,
            "limitation": ATTRIBUTION_LIMITATION,
        }

        coverage = HistoryCoverage(
            assessed=True,
            commits_total_visible=visible_count,
            commits_analyzed=total_commits,
            shallow_boundary=shallow_boundary,
            caps_hit=sorted(stats_counters["caps_hit"]),
            skipped_deep_commits=skipped_deep_commits,
            blobs_unavailable=stats_counters["blobs_unavailable"],
            notes=det_result.notes,
        )

        return HistoryResult(
            coverage=coverage,
            source_commit=head_commit_hex,
            source_tree=head_tree_hex,
            commits=commit_records,
            findings=finding_records,
            attribution=attribution_summary,
            head_tooling_present=tooling,
            head_secrets=head_secrets,
            series=det_result.series,
            ownership={
                "top_contributor_share": top_share,
                "single_owner_top_dirs": single_owner_dirs,
                "contributors": masked_contributors,
            },
        )
    finally:
        repo.close()
