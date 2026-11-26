# ADR-0001: Audit-Scoped Persistence & Graph Isolation

- **Status**: Accepted (Gate 0)
- **Date**: 2026-11-27
- **Addresses**: D1 (`state.py` globals), D2 (`uvicorn --workers 2`), D4 (inline execution), D9 (global graph store)

## Context

Currently `backend/app/state.py` stores `_ACTIVE_CODEBASE` and `_ACTIVE_REPORT` in process memory, and `backend/app/services/{graph_service,demo_graph,cognodb_graph}.py` store a single global graph `_G` / `_driver`. Under `render.yaml` (`--workers 2`), two sequential requests from the same browser can hit different OS processes, causing `"no active codebase"` failures, cross-user data leakage, and making concurrent audits, background jobs, and verifiable attestations impossible.

## Decision

1. **Database-backed audit lifecycle (`SQLAlchemy 2` + `alembic`)**:
   - All audit metadata, status (`queued -> running -> completed | failed | expired`), enumerated stage events (`audit_events`), findings (`findings`), coverage/scorecard/process/licenses/ownership/graph payloads live in SQLAlchemy tables (`audits` keyed by 128-bit `secrets.token_urlsafe(16)` capability IDs).
   - SQLite (`sqlite:///./.data/codit.db`) is permitted in dev/test; startup **refuses to boot** if `ENV=production` resolves to SQLite (Postgres via `psycopg[binary]>=3.1` required).
2. **Per-audit isolated graphs via `GraphHandle`**:
   - Each audit persists a serialized `graph_json` blob capped at 5 MB. If oversized, nodes are pruned keeping highest-criticality nodes and `coverage.graph_truncated=true` is set.
   - `services/graph_service.py` wraps an immutable-per-audit `GraphHandle` backed by NetworkX (`nx.MultiDiGraph`), reconstructed on demand from `graph_json` and cached in an in-process bounded LRU cache (max size 16). Every query function (`search`, `get_component`, `dependencies_bundle`, `impact`, `criticality`, `leaderboard`, `shortest_path`, `stats`) takes `graph: GraphHandle` explicitly (with optional fallback to the demo seed handle only for un-ingested demo queries).
   - CognoDB remains configurable only for single-tenant dev/demo usage and is disallowed for multi-audit isolation in `ENV=production`.
3. **Background job runner (`backend/app/jobs/runner.py`)**:
   - Uses `ThreadPoolExecutor(max_workers=JOB_WORKERS)` (default 2) with all progress stored in `audit_events` so any worker can serve polls.
   - Startup reaper transitions stale `running` jobs older than `SANDBOX_WALLTIME_SECONDS + 60` to `failed (error_code="interrupted")`.
   - Periodic reaper (every 10 minutes + startup) deletes expired audits (`expires_at < now`), their cascade events/findings, and staging directories, while setting `attestations.audit_id = NULL`.
4. **Legacy two-step compatibility wrapper**:
   - Existing `/api/ingest/*`, `/api/analyze/run`, `/api/report*`, and `/api/components*` endpoints read/write a signed `HttpOnly` `codit_audit` cookie binding the session to an `audit_id`, keeping intermediate file entries only in `STAGING_DIR/<audit_id>` (`0700` permissions, 15-minute hard TTL, wiped on analyze completion/failure/reap). `FileEntry.content` is never inserted into the database.

## Consequences

- **Positive**: Zero cross-tenant graph or report leakage; `--workers 2` works deterministically; retention guarantees are enforceable at row level.
- **Known limitation (single-instance staging)**: Local `STAGING_DIR` assumes sticky/single-instance disk only for the legacy two-step UI flow prior to P9's one-shot `POST /api/audits` migration. Multi-instance horizontal scaling requires either one-shot uploads (P9) or shared ephemeral object storage.
