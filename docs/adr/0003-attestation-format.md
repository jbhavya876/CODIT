# ADR-0003: Attestation Format, Canonicalization & Key Lifecycle

- **Status**: Accepted (Gate 0)
- **Date**: 2026-11-27
- **Addresses**: Verifiable Score (P8), Constraints 10, 14, 15, Anti-goals (no certification/tampering/misattribution)

## Context

CODIT attestations (`codit.attestation.v1`) must allow any external third party to verify an audit score offline using only the signed JSON document, published public keys, and `codit-guard attest verify`. To resist forgery, canonicalization drift across runtimes, data leakage, and third-party misattribution/defamation, the signed structure and verification workflow require strict invariants.

## Decision

1. **Payload schema & strict primitive constraints**:
   - Signed payload schema `codit.attestation.v1` permits **only**: integers, booleans, enumerated strings (`phase`, `blockers`, `phase_qualifiers`, `status`), hex digests (`commit`, `tree`, `archive sha256`, `findings_digest`), `att_<ULID>`, ISO-8601 UTC timestamps (`YYYY-MM-DDTHH:MM:SSZ`), and (only after control verification) an allowlist-validated `owner/name` repository slug.
   - **Floating-point values are strictly rejected** at serialization time (raising an error on any `float` anywhere inside the payload tree) to eliminate cross-language float formatting ambiguity. Zero repo-derived free text or findings appear inside the attestation payload.
   - `findings_digest` commits to `sha256(canonical_json(sorted((rule_id, fingerprint, severity) for f in findings)))`, keeping individual findings private unless the repo owner later discloses them to prove inclusion.
2. **Deterministic Canonicalization**:
   - Signature input bytes are produced by computing `json.dumps(payload_without_signature, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")`.
3. **Ed25519 Key Handling & Rotation**:
   - Private signing seed (`ATTEST_SIGNING_KEY`: base64-encoded 32-byte Ed25519 seed) and key identifier (`ATTEST_KEY_ID`) live strictly in process environment variables. Never logged, persisted to SQL, serialized in HTTP error responses, or committed. If `ATTEST_SIGNING_KEY` is unset, `POST /api/audits/{id}/attest` fails closed with HTTP `503 attestation_unavailable`.
   - Corresponding public keys (`kid`, `alg: "Ed25519"`, base64url raw 32-byte key, `status: active|retired`, `not_before`) live in `backend/app/attest/keys_public.json` and are served at `/.well-known/codit-keys.json`. Retired keys remain published indefinitely so unexpired historical attestations stay verifiable after key rotation.
4. **Repository-Control Verification & Consent**:
   - `git` subjects require atomic single-use nonce verification: `POST /api/attest/challenge` issues a 128-bit nonce bound to the validated repo slug (`24h` TTL). The audited commit tree must contain `.codit/verify` matching `codit-verify=<nonce>`. Issuance atomically consumes the nonce (`UPDATE attest_challenges SET used_at=... WHERE nonce=? AND used_at IS NULL AND expires_at>?`) and sets `control_verified=true`.
   - `archive` subjects omit any repo name, identify strictly by archive `sha256`, and record `control_verified=false` (`ARCHIVE` badge state).
   - Issuance always requires explicit `{"consent_publish": true}` on `POST /api/audits/{id}/attest`.
5. **Revocation**:
   - Controlled exclusively via `POST /api/admin/attest/{id}/revoke` authenticated with `hmac.compare_digest` against `ADMIN_TOKEN` (router disabled when unset). Revocations are reflected immediately in `/.well-known/codit-revocations.json`, `/v/{id}`, and `/badge/{id}.svg` (`REVOKED` overrides `EXPIRED`).

## Consequences

- External CLI verification (`codit-guard attest verify`) requires zero proprietary binaries — only standard JSON canonicalization and Ed25519 signature verification (`cryptography>=42`).
- Existing private audits of arbitrary public repos cannot be converted into public repo-named attestations without write-access proof.
