# CODIT Operations & Incident Response Runbook (`3.0.0`)

## 1. Key Generation & Normal Rotation (`ATTEST_SIGNING_KEY`)

1. Generate a 32-byte Ed25519 seed **offline** (never in CI logs or committed files):
   ```python
   import base64
   from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
   k = Ed25519PrivateKey.generate()
   print("ATTEST_SIGNING_KEY:", base64.b64encode(k.private_bytes_raw()).decode())
   print("PUBLIC_KEY_B64U:", base64.urlsafe_b64encode(k.public_key().public_bytes_raw()).decode().rstrip("="))
   ```
2. Back up the seed offline, set `ATTEST_SIGNING_KEY` and a dated `ATTEST_KEY_ID` (e.g. `2027-01-a`) in the Render secret manager.
3. Add the public key to `backend/app/attest/keys_public.json` with `"status": "active"`.
4. To rotate normally:
   - Generate a new seed (`2027-06-a`).
   - Change the previous key entry in `backend/app/attest/keys_public.json` to `"status": "retired"` (**never delete retired public keys** so historical attestations remain verifiable).
   - Add the new key entry (`"status": "active"`), deploy, and update `ATTEST_SIGNING_KEY` + `ATTEST_KEY_ID`.

## 2. Emergency Key-Leak Incident Response

If `ATTEST_SIGNING_KEY` is suspected exposed:
1. **Disable issuance immediately:** clear or rotate `ATTEST_SIGNING_KEY` in the runtime secret store (missing key causes `/api/audits/{id}/attest` to fail closed with `503 attestation_unavailable`).
2. **Revoke affected attestations:** enumerate all attestations signed with the compromised `kid` and invoke:
   ```bash
   curl -X POST https://coditt.xyz/api/admin/attest/<attestation_id>/revoke \
     -H "Authorization: Bearer $ADMIN_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"reason_code":"compromised_key"}'
   ```
3. **Republish keys:** mark the compromised `kid` `"status": "revoked"` or `"retired"` in `keys_public.json`, publish the replacement active key, and verify `/.well-known/codit-keys.json` & `/.well-known/codit-revocations.json`.
4. **Notify:** notify affected repository owners to re-run and re-issue attestations under the new `kid`.

## 3. Revoking Individual Attestations

Allowed enumerated `reason_code` values: `owner_request`, `compromised_key`, `superseded`, `false_claim`, `policy_violation`.
`ADMIN_TOKEN` must be set; when unset, `/api/admin/*` returns `404`.

## 4. Reaper & Staging Cleanup

- Background reaper (`backend/app/jobs/runner.py`) runs automatically on startup in `lifespan`:
  - Marks `running` jobs exceeding `SANDBOX_WALLTIME_SECONDS + 60` as `failed(interrupted)`.
  - Deletes `AuditRow` records past `AUDIT_RETENTION_HOURS` (default `24h`), nulls `AttestationRow.audit_id` FK first, and deletes orphaned `STAGING_DIR` folders past `STAGING_TTL_MINUTES` (default `15m`).
  - Purges expired `AttestationRow` records after `expires_at + ATTESTATION_RETENTION_DAYS`.
- Manual trigger: `python -c "from backend.app.jobs.runner import reap_expired_audits, reap_stale_running_jobs; print(reap_stale_running_jobs(), reap_expired_audits())"`.

## 5. Database Migrations, Backup, Restore & Rollback Plan

- **Apply migration:** `alembic -c backend/alembic.ini upgrade head`
- **Backup (Postgres):** `pg_dump --format=custom --no-owner "$DATABASE_URL" > codit_backup_$(date -u +%Y%m%dT%H%M%SZ).dump`
- **Restore (Postgres):** `pg_restore --clean --if-exists --no-owner -d "$DATABASE_URL" codit_backup_*.dump`
- **Rollback Plan (`3.0.0` -> previous release):**
  1. Restore the pre-migration Postgres snapshot before downgrading schema, OR run `alembic -c backend/alembic.ini downgrade base`.
  2. Roll back the Render deploy to the prior git commit / Docker image.
  3. Existing `1.0.0` scorecards persisted before `3.0.0` remain immutable and untouched.
