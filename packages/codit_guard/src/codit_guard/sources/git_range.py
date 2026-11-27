"""
Git commit-range diff reader (`--base REF --head REF`) with base-commit policy trust.
Supports `--scope net` (default) and `--scope per-commit`.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from codit_core.delta import CommitDelta, FileDelta

from codit_guard.baseline import parse_baseline_json
from codit_guard.config import GuardConfig, parse_config_yaml
from codit_guard.sources.git_common import (
    GitSourceError,
    build_file_delta,
    decode_safe_blob,
    git_cat_file_batch,
    git_obj_sha,
    is_ignored_by_policy,
    parse_name_status_z,
    run_git,
)


def verify_range_refs(repo_root, base_ref: str, head_ref: str) -> Tuple[str, str]:
    base_sha = git_obj_sha(repo_root, f"{base_ref}^{{commit}}")
    head_sha = git_obj_sha(repo_root, f"{head_ref}^{{commit}}")
    if not base_sha:
        raise GitSourceError(f"Base reference '{base_ref}' is unreachable or does not resolve to a commit.")
    if not head_sha:
        raise GitSourceError(f"Head reference '{head_ref}' is unreachable or does not resolve to a commit.")
    return base_sha, head_sha


def load_trusted_base_policy(repo_root, base_sha: str) -> Tuple[GuardConfig, Set[str]]:
    """
    Constraint 17: Load `.codit.yml` and `.codit/baseline.json` strictly from `base`.
    """
    fetched = git_cat_file_batch(repo_root, [f"{base_sha}:.codit.yml", f"{base_sha}:.codit/baseline.json"])
    _s1, raw_cfg = fetched.get(f"{base_sha}:.codit.yml", (None, None))
    if raw_cfg is not None:
        cfg = parse_config_yaml(raw_cfg.decode("utf-8-sig", errors="replace"), source="base")
    else:
        cfg = GuardConfig(source="default")

    _s2, raw_base = fetched.get(f"{base_sha}:.codit/baseline.json", (None, None))
    baseline_fps = parse_baseline_json(raw_base.decode("utf-8-sig", errors="replace")) if raw_base is not None else set()
    return cfg, baseline_fps


def _ls_tree_paths(repo_root, commit_sha: str) -> Tuple[str, ...]:
    raw = run_git(repo_root, ["ls-tree", "-r", "--name-only", "-z", commit_sha], check=False)
    if not raw:
        return ()
    return tuple(p.decode("utf-8", errors="surrogateescape") for p in raw.split(b"\x00") if p)


def _workflows_at_commit(repo_root, commit_sha: str, tree_paths: Tuple[str, ...], not_assessed) -> Dict[str, str]:
    wf_paths = [
        p for p in tree_paths
        if p.lower().replace("\\", "/").startswith(".github/workflows/") and p.lower().endswith((".yml", ".yaml"))
    ]
    fetched = git_cat_file_batch(repo_root, [f"{commit_sha}:{p}" for p in wf_paths])
    wf: Dict[str, str] = {}
    for p in wf_paths:
        _sha, raw_b = fetched.get(f"{commit_sha}:{p}", (None, None))
        txt = decode_safe_blob(raw_b, p, not_assessed)
        if txt is not None:
            wf[p] = txt
    return wf


def _diff_two_commits(
    repo_root,
    parent_sha: Optional[str],
    commit_sha: str,
    *,
    ignore_paths: List[str],
    test_globs: List[str],
    not_assessed: List[Dict[str, Optional[str]]],
) -> Tuple[CommitDelta, Dict[str, str]]:
    if parent_sha:
        raw_ns = run_git(repo_root, ["diff", "--name-status", "-M", "-z", parent_sha, commit_sha])
    else:
        raw_ns = run_git(repo_root, ["diff-tree", "--no-commit-id", "--name-status", "-r", "--root", "-M", "-z", commit_sha])

    changed = parse_name_status_z(raw_ns)
    active_changed = [ch for ch in changed if not is_ignored_by_policy(ch.path, ignore_paths)]

    specs: List[str] = []
    for ch in active_changed:
        if parent_sha and ch.status in ("M", "D", "R"):
            specs.append(f"{parent_sha}:{ch.old_path or ch.path}")
        if ch.status in ("A", "M", "R"):
            specs.append(f"{commit_sha}:{ch.path}")

    fetched = git_cat_file_batch(repo_root, list(dict.fromkeys(specs)))

    deltas: List[FileDelta] = []
    test_contents: Dict[str, str] = {}

    for ch in active_changed:
        b_sha: Optional[str] = None
        a_sha: Optional[str] = None
        if parent_sha and ch.status in ("M", "D", "R"):
            b_sha, b_raw = fetched.get(f"{parent_sha}:{ch.old_path or ch.path}", (None, None))
            if b_raw is None:
                continue
        else:
            b_raw = b""

        if ch.status in ("A", "M", "R"):
            a_sha, a_raw = fetched.get(f"{commit_sha}:{ch.path}", (None, None))
            if a_raw is None:
                continue
        else:
            a_raw = b""

        before_text = decode_safe_blob(b_raw, ch.old_path or ch.path, not_assessed)
        after_text = decode_safe_blob(a_raw, ch.path, not_assessed)
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

    c_date = run_git(repo_root, ["show", "-s", "--format=%cI", commit_sha]).decode("utf-8", errors="replace").strip()
    if "+" in c_date:
        c_date = c_date.replace("+00:00", "Z")
    prev_paths = _ls_tree_paths(repo_root, parent_sha) if parent_sha else ()
    curr_paths = _ls_tree_paths(repo_root, commit_sha)
    all_paths = tuple(sorted(set(prev_paths) | set(curr_paths)))

    cd = CommitDelta(
        sha=commit_sha,
        short=commit_sha[:7],
        date=c_date,
        files=tuple(deltas),
        files_changed=len(changed),
        tree_paths=all_paths,
    )
    return cd, test_contents


def read_range_commit_deltas(
    repo_root,
    base_sha: str,
    head_sha: str,
    *,
    scope: str,
    ignore_paths: List[str],
    test_globs: List[str],
    not_assessed: List[Dict[str, Optional[str]]],
) -> Tuple[List[CommitDelta], Dict[str, Dict[str, str]], Dict[str, str]]:
    head_paths = _ls_tree_paths(repo_root, head_sha)
    after_workflows = _workflows_at_commit(repo_root, head_sha, head_paths, not_assessed)

    if scope == "net":
        cd, tc = _diff_two_commits(
            repo_root,
            base_sha,
            head_sha,
            ignore_paths=ignore_paths,
            test_globs=test_globs,
            not_assessed=not_assessed,
        )
        tcbc = {cd.sha: tc} if tc else {}
        return [cd], tcbc, after_workflows

    raw_list = run_git(repo_root, ["rev-list", "--first-parent", "--reverse", f"{base_sha}..{head_sha}"])
    commits_list = [ln.strip() for ln in raw_list.decode("ascii").splitlines() if ln.strip()]
    out: List[CommitDelta] = []
    tcbc: Dict[str, Dict[str, str]] = {}
    for c_sha in commits_list:
        parent_sha = git_obj_sha(repo_root, f"{c_sha}^1")
        cd, tc = _diff_two_commits(
            repo_root,
            parent_sha,
            c_sha,
            ignore_paths=ignore_paths,
            test_globs=test_globs,
            not_assessed=not_assessed,
        )
        out.append(cd)
        if tc:
            tcbc[cd.sha] = tc
    return out, tcbc, after_workflows
