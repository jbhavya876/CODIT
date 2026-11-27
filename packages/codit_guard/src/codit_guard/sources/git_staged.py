"""Staged git index diff reader (`--staged`) for pre-commit enforcement."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from codit_core.delta import CommitDelta, FileDelta

from codit_guard.sources.git_common import (
    build_file_delta,
    decode_safe_blob,
    git_cat_file_batch,
    git_obj_sha,
    is_ignored_by_policy,
    parse_name_status_z,
    run_git,
)


def _tree_paths_at_index(repo_root: Path) -> Tuple[str, ...]:
    raw = run_git(repo_root, ["ls-files", "-z"], check=False)
    if not raw:
        return ()
    return tuple(p.decode("utf-8", errors="surrogateescape") for p in raw.split(b"\x00") if p)


def read_staged_commit_delta(
    repo_root: Path,
    *,
    ignore_paths: List[str],
    test_globs: List[str],
    not_assessed: List[Dict[str, Optional[str]]],
) -> Tuple[CommitDelta, Dict[str, str], Dict[str, str]]:
    """Return (CommitDelta, test_contents_by_path, head_workflows_after)."""
    has_head = git_obj_sha(repo_root, "HEAD") is not None
    if has_head:
        raw_ns = run_git(repo_root, ["diff", "--cached", "--name-status", "-M", "-z"])
    else:
        raw_ns = run_git(repo_root, ["diff", "--cached", "--name-status", "--root", "-M", "-z"], check=False)

    changed = parse_name_status_z(raw_ns)
    idx_paths = _tree_paths_at_index(repo_root)

    # Batch-fetch ALL required index/HEAD blobs + workflow blobs in ONE git cat-file --batch call
    specs: List[str] = []
    wf_paths: List[str] = []
    for p in idx_paths:
        lp = p.lower().replace("\\", "/")
        if lp.startswith(".github/workflows/") and lp.endswith((".yml", ".yaml")):
            wf_paths.append(p)
            specs.append(f":{p}")

    active_changed = [ch for ch in changed if not is_ignored_by_policy(ch.path, ignore_paths)]
    for ch in active_changed:
        if has_head and ch.status in ("M", "D", "R"):
            specs.append(f"HEAD:{ch.old_path or ch.path}")
        if ch.status in ("A", "M", "R"):
            specs.append(f":{ch.path}")

    fetched = git_cat_file_batch(repo_root, list(dict.fromkeys(specs)))

    after_workflows: Dict[str, str] = {}
    for wp in wf_paths:
        _sha, raw_wf = fetched.get(f":{wp}", (None, None))
        txt = decode_safe_blob(raw_wf, wp, not_assessed)
        if txt is not None:
            after_workflows[wp] = txt

    deltas: List[FileDelta] = []
    test_contents: Dict[str, str] = {}

    for ch in active_changed:
        b_sha: Optional[str] = None
        a_sha: Optional[str] = None
        if has_head and ch.status in ("M", "D", "R"):
            b_sha, before_raw = fetched.get(f"HEAD:{ch.old_path or ch.path}", (None, None))
            if before_raw is None:
                continue
        else:
            before_raw = b""

        if ch.status in ("A", "M", "R"):
            a_sha, after_raw = fetched.get(f":{ch.path}", (None, None))
            if after_raw is None:
                continue
        else:
            after_raw = b""

        before_text = decode_safe_blob(before_raw, ch.old_path or ch.path, not_assessed)
        after_text = decode_safe_blob(after_raw, ch.path, not_assessed)
        if before_text is None or after_text is None:
            continue

        fd, tc = build_file_delta(
            path=ch.path,
            old_path=ch.old_path,
            status=ch.status,
            before_text=before_text,
            after_text=after_text,
            before_sha=b_sha,
            after_sha=a_sha,
            test_globs=test_globs,
        )
        deltas.append(fd)
        if tc:
            test_contents[ch.path] = tc

    head_paths_raw = run_git(repo_root, ["ls-tree", "-r", "--name-only", "-z", "HEAD"], check=False) if has_head else b""
    head_paths = tuple(p.decode("utf-8", errors="surrogateescape") for p in head_paths_raw.split(b"\x00") if p) if head_paths_raw else ()
    all_paths = tuple(sorted(set(idx_paths) | set(head_paths)))

    delta = CommitDelta(
        sha="0" * 40,
        short="staged",
        date=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        files=tuple(deltas),
        files_changed=len(changed),
        tree_paths=all_paths,
    )
    return delta, test_contents, after_workflows
