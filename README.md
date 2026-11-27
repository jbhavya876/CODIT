# CODIT (`3.0.0`) — The Assurance Layer for AI-Written Code

CODIT statically inspects software repositories, git object history, and dependency lockfiles to surface security exposures, license conflicts, and process-integrity anomalies across seven deterministic scoring dimensions.

> **Scope notice:** Static analysis of repository contents and history. No code is executed. A CODIT score or badge is a deterministic signal over observed evidence — never a legal opinion, formal certification, or warranty.

---

## Core Capabilities

1. **Process Forensics (`AGT-001..AGT-012`)**
   - Inspects bare git history inside a bounded `dulwich` reader (never invokes `git` CLI against untrusted directories; raw commit messages, author names, and emails are discarded inside the worker).
   - Flags test deletion accompanying production changes, orphan test removal, newly skipped tests, assertion stripping, trivially true assertions (`assert True`), CI verification weakening, quality threshold drops, suppression bursts, historical credentials requiring rotation, unverified megacommits, and focused test markers.
   - Commit metadata attribution follows strict honesty rules: *"Attribution reflects declarations in commit metadata. Commits without a declaration are unknown, not human-authored."*
2. **Local-First Diff Gate (`codit-guard`)**
   - Shares the pure `codit-core` rule catalog with the server and outputs text, JSON, or SARIF 2.1.0.
   - **Enforcement layers and bypass boundaries:**

     | Layer | What It Checks | Boundary |
     |---|---|---|
     | **Agent hook (`codit-guard hook claude-code`)** | Inspects `Edit`/`Write`/`MultiEdit` payloads and `Bash` test/CI tampering commands | Shortens the feedback loop; an agent can use unmatched tools |
     | **Commit hook (`codit-guard install --git-hook`)** | Evaluates staged diffs before commit | Blocks ordinary local commits; bypassable with `git commit --no-verify` |
     | **CI required check (`action.yml`)** | Evaluates PR ranges reading `.codit.yml` and `.codit/baseline.json` from the `--base` commit | **Only the CI check, set as a required status check, is authoritative.** |

3. **License & IP Lens (`LIC-001..LIC-008`)**
   - Parses pinned versions from `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `poetry.lock`, `Pipfile.lock`, and `requirements.txt` (unpinned specs are reported as not assessed, never guessed).
   - Evaluates SPDX compatibility against `MIT`, permissive, or `proprietary` project postures and flags unresolved production dependencies transparently.
   - *"Automated license classification. Not legal advice. Verify with counsel before relying on it."*
4. **Rubric `2.0.0` & Assumption-Labeled Effort Model**
   - Seven dimensions weighted to `1.00`: `security` (`0.30`), `tests` (`0.20`), `agent_integrity` (`0.15`), `scalability` (`0.12`), `licenses` (`0.10`), `duplication` (`0.07`), `maintainability` (`0.06`).
   - Full specification: [`docs/RUBRIC.md`](docs/RUBRIC.md) and live endpoint `/rubric/2.0.0`. Missing dimensions exclude their weight and block `Production-track` (*a badge must not reward missing evidence*).
   - Optional ONNX fragility & SHAP outputs remain labeled calibrated heuristics and never affect the deterministic rubric score or phase.
5. **Four Audience Report Profiles**
   - `technical`, `diligence`, `executive` (strict allowlist LLM summary with deterministic template fallback), and `underwriting` (`codit.underwriting.v1` JSON with zero repository-derived strings).
6. **Ed25519 Signed Attestations (`/v/{id}`, `/badge/{id}.svg`)**
   - Git attestations require single-use `.codit/verify` repository-control proof; archive (ZIP) attestations contain SHA-256 only with no repository name.
   - Verify offline with zero server trust:
     ```bash
     codit-guard attest verify attestation.json --keys https://coditt.xyz/.well-known/codit-keys.json
     ```

---

## Retention & Privacy Architecture

- **Lines Executed:** `0` lines of repository source are ever imported, compiled, or run.
- **Raw Source Retention:** `0s` after audit completion (staging directories under `STAGING_DIR` use `0700` permissions and are removed in `finally`, with a 15-minute reaper safety net).
- **Derived Audit Results Retention:** `AUDIT_RETENTION_HOURS` (default `24h`), purged automatically by the background reaper.
- **Database Storage:** SQLAlchemy (`audits`, `audit_events`, `findings`, `blob_metrics`, `license_cache`, `attestations`, `attest_challenges`) stores derived findings and metrics only — never source files, commit messages, names, or emails.

---

## Quick Start (Local Development)

```bash
# Backend + workspace packages
pip install -r backend/requirements.txt
alembic -c backend/alembic.ini upgrade head
pytest backend/tests/ -q

# Frontend
npm --prefix frontend ci
npm --prefix frontend run build

# Run unified API + static SPA server
uvicorn backend.app:create_app --factory --host 127.0.0.1 --port 8000 --workers 2
```

## Local Gate & GitHub Action

Install locally from the repository packages (or via PyPI once published):

```bash
pip install ./packages/codit_core ./packages/codit_guard
codit-guard check --offline
```

Use in GitHub Actions via [`action.yml`](action.yml):

```yaml
- uses: jbhavya876/CODIT@v1
  with:
    fail-on: high
    install-from: github # switch to 'pypi' after publishing codit-core & codit-guard
    upload-sarif: "true"
```

Pre-commit integration is defined in [`.pre-commit-hooks.yaml`](.pre-commit-hooks.yaml).

---

## Repository Layout

| Path | Purpose |
|---|---|
| `backend/` | FastAPI server, bare-history `dulwich` reader, license resolver, Rubric `2.0.0`, Alembic migrations, Ed25519 attestations, and `backend/tests/` (`124` tests) |
| `frontend/` | React 18 + Tailwind + Vite Forensic Luxury SPA (`Audit Cockpit`, `Ingest Repo`, `Process`, `Licenses`, `Reports`, `Attest`) |
| `packages/codit_core/` | Pure zero-DB rule catalog (`AGT-001..AGT-012`, `GRD-001..GRD-002`, `LIC-001..LIC-008`), secret scanner, and AST test body hashing |
| `packages/codit_guard/` | Local CLI diff gate, Claude Code `PreToolUse` hook, `.codit/baseline.json`, SARIF 2.1.0 output, and offline attestation verifier |
| `scripts/` | Offline Ed25519 keygen (`keygen_attest.py`), zero-echo runtime secret generator (`bootstrap_env.py`), calibration, and token export |
| `docs/` | Architecture Decision Records (`docs/adr/`), Rubric specification, Threat Model, Runbook, UI Design System, and Validation Evidence (`docs/evidence/`) |

---

## Deployment & Operator Tooling

- **Environment template:** Copy [`.env.example`](.env.example) to `.env` for local development. In production (`ENV=production`), SQLite is rejected and a PostgreSQL `DATABASE_URL` is required.
- **Offline Ed25519 attestation keypair (zero secret stdout output):**
  ```bash
  python scripts/keygen_attest.py --kid 2026-12-a --publish
  ```
- **Runtime secret bootstrap (writes mode `0600` under `.secrets/prod.env`):**
  ```bash
  python scripts/bootstrap_env.py --public-base-url https://coditt.xyz
  ```
- **Containers & Render:** [`docker-compose.yml`](docker-compose.yml) (API, network-isolated worker, Neo4j) and [`render.yaml`](render.yaml) (Render web service + `codit-postgres`).

---

## Documentation & Validation Evidence

- [Rubric `2.0.0` Specification (`docs/RUBRIC.md`)](docs/RUBRIC.md)
- [Threat Model (`docs/THREAT_MODEL.md`)](docs/THREAT_MODEL.md) · [Operations Runbook (`docs/RUNBOOK.md`)](docs/RUNBOOK.md)
- [UI Design System (`docs/UI_DESIGN_SYSTEM.md`)](docs/UI_DESIGN_SYSTEM.md) · [Architecture Decision Records (`docs/adr/`)](docs/adr/)
- [Changelog (`CHANGELOG.md`)](CHANGELOG.md)
- Validation evidence: [`dogfood_audit.md`](docs/evidence/dogfood_audit.md) · [`real_world_corpus.md`](docs/evidence/real_world_corpus.md) · [`human_review.md`](docs/evidence/human_review.md)

## License

Released under the [MIT License](LICENSE).
