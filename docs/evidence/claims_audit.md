# Trust Claims & UI Copy Audit

Every trust statement rendered in the CODIT UI, public verification page, and CLI is grounded directly in server configuration or execution behavior.

| Surface | Rendered Statement | Enforcing Code / Source |
|---|---|---|
| `TrustStrip` (`GET /api/health`) | `0 lines executed` | `treesitter_walker.py`, `dulwich` (`walker.py`), `zip_extract.py` — no target script or package lifecycle execution |
| `TrustStrip` (`GET /api/health`) | `Zip guards active` | `backend/app/ingestion/zip_extract.py` (traversal, symlink, compression ratio, depth, count guards) + `extract_git_history_from_zip` allowlist |
| `TrustStrip` (`GET /api/health`) | `Static analysis only · 180s / 1024MB limits` (never claims an isolated container sandbox when `sandbox_isolated=false`) | `backend/app/history/worker.py`, `backend/app/routes/api.py` (`/health` `runtime_posture`) |
| `TrustStrip` (`GET /api/health`) | `Source retention: 0s · Results kept 24h` | `audit_service.run_audit_pipeline` `finally: purge_staging(...)` and `jobs/runner.py::reap_expired_audits` (`AUDIT_RETENTION_HOURS`) |
| `GuardDrawer` & `README.md` | `"Only the CI check, set as a required status check, is authoritative."` | `.codit.yml` read from `--base` in `codit_guard/cli.py`, flagging `GRD-001` on edits |
| `ProcessTab` & `diligence.py` | `"Attribution reflects declarations in commit metadata. Commits without a declaration are unknown, not human-authored."` | `codit_core/attribution.py` returns `status="unknown"` when absent |
| `LicensesTab` & reports | `"Automated license classification. Not legal advice. Verify with counsel before relying on it."` | `codit_core/licenses/__init__.py::LICENSE_DISCLAIMER`, `backend/app/collectors/licenses.py` |
| `/v/{id}` & reports | `"Static analysis of repository contents and history. No code was executed. This is not a certification, legal opinion, or guarantee."` | `backend/app/delivery/profiles/shared.py::METHODOLOGY_PARAGRAPH`, `backend/app/routes/public.py` |
