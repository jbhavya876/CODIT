# Independent Human Gate & External Validations (Pending Human Actions — Section 14)

This file tracks the items from **Section 14** and the **Definition of Done Human Gate** that require an independent human reviewer, external credentials, or production provisioning outside this automated workspace.

## 1. Independent Real-World Review (`human_review.md` Gate)

- **Requirement:** An engineer who did **not** build this system selects >= 10 permissive public repositories containing commits declaring agent involvement, samples 50 flagged events (stratified by rule), labels each as `true_positive` / `false_positive` / `unclear`, checks whether `Process`, `Licenses`, and `Diligence` outputs are substantively useful (not generic, not alarmist, and consistent with raw history), and records >= 85% precision or fixes disagreements.
- **Status:** **PENDING HUMAN REVIEWER** (automated self-audit & CODIT dogfood evidence are committed separately in `docs/evidence/dogfood_audit.md`).

## 2. Production Provisioning & Release Actions (Section 14)

1. **Managed Postgres:** Provision `codit-postgres` via Render Blueprint (`render.yaml`) and confirm `DATABASE_URL` points to Postgres (`ENV=production` refuses SQLite).
2. **Offline Ed25519 Keypair:** Generate `ATTEST_SIGNING_KEY` offline (`docs/RUNBOOK.md` Section 1), store seed in secret manager, publish public key in `backend/app/attest/keys_public.json`.
3. **Production Secrets:** Configure `ADMIN_TOKEN`, `COOKIE_SECRET`, `PUBLIC_BASE_URL`, and optional `GITHUB_APP_ID` / `GITHUB_APP_PRIVATE_KEY` (read-only contents/metadata scopes only).
4. **Package Release:** Publish `codit-core` and `codit-guard` to PyPI and decide package license.
5. **Tag & Branch Protection:** Tag `v1` referenced in `action.yml` and enable the `codit-guard` CI workflow check as a required status check on `main`.
6. **Executive LLM Key (Optional):** Set `ANTHROPIC_API_KEY` if LLM executive prose is desired (deterministic template fallback operates without it).
7. **Legal Review:** Legal counsel review of `/v/{id}` wording, license disclaimer, and SVG badge copy before public launch.
