# ADR-0002: Untrusted Git History Reader & Process Isolation

- **Status**: Accepted (Gate 0)
- **Date**: 2026-11-27
- **Addresses**: D3 (`.git` ignored & shallow clone), Constraint 9 (no `git` CLI on untrusted directories), Constraint 21 (JSON-only child IPC)

## Context

Process Forensics (P1–P3) inspects commit history, renames, added/removed lines, trailers, and CI/test modifications. However, a repository's `.git/` directory is attacker-controlled input: invoking the native `git` CLI on an untrusted directory (especially extracted from a ZIP upload or containing malicious config/hooks/alternates) risks arbitrary code execution via `core.fsmonitor`, `core.sshCommand`, `core.pager`, `diff.*.textconv`, `filter.*`, `objects/info/alternates`, or symlink traversal. Furthermore, `backend/app/ingestion/git_clone.py` previously embedded installation tokens directly in the clone URL (`argv`), exposing secrets in process listings.

## Decision

1. **Strict split between remote acquisition and object reading**:
   - **Remote acquisition (`backend/app/history/acquire.py`)**: Public and private GitHub clones construct the URL solely from validated `owner` / `repo` slugs (`^[A-Za-z0-9_.-]{1,100}$`) and validated branch names (`^[A-Za-z0-9._/-]{1,100}$`, non-`-` prefix) — never accepting arbitrary client URLs or flags. Uses hardened `git -c core.hooksPath=/dev/null -c protocol.file.allow=never -c protocol.ext.allow=never -c core.symlinks=false -c credential.helper= -c core.fsmonitor=false clone --bare --depth <N> --single-branch --branch <branch> --no-tags --filter=blob:limit=<HISTORY_MAX_BLOB_KB>k` with isolated environment (`GIT_TERMINAL_PROMPT=0`, `GIT_CONFIG_NOSYSTEM=1`, `GIT_CONFIG_GLOBAL=/dev/null`, `GIT_ASKPASS=/bin/true`, `GIT_LFS_SKIP_SMUDGE=1`, `GIT_NO_LAZY_FETCH=1`). Private tokens are passed strictly via `GIT_CONFIG_COUNT=1` / `GIT_CONFIG_KEY_0=http.extraHeader` / `GIT_CONFIG_VALUE_0` in environment variables (never in CLI argv). A transfer watchdog aborts the clone if directory size exceeds `HISTORY_TRANSFER_MAX_MB`.
   - **ZIP `.git/` acquisition (`backend/app/ingestion/zip_extract.py`)**: Extracts only an allowlisted subtree (`HEAD`, `packed-refs`, `shallow`, `refs/**`, `objects/[0-9a-f]{2}/[0-9a-f]{38}`, `objects/pack/*.pack`, `objects/pack/*.idx`), rejecting symlinks (`external_attr`), `.git`-as-file, traversal paths, and dropping `config`, `hooks/`, `info/`, `objects/info/alternates`, `worktrees/`, `modules/`. Writes a minimal clean `config`.
2. **Pure-Python object reading via `dulwich` inside a resource-capped child worker**:
   - All `.git` inspection runs inside `python -m backend.app.history.worker <job.json>` using `dulwich>=0.22` (`Repo`, `diff_tree.tree_changes` + `RenameDetector`, `patch.write_blob_diff` or line diffing). No `git` CLI is ever invoked inside or against an extracted `.git` directory.
   - The child worker imports zero HTTP clients, sets POSIX `resource.setrlimit` (`RLIMIT_CPU`, `RLIMIT_AS`, `RLIMIT_NOFILE`) on Linux production hosts (skipping with a logged warning on non-Linux dev machines such as Windows), and enforces a parent wall-clock process-group kill (`HISTORY_WALLTIME_SECONDS`).
   - IPC uses strict UTF-8 JSON (`job.json` -> `result.json` capped at 25 MB, stdout capped at 1 MB) validated via Pydantic models — never `pickle`.
3. **Identity & content minimization**:
   - The worker strips author names, emails, commit messages, and raw source before exiting. Only per-audit keyed `author_key = HMAC-SHA256(per_audit_salt, email.lower())[:12]`, enumerated signal booleans (`has_agent_trailer`, `agent_id`, `claims_tests_pass`), SHA, ISO date, and `CoreFinding` / series aggregates cross back to the parent process.
   - Tree entry paths (`bytes`) are decoded with `surrogateescape`, checked against `..`/absolute/NUL, and read exclusively from the object store without filesystem path joins.

## Known Residual Risks

- Pure-Python pack decompression (`zlib`) and large delta chains remain subject to CPU/memory exhaustion bugs in `dulwich` or malformed zlib streams; mitigated by child-process `RLIMIT_AS`/`RLIMIT_CPU`, parent wall-clock termination, blob size caps (`HISTORY_MAX_BLOB_KB`), per-commit file-count caps (`HISTORY_MAX_FILES_PER_COMMIT`), and transfer size caps (`HISTORY_TRANSFER_MAX_MB`).
- Host OS dev parity: `RLIMIT_AS` / `RLIMIT_CPU` resource limits are not available on Windows dev hosts and are enforced in Linux CI and production runtime.
