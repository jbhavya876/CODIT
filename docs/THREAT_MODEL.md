# CODIT Threat Model (`3.0.0`)

STRIDE-oriented mapping from protected assets and untrusted actors to enforced controls and automated proof tests.

---

## 1. Protected Assets

1. **Ed25519 Attestation Private Key (`ATTEST_SIGNING_KEY`)**: signs `codit.attestation.v1` claims. Leak enables forged public attestations.
2. **Audit Results & Privacy Guarantees**: derived scorecards, findings, process metadata, and license registers stored in SQLAlchemy; **raw source code, commit messages, author names, and author emails must never be stored or leaked**.
3. **Scoped Repository Credentials (`GITHUB_APP_PRIVATE_KEY`, installation tokens, `ADMIN_TOKEN`)**: grant temporary read-only repository clone access or admin revocation rights.
4. **PR Policy Integrity (`.codit.yml`, `.codit/baseline.json`)**: governs pass/fail enforcement in CI.

## 2. Threat Actors

- **Malicious Repository / Git History Author**: embeds hooks, `fsmonitor`, `alternates`, delta bombs, symlinks, path traversal tree entries, prompt injections, or HTML payloads inside git objects.
- **Malicious ZIP Submitter**: uploads Zip-Slip paths, symlinks, Zip-Bombs, or disguised `.git` triggers.
- **Malicious PR Author / Coding Agent**: weakens tests, suppresses linters, weakens CI workflows, modifies `.codit.yml`, or sends oversized/ambiguous hook payloads.
- **Malicious Badge / Attestation Claimer**: seeks a badge for someone else's repo, attempts to replay challenge nonces, tampers signed JSON, or passes floats to exploit serializer differences.
- **Curious Third Party**: attempts unauthenticated cross-audit enumeration or scraping via capability IDs / underwriting exports / LLM outputs.

## 3. Threat -> Control -> Proof Matrix

| STRIDE | Threat | Enforced Control | Verified By Test(s) |
|---|---|---|---|
| **T / E** | Git config (`core.fsmonitor`), hooks, or `alternates` executed during clone/read | Never run `git` CLI on untrusted directories; `dulwich` object reader + ZIP `.git` allowlist + `--depth` token via `GIT_CONFIG_COUNT` env | `test_p1_history.py::test_adversarial_a1_a2_a3_a5_zip_git_attacks`, `canary identity scrub` |
| **D** | Zip-bomb, 100k-commit repo, or delta-chain OOM/CPU exhaustion | Pre-decompression byte/file/depth quotas; `HISTORY_MAX_COMMITS`, `HISTORY_MAX_BLOB_KB`, `HISTORY_WALLTIME_SECONDS`, `RLIMIT_AS`/`RLIMIT_CPU` (Linux) | `test_ingestion.py`, `test_p10_hardening.py::test_adversarial_a4_oversized_blob_and_a11_commit_cap` |
| **T** | CLI argument / scheme injection in repo URL or branch (`--upload-pack=`, `file://`, `ext::`) | Strict regex allowlist in `validate_github_repo_input` & `validate_branch_name` | `test_p1_history.py`, `test_p7_reports.py::test_audits_lifecycle_entitlements_and_a12_validation` |
| **I** | Raw source, author names, emails, or commit messages leak to DB, API, underwriting, LLM, SVG, or `/v/{id}` | In-worker `scrubber` + SQLAlchemy stores derived fields only; allowlisted executive LLM payload; canary-tested underwriting & verify templates | `test_p10_hardening.py::test_db_and_filesystem_zero_source_and_zero_canary_persistence`, `test_p7_reports.py::test_canary_isolation*`, `test_p8_attestations.py` |
| **T** | Prompt injection (`"Ignore previous instructions..."`) or XSS (`<script>`, `"><img src=x>`) via repo artifacts | Commit messages excluded from LLM & reports (`a8`); Jinja2 autoescape + strict CSP meta on HTML exports; strict CSP `default-src 'none'` & zero scripts on `/v/{id}` | `test_p7_reports.py`, `test_p8_attestations.py`, `test_security_middleware.py::test_verify_page_stricter_csp_than_spa` |
| **S** | Forged badge / misattribution for third-party repo or nonce race reuse | `.codit/verify` challenge file required in audited commit; atomic SQL `UPDATE ... WHERE used_at IS NULL` single-use claim; ZIP subjects omit repo name | `test_p8_attestations.py::test_challenge_hostile_repo_rejected_and_atomic_single_use_race` |
| **T / R** | Signature forgery, float ambiguity, or tampered attestations | Canonical UTF-8 JSON without floats (`reject_floats`), Ed25519 signature, fail-closed `503` when `ATTEST_SIGNING_KEY` unset, published public keys + revocations | `test_p8_attestations.py::test_canonicalization_stability_unicode_and_float_rejection`, `test_attestation_issuance*` |
| **T** | PR edits `.codit.yml` or runs `codit-guard` SSRF via malicious package name | CI mode (`--base`/`--head`) always reads `.codit.yml` & baseline from `--base` and flags `GRD-001`; strict npm/PyPI coord regex & HTTPS allowlist | `test_p4_guard.py` (`a14`), `test_p5_licenses.py::test_ssrf_controls_and_recording_transport` |
| **I / E** | Cross-tenant audit leakage across Gunicorn/Uvicorn workers | Zero module-level `_ACTIVE*` state; signed HMAC cookie + per-audit `GraphHandle`; `404` capability isolation | `test_p0_foundation.py::test_concurrent_audits_fully_isolated`, `test_no_module_level_active_globals_in_backend_app` |
| **D** | Endpoint abuse on expensive audit creation, attestation, or admin routes | Per-IP sliding-window buckets (`audits` 4/m, `attest` 6/m, `admin` 10/m, `public` 120/m); `ADMIN_TOKEN` constant-time check | `test_security_middleware.py::TestPivotRateLimitGroupsAndVerifyCSP` |
