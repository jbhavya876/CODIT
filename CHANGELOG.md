# Changelog

## [3.0.0] - 2026-11-27

### Added
- **Pure `codit-core` Engine (`packages/codit_core`):** Secret scanner, path/test classifier, whitespace-invariant AST body hashes, stable finding fingerprints, git commit trailer/footer/bot-account attribution, `AGT-001..AGT-012` / `GRD-001..GRD-002` process-integrity detectors, and SPDX / license matrix engine (`LIC-001..LIC-008`).
- **Local-First Gate (`packages/codit_guard`):** `codit-guard check` (staged / range / paths), `codit-guard hook claude-code` (`PreToolUse` stdin/exit-2 contract), `codit-guard baseline`, `codit-guard explain`, `codit-guard attest verify`, SARIF 2.1.0 export, `.pre-commit-hooks.yaml`, and GitHub `action.yml`.
- **Audit-Scoped Persistence & Safe History:** SQLAlchemy 2 ORM + Alembic `0001_pivot`, per-audit `GraphHandle`, dulwich bare-history reader + ZIP `.git` allowlist extraction, zero raw source or identity storage, signed `codit_audit` cookies.
- **License & IP Provenance Lens:** Parsers for 6 lockfile ecosystems (`package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `poetry.lock`, `Pipfile.lock`, `requirements.txt`), SSRF-hardened allowlisted lookups (`deps.dev`, npm, PyPI) with 7-day SQLAlchemy cache, unpinned `not_assessed` tracking.
- **Scoring Rubric `2.0.0` & Effort Model:** Seven weighted dimensions (`security`, `tests`, `agent_integrity`, `scalability`, `licenses`, `duplication`, `maintainability`), missing-evidence renormalization (`Production-track` unattainable without assessed evidence), transparent assumption-labeled person-day effort ranges, generated `docs/RUBRIC.md` + `/rubric/2.0.0`.
- **Four Audience Profiles & Entitlements:** `technical`, `diligence`, `executive` (allowlisted LLM payload with strict validator + template fallback), and zero-repo-string `codit.underwriting.v1` JSON schema, gated behind pluggable `EntitlementProvider` (`FreeTierProvider` / `X402Provider`).
- **Cryptographic Attestations & Public Verification:** Ed25519 `codit.attestation.v1` payloads, single-use `.codit/verify` repository-control challenge, zero-JS Jinja2 `/v/{id}` page with strict CSP, XML-escaped `/badge/{id}.svg` badges, `/.well-known/codit-{keys,revocations}.json`, and admin revocation.
- **Instrument UI Extensions:** One-shot `POST /api/audits` intake with Process History selector and real event polling, Process tab (keyboard-accessible Integrity Ledger + table toggle + Attribution strip), Licenses tab, ProfileSwitcher Reports tab, Attest tab, Guard CLI drawer, and runtime-backed `TrustStrip`.

### Changed
- Bumped application, `codit-core`, `codit-guard`, and frontend package versions to `3.0.0`.
- Added per-route-group rate limits (`audits`, `attest`, `public`, `admin`) and stricter CSP on `/v/{id}`.
