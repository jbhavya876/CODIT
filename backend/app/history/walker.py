"""
Pure-Python git history walker using `dulwich` (ADR-0002).

NEVER invokes the `git` CLI on target directories.
Decodes paths safely without filesystem path joins, minimizes author identity
via per-audit salted HMAC, and discards all commit messages, names, and emails.
"""

from __future__ import annotations

import difflib
import hashlib
import hmac
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from dulwich.diff_tree import RenameDetector, TreeChange, tree_changes
from dulwich.errors import NotCommitError
from dulwich.objects import Blob, Commit, Tree
from dulwich.repo import Repo

from codit_core.classify import (
    is_ci_path,
    is_gate_config_path,
    is_generated_path,
    is_test_path,
    language_of,
)
from codit_core.secrets import scan_text

from backend.app.config import Config
from backend.app.history.models import (
    CommitRecord,
    FileDeltaModel,
    HistoryCoverage,
    HistoryOptions,
    HistoryResult,
)

log = logging.getLogger(__name__)

_GITLINK_MODE = 0o160000
_SYMLINK_MODE = 0o120000
_MAX_DIFF_LINES_PER_FILE = 20_000
_LFS_PREFIX = b"version https://git-lfs.github.com/spec/v1"

_CLAIM_PATTERNS = [
    re.compile(
        r"\b(fix(e[sd])?|make|made|get|got|ensure[sd]?|all)\b[^.\n]{0,40}\btests?\b[^.\n]{0,20}\b(pass(ing|es|ed)?|green)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\btests? (now )?pass(ing)?\b", re.IGNORECASE),
    re.compile(r"\bci (is )?(now )?(green|passing)\b", re.IGNORECASE),
]

_TOOLING_FILES = {
    "CLAUDE.md",
    "AGENTS.md",
    ".cursor/rules",
    ".cursorrules",
    ".github/copilot-instructions.md",
    ".windsurfrules",
    "GEMINI.md",
    ".aider.conf.yml",
}

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
    candidates = [dot_git / "shallow", dot_git / ".git" / "shallow"]
    for p in candidates:
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


def _compute_line_delta(before_text: str, after_text: str) -> Tuple[List[Dict[str, Any]], int, int]:
    """Return (added_lines[{lineno,text}], added_count, removed_count), CRLF-normalized."""
    b_lines = before_text.splitlines()[:_MAX_DIFF_LINES_PER_FILE]
    a_lines = after_text.splitlines()[:_MAX_DIFF_LINES_PER_FILE]

    matcher = difflib.SequenceMatcher(None, b_lines, a_lines, autojunk=False)
    added_lines: List[Dict[str, Any]] = []
    added_count = 0
    removed_count = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in ("replace", "delete"):
            removed_count += i2 - i1
        if tag in ("replace", "insert"):
            added_count += j2 - j1
            for offset, text in enumerate(a_lines[j1:j2], start=j1 + 1):
                added_lines.append({"lineno": offset, "text": text})
    return added_lines, added_count, removed_count


def _scan_head_tree(store, tree_id: Optional[bytes], max_blob_bytes: int) -> Tuple[Dict[str, bool], List[Dict[str, Any]]]:
    tooling: Dict[str, bool] = {t: False for t in _TOOLING_FILES}
    secrets_at_head: List[Dict[str, Any]] = []
    if not tree_id:
        return tooling, secrets_at_head

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
                    if full_path in _TOOLING_FILES or full_path.startswith(".cursor"):
                        if full_path == ".cursor/rules":
                            tooling[".cursor/rules"] = True
                    stack.append((full_path, entry.sha))
                else:
                    if full_path in tooling:
                        tooling[full_path] = True
                    elif full_path.startswith(".cursor/rules/"):
                        tooling[".cursor/rules"] = True
                    # Scan text files for secret hashes (for AGT-010 cross-check)
                    try:
                        blob = store[entry.sha]
                    except KeyError:
                        continue
                    if isinstance(blob, Blob) and len(blob.data) <= max_blob_bytes and b"\x00" not in blob.data[:8192]:
                        text = blob.data.decode("utf-8", errors="replace")
                        for m in scan_text(full_path, text):
                            secrets_at_head.append({
                                "path": full_path,
                                "kind": m.kind,
                                "rule_id": m.rule_id,
                                "secret_hash": m.secret_hash,
                                "line": m.line,
                            })
    except Exception as exc:
        log.debug("HEAD tree scan error: %s", exc)
    return tooling, secrets_at_head


def _detect_basic_trailer_signal(message_text: str) -> Tuple[bool, Optional[str], str, str]:
    """Lightweight P1 signal check (enriched in P2 with signatures.yaml)."""
    lines = message_text.rstrip().splitlines()
    if not lines:
        return False, None, "none", "none"
    # Final paragraph only
    last_para: List[str] = []
    for line in reversed(lines):
        if not line.strip():
            break
        last_para.append(line)
    para_text = "\n".join(reversed(last_para)).lower()
    if "co-authored-by:" in para_text and any(
        tok in para_text for tok in ("claude", "copilot", "cursor", "codex", "devin", "aider", "[bot]")
    ):
        return True, "declared-agent", "trailer", "high"
    if "generated with" in para_text and "claude" in para_text:
        return True, "claude-code", "footer", "high"
    return False, None, "none", "none"


def walk_history(
    repo_path: Path,
    options: Optional[HistoryOptions] = None,
    *,
    test_globs: Optional[List[str]] = None,
) -> HistoryResult:
    """
    Walk first-parent git history using `dulwich` and emit scrubbed HistoryResult.
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

        # Collect first-parent commit chain up to caps
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

        # Oldest -> newest
        chain.reverse()

        per_audit_salt = os.urandom(32)
        stats_counters: Dict[str, Any] = {
            "blobs_unavailable": 0,
            "caps_hit": caps_hit,
        }
        skipped_deep_commits = 0
        commit_records: List[CommitRecord] = []
        author_counts: Dict[str, int] = {}
        dir_authors: Dict[str, Set[str]] = {}

        rename_detector = RenameDetector(store, rename_threshold=60, max_files=max(max_files_per_commit, 200))

        for commit in chain:
            sha_hex = commit.id.decode("ascii")
            short_hex = sha_hex[:7]
            iso_date = _format_iso_utc(commit.commit_time)
            email_bytes = _extract_email_bytes(commit.author)
            author_key = hmac.new(per_audit_salt, email_bytes, hashlib.sha256).hexdigest()[:12]
            author_counts[author_key] = author_counts.get(author_key, 0) + 1

            msg_text = (commit.message or b"").decode("utf-8", errors="replace")
            claims_pass = _claims_tests_pass(msg_text)
            has_trailer, agent_id, att_basis, att_conf = _detect_basic_trailer_signal(msg_text)
            # Clear commit message immediately
            del msg_text

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
                        has_agent_trailer=has_trailer,
                        agent_id=agent_id,
                        attribution_basis=att_basis,
                        attribution_confidence=att_conf,
                        claims_tests_pass=claims_pass,
                        skipped_deep=False,
                        files_changed=0,
                        shallow_baseline=True,
                    )
                )
                continue

            changes: List[TreeChange] = list(
                tree_changes(
                    store,
                    prev_tree_id,
                    commit.tree,
                    want_unchanged=False,
                    rename_detector=rename_detector,
                )
            )
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
                        has_agent_trailer=has_trailer,
                        agent_id=agent_id,
                        attribution_basis=att_basis,
                        attribution_confidence=att_conf,
                        claims_tests_pass=claims_pass,
                        skipped_deep=True,
                        files_changed=files_changed,
                    )
                )
                continue

            file_deltas: List[FileDeltaModel] = []
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

                added_lines_raw, added_cnt, removed_cnt = _compute_line_delta(old_text, new_text)
                if kind == "source":
                    prod_delta += added_cnt - removed_cnt
                elif kind == "test":
                    test_delta += added_cnt - removed_cnt

                # Only store secret scan hashes, never source text in HistoryResult JSON
                # (Full AST/testmetrics analysis in worker lands in P3)
                file_deltas.append(
                    FileDeltaModel(
                        path=safe_path,
                        old_path=safe_old_path,
                        status=status,
                        kind=kind,
                        language=lang,
                        added=[],
                        removed_count=removed_cnt,
                        added_count=added_cnt,
                        before_blob_sha=old_entry.sha.decode("ascii") if old_entry and old_entry.sha else None,
                        after_blob_sha=new_entry.sha.decode("ascii") if new_entry and new_entry.sha else None,
                    )
                )

            commit_records.append(
                CommitRecord(
                    sha=sha_hex,
                    short=short_hex,
                    date=iso_date,
                    author_key=author_key,
                    has_agent_trailer=has_trailer,
                    agent_id=agent_id,
                    attribution_basis=att_basis,
                    attribution_confidence=att_conf,
                    claims_tests_pass=claims_pass,
                    skipped_deep=False,
                    files_changed=files_changed,
                    prod_lines_delta=prod_delta,
                    test_lines_delta=test_delta,
                    files=file_deltas,
                )
            )

        tooling, head_secrets = _scan_head_tree(store, head_obj.tree, max_blob_bytes)

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

        coverage = HistoryCoverage(
            assessed=True,
            commits_total_visible=visible_count,
            commits_analyzed=total_commits,
            shallow_boundary=shallow_boundary,
            caps_hit=sorted(stats_counters["caps_hit"]),
            skipped_deep_commits=skipped_deep_commits,
            blobs_unavailable=stats_counters["blobs_unavailable"],
        )

        return HistoryResult(
            coverage=coverage,
            source_commit=head_commit_hex,
            source_tree=head_tree_hex,
            commits=commit_records,
            head_tooling_present=tooling,
            head_secrets=head_secrets,
            ownership={
                "top_contributor_share": top_share,
                "single_owner_top_dirs": single_owner_dirs,
                "contributors": masked_contributors,
            },
        )
    finally:
        repo.close()
