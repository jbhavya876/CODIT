# CODIT Pivot — Engineering Log

Started from commit `463e02d` (`main`, 2026-11-27).
Specification: **CODIT Pivot — The Assurance Layer for AI-Written Code (`3.0.0`)**.

---

## 1. Baseline Verification (Gate 0)

- **Python runtime**: `Python 3.13.1` (`.venv\Scripts\python.exe`)
- **Git CLI**: `git version 2.49.0.windows.1` (host dev OS is Windows; production target is Linux — POSIX `resource.setrlimit` caps skip with a logged warning on non-Linux dev machines and are enforced in Linux production)
- **Baseline pytest run** (`.venv\Scripts\pytest.exe backend/tests/ -q` at commit `463e02d`):
  - **`69 passed, 2 warnings in 42.37s`**

---

## 2. Ground-Truth Verification (D1–D9)

- **D1 — CONFIRMED**: `backend/app/state.py:11-22` holds process-global `_ACTIVE_CODEBASE` and `_ACTIVE_REPORT`; `backend/app/routes/analyze.py:45` declares `global _ACTIVE_REPORT` inside `run_full_analysis()`.
- **D2 — CONFIRMED**: `render.yaml:13` starts `uvicorn run:app --host 0.0.0.0 --port $PORT --workers 2`, causing split per-worker memory across requests.
- **D3 — CONFIRMED**: `backend/app/ingestion/models.py:52-53` ignores `".git"` in `IGNORED_DIR_NAMES`; `backend/app/ingestion/git_clone.py:44-46,69-71` clones `--depth 1` and deletes `.git` immediately. In addition, `git_clone.py:41` embeds `access_token` directly in `clone_url` (`https://x-access-token:{access_token}@github.com/...`), which leaks into process listings and must be replaced with env-based `http.extraHeader`.
- **D4 — CONFIRMED**: `backend/app/routes/analyze.py:43-157` runs AST parsing, collectors, graph assembly, scoring, ONNX/SHAP inference, and roadmap synthesis synchronously inline inside the HTTP handler. `backend/sandbox/job_queue.py:54-151` (`SandboxExecutor`, re-exported via `backend/app/sandbox/__init__.py:2`) is never called by `routes/analyze.py` or `routes/ingest.py`; moreover `run_in_sandbox` runs `asyncio.to_thread(worker_fn, temp_dir, job)` in-process rather than spawning an isolated container or resource-capped child process (`test_network_isolation` falls back to `True` when Docker is absent).
- **D5 — CONFIRMED**: Random `uuid.uuid4().hex[:6|:8]` fragments generate non-deterministic finding IDs at `backend/app/collectors/tests.py:85,103,115,139`, `backend/app/collectors/duplication.py:71`, `backend/app/collectors/scalability.py:72`, and `backend/app/collectors/security.py:180`.
- **D6 — CONFIRMED**: `frontend/src/components/ui/TrustStrip.jsx:12-13` hardcodes `"Ephemeral Sandbox"` and `"Retention: 0s"`, whereas `backend/app/config.py:67` / `.env.example:37` define `REPORT_RETENTION_HOURS=24` and inline execution does not use a container sandbox.
- **D7 — CONFIRMED**: `NOTES.md:5-30` documents an older obsidian `#080B11` / `Inter` / `#38BDF8` draft token set, whereas `frontend/tailwind.config.js:8-85`, `frontend/src/index.css:1-100`, and `docs/UI_DESIGN_SYSTEM.md:24-70` are all aligned on the shipped **Forensic Luxury** token set (`#0A0B0D` chamber, `#EFEAE0` dossier, `#D4FF3A` laser-lime, `Instrument Serif` + `Geist Sans` + `JetBrains Mono`). **Resolution**: The shipped `tailwind.config.js` / `index.css` / `docs/UI_DESIGN_SYSTEM.md` token set is canonical; `NOTES.md` will be updated in P9 alongside the frontend work so no second palette or accent color is introduced.
- **D8 — CONFIRMED & MODIFIED**: `README.md:188,234` states `49 passed` tests instead of the actual `69` tests. `README.md:92-115` already describes ONNX/SHAP honestly ("trained on synthetic structural profiles fit to hand-authored architectural formulas"), rather than claiming to eliminate heuristics, so that ML wording was previously corrected; however, `README.md` still lacks documentation for `codit-guard`, process forensics, licenses, audience reports, and attestations.
- **D9 — CONFIRMED**: `backend/app/services/graph_service.py:30-32` holds module-level `_active`, `_mode`, `_startup_error`; `backend/app/services/demo_graph.py:26-27` holds global `_G` and `_IS_CUSTOM_GRAPH`; `backend/app/services/cognodb_graph.py:23` holds global `_driver`; `graph_service.py:84-97` writes assembled codebase graphs into the single global `_G` (and its `cognodb` branch at line 95 is a no-op `pass`).

---

## 3. Section 14 Early Flags (Human-Only Actions)

The following external/operational items require human provisioning or sign-off outside automated execution and are tracked explicitly so development and tests run cleanly with local equivalents until provisioned:
1. Managed PostgreSQL instance (`DATABASE_URL`) for `ENV=production` deployment.
2. Offline generation of production Ed25519 signing seed (`ATTEST_SIGNING_KEY`) stored in secret manager, plus public key entry in `backend/app/attest/keys_public.json`. Tests and local dev inject ephemeral test keys via environment fixtures.
3. Production `ADMIN_TOKEN`, `PUBLIC_BASE_URL`, and GitHub App installation permissions (`contents: read`, `metadata: read`).
4. PyPI publishing & license selection for `codit-guard`, tagging `v1` for `action.yml`, and enabling required branch-protection check on `main`.
5. `ANTHROPIC_API_KEY` in production (executive report automatically exercises deterministic template fallback when unset or validation fails).
6. Legal review of verify-page wording, license disclaimer, and badge phrasing before public launch.
7. Independent human engineer review (`docs/evidence/real_world_review.md` and `docs/evidence/human_review.md`) prior to final human sign-off.

---

## 4. Decision & Deviation Log

| Date | Gate | Topic | Decision / Deviation | Reference |
|---|---|---|---|---|
| 2026-11-27 | G0 | Audit scoping & graph isolation | Per-audit SQLAlchemy records + isolated NetworkX `GraphHandle` reconstructed from persisted `graph_json` (5 MB cap, LRU size 16). CognoDB restricted to single-tenant non-production mode. | [ADR-0001](adr/0001-audit-scoping.md) |
| 2026-11-27 | G0 | History reader boundary | Pure-Python `dulwich` object traversal inside a separate resource-capped child process (`RLIMIT_*` on Linux; logged skip on Windows dev). Hardened `git clone` for remote acquisition only. | [ADR-0002](adr/0002-history-reader.md) |
| 2026-11-27 | G0 | Attestation format & signing | `codit.attestation.v1` using canonical sorted compact UTF-8 JSON (strictly no floats), Ed25519 via `cryptography`, atomic `.codit/verify` challenge for `git` subjects, archive SHA-256 only for uploads. | [ADR-0003](adr/0003-attestation-format.md) |
| 2026-11-27 | G0 | `codit_core` extraction boundary | Pure Python library in `packages/codit_core/` with zero FastAPI/DB/network/LLM imports. Single source of truth for secret scanning, path classification, `CommitDelta` detectors, fingerprints, and pure license classification. | [ADR-0004](adr/0004-codit-core-boundary.md) |
| 2026-11-27 | G0 | Staging single-instance note | Until P9 retires two-step ingest->analyze, `STAGING_DIR/<audit_id>` uses local disk with `0700` perms and `STAGING_TTL_MINUTES` (15m) reaper cleanup; single-instance disk assumption recorded here (multi-instance requires shared object storage). | P0 item 5 |
