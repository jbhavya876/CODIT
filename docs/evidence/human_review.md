# Independent Human Gate & External Validations (Pending Human Actions — Section 14)

This file tracks the items from **Section 14** and the **Definition of Done Human Gate** that require an independent human reviewer, external credentials, or production provisioning outside this automated workspace.

## 1. Independent Real-World Review (`human_review.md` Gate)

- **Requirement:** An engineer who did **not** build this system selects >= 10 permissive public repositories containing commits declaring agent involvement, samples 50 flagged events (stratified by rule), labels each as `true_positive` / `false_positive` / `unclear`, checks whether `Process`, `Licenses`, and `Diligence` outputs are substantively useful (not generic, not alarmist, and consistent with raw history), and records >= 85% precision or fixes disagreements.
- **Prepared Evidence:**
  - Automated self-audit & CODIT dogfood evidence are committed in `docs/evidence/dogfood_audit.md`.
  - A 19-repository real-world run with a stratified 48-event sample table (`reviewer_label = _PENDING_`) is pre-captured in `docs/evidence/real_world_corpus.md` so the independent reviewer can audit raw commits/outputs directly (and add or swap repos if desired).
  - Running that corpus already surfaced and fixed three real-world defects: `dulwich` `RenameDetector` missing-promisor-blob `KeyError` handling in `backend/app/history/walker.py`, quadratic `difflib.SequenceMatcher` stalls in `walker._compute_line_delta` (replaced by O(N) prefix/suffix trimming + `Counter` fallback), and `AGT-011` excluding pure non-code/documentation commits in `packages/codit_core/src/codit_core/detectors/agt009_011_012.py`.
- **Status:** **PENDING HUMAN REVIEWER** — independent human labeling (`_PENDING_` rows in `docs/evidence/real_world_corpus.md`) and precision sign-off cannot be performed by the authoring system.

## 2. Production Provisioning & Release Actions (Section 14)

1. **Managed Postgres (External Provisioning):** Provision `codit-postgres` via Render Blueprint (`render.yaml`) and confirm `DATABASE_URL` points to Postgres (`ENV=production` refuses SQLite).
2. **Offline Ed25519 Keypair (Tooling Ready — Run Offline):** Zero-echo key generator and key-ring rotation script prepared at `scripts/keygen_attest.py` (writes `0600` private seed outside git in `.secrets/`, prints only public key JSON, retains retired keys on rotation in `backend/app/attest/keys_public.json`). Run on a clean offline host and copy the seed to Render secret manager (`ATTEST_SIGNING_KEY`).
3. **Production Secrets (Tooling Ready — Operator Config):** Zero-echo secret bootstrapper prepared at `scripts/bootstrap_env.py` (generates `ADMIN_TOKEN`, `COOKIE_SECRET`, `PUBLIC_BASE_URL` into a `0600` env file without stdout leaks). Apply to Render env vars and optionally configure `GITHUB_APP_ID` / `GITHUB_APP_PRIVATE_KEY` (read-only contents/metadata scopes only).
4. **Package Release (Wheels Verified — PyPI Publish External):** MIT `LICENSE`, `README.md`, classifiers, URLs, and PEP 517 wheel builds verified for `packages/codit_core` and `packages/codit_guard` (`3.0.0`). `action.yml` defaults to `install-from: github` (tag `v1` git subdirectory install) so the GitHub Action works immediately before PyPI upload; set `install-from: pypi` once published with PyPI credentials.
5. **Tag & Branch Protection (Local Tag Ready — Admin Push/Rule External):** `v1` tag is tagged locally against `main`; push `main` and `v1` and enable the `codit-guard` CI workflow check as a required status check in GitHub repo settings.
6. **Executive LLM Key (Optional):** Set `ANTHROPIC_API_KEY` if LLM executive prose is desired (deterministic template fallback operates without it).
7. **Legal Review (External Counsel):** Legal counsel review of `/v/{id}` wording, license disclaimer, and SVG badge copy before public launch.
