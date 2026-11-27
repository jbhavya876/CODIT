"""
Attestation issuance, lookup, revocation, and optional staleness cache (P8).
"""

from __future__ import annotations

import os
import subprocess
import time
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
from sqlalchemy import asc, select
from ulid import ULID

from backend.app.attest.canonical import compute_findings_digest, reject_floats, utc_iso_second
from backend.app.attest.challenge import consume_challenge_atomic
from backend.app.attest.signing import (
    AttestationUnavailableError,
    sign_attestation_payload,
    verify_signed_attestation,
)
from backend.app.config import Config
from backend.app.db.engine import session_scope
from backend.app.db.models import AttestationRow, AuditRow, FindingRow
from backend.app.delivery.profiles.shared import safe_hex_40, safe_hex_64
from backend.app.history.acquire import HistoryAcquisitionError, validate_github_repo_input

VALID_REVOCATION_REASONS = frozenset({
    "owner_request",
    "compromised_key",
    "superseded",
    "false_claim",
    "policy_violation",
})

_STALENESS_CACHE: Dict[str, Tuple[float, Optional[int]]] = {}
_STALENESS_TTL_SECONDS = 3600.0


class AttestError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


@lru_cache(maxsize=1)
def _engine_git_revision() -> str:
    env_rev = os.getenv("ENGINE_GIT_SHA", "").strip()
    if env_rev:
        return env_rev[:40]
    try:
        repo_root = Path(__file__).resolve().parents[3]
        out = subprocess.check_output(
            ["git", "rev-parse", "--short=12", "HEAD"],
            cwd=str(repo_root),
            timeout=2,
            stderr=subprocess.DEVNULL,
        )
        return out.decode("ascii", errors="ignore").strip() or "unknown"
    except Exception:
        return "unknown"


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _derive_subject(row: AuditRow) -> Dict[str, Any]:
    if row.source_kind in ("public", "private"):
        try:
            owner, name = validate_github_repo_input(row.source_ref)
        except HistoryAcquisitionError as exc:
            raise AttestError(403, "control_not_verified", f"Repository slug is not eligible for verification: {exc}") from exc

        commit_hex = safe_hex_40(row.source_commit or (row.process_json or {}).get("source_commit"))
        tree_hex = safe_hex_40(row.source_tree or (row.process_json or {}).get("source_tree"))
        if not commit_hex or not tree_hex:
            raise AttestError(
                403,
                "control_not_verified",
                "Git commit and tree hashes are required (enable history inspection on an audited commit containing .codit/verify).",
            )

        verify_tokens = list((row.report_meta_json or {}).get("verify_tokens") or [])
        canonical_repo = f"{owner}/{name}"
        matched_nonce = consume_challenge_atomic(canonical_repo, verify_tokens)
        if not matched_nonce:
            raise AttestError(
                403,
                "control_not_verified",
                "Repository control not verified: commit the challenge token to .codit/verify before auditing.",
            )

        return {
            "kind": "git",
            "host": "github.com",
            "repo": canonical_repo,
            "commit": commit_hex,
            "tree": tree_hex,
            "control_verified": True,
        }

    if row.source_kind == "zip":
        archive_hex = safe_hex_64(row.source_archive_sha256)
        if not archive_hex:
            raise AttestError(403, "control_not_verified", "Archive SHA-256 digest is missing.")
        return {
            "kind": "archive",
            "sha256": archive_hex,
            "control_verified": False,
        }

    raise AttestError(403, "control_not_verified", "Demo audits cannot receive public attestations.")


def issue_attestation(audit_id: str, *, consent_publish: bool) -> Dict[str, Any]:
    if consent_publish is not True:
        raise AttestError(400, "consent_required", "Explicit `consent_publish: true` is required before issuing a public attestation.")

    with session_scope() as session:
        row = session.get(AuditRow, audit_id)
        if row is None:
            raise AttestError(404, "not_found", "Audit not found.")
        exp = _ensure_utc(row.expires_at)
        now = datetime.now(timezone.utc)
        if exp <= now or row.status == "expired":
            raise AttestError(404, "not_found", "Audit not found.")
        if row.status != "completed" or not row.scorecard_json:
            raise AttestError(409, "audit_not_complete", "Audit must complete before an attestation can be issued.")

        finding_rows = session.execute(
            select(FindingRow).where(FindingRow.audit_id == audit_id).order_by(asc(FindingRow.id))
        ).scalars().all()
        findings_digest = compute_findings_digest(
            (fr.rule_id, fr.fingerprint, fr.severity) for fr in finding_rows
        )

        # Snapshot attributes cleanly before building payload
        sc = dict(row.scorecard_json or {})
        cov = dict(row.coverage_json or {})
        rubric_ver = str(sc.get("rubric_version") or row.rubric_version or "2.0.0")
        engine_ver = str(row.engine_version or "3.0.0")
        session.expunge(row)

    # Check signing availability BEFORE consuming single-use challenge nonce
    from backend.app.attest.signing import _load_active_private_key
    try:
        _load_active_private_key()
    except AttestationUnavailableError as exc:
        raise AttestError(503, "attestation_unavailable", str(exc)) from exc

    subject = _derive_subject(row)

    att_id = f"att_{str(ULID()).lower()}"
    issued_dt = datetime.now(timezone.utc).replace(microsecond=0)
    expires_dt = issued_dt + timedelta(days=Config.ATTEST_TTL_DAYS)

    hist_cov = cov.get("history") or {}
    if bool(hist_cov.get("assessed")):
        hist_block: Dict[str, Any] = {
            "assessed": True,
            "commits_analyzed": int(hist_cov.get("commits_analyzed", 0)),
            "partial": bool(hist_cov.get("shallow_boundary") or hist_cov.get("caps_hit")),
        }
    else:
        hist_block = {"assessed": False}

    lic_cov = cov.get("licenses") or {}
    lic_pct: Optional[int]
    if not lic_cov or lic_cov.get("not_applicable"):
        lic_pct = None if lic_cov.get("not_applicable") else 0
    else:
        lic_pct = int(lic_cov.get("resolved_pct", 0))

    raw_dims = sc.get("dimensions") or {}
    dim_ints: Dict[str, Optional[int]] = {}
    for dname in ("security", "tests", "agent_integrity", "scalability", "licenses", "duplication", "maintainability"):
        d_obj = raw_dims.get(dname)
        if not isinstance(d_obj, dict) or d_obj.get("score") is None or not d_obj.get("assessed", True):
            dim_ints[dname] = None
        else:
            dim_ints[dname] = int(d_obj["score"])

    payload_unsigned: Dict[str, Any] = {
        "schema": "codit.attestation.v1",
        "attestation_id": att_id,
        "issued_at": utc_iso_second(issued_dt),
        "expires_at": utc_iso_second(expires_dt),
        "subject": subject,
        "coverage": {
            "files_total": int(cov.get("files_total", 0)),
            "files_scanned": int(cov.get("files_scanned", 0)),
            "partial": bool(cov.get("partial", False)),
            "history": hist_block,
            "licenses_resolved_pct": lic_pct,
        },
        "rubric": {
            "id": "codit-rubric",
            "version": rubric_ver,
        },
        "engine": {
            "version": engine_ver,
            "revision": _engine_git_revision(),
        },
        "result": {
            "overall": int(sc.get("overall", sc.get("overall_score", 0))),
            "phase": str(sc.get("phase", "Prototype")),
            "phase_qualifiers": [str(q) for q in (sc.get("phase_qualifiers") or [])],
            "dimensions": dim_ints,
            "blockers": [str(b) for b in (sc.get("blockers") or [])],
        },
        "findings_digest": findings_digest,
    }
    reject_floats(payload_unsigned)

    try:
        signed_payload = sign_attestation_payload(payload_unsigned)
    except AttestationUnavailableError as exc:
        raise AttestError(503, "attestation_unavailable", str(exc)) from exc

    sig_meta = signed_payload["signature"]
    with session_scope() as session:
        session.add(
            AttestationRow(
                id=att_id,
                audit_id=audit_id,
                issued_at=issued_dt,
                expires_at=expires_dt,
                subject_json=subject,
                payload_json=signed_payload,
                signature=sig_meta["sig"],
                kid=sig_meta["kid"],
                control_verified=bool(subject.get("control_verified", False)),
                revoked_at=None,
                revoked_reason_code=None,
            )
        )

    base = Config.PUBLIC_BASE_URL.rstrip("/")
    return {
        "attestation_id": att_id,
        "verify_url": f"{base}/v/{att_id}",
        "badge_url": f"{base}/badge/{att_id}.svg",
        "verify_path": f"/v/{att_id}",
        "badge_path": f"/badge/{att_id}.svg",
        "attestation": signed_payload,
    }


def get_attestation_record(attestation_id: str, now: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
    if not attestation_id:
        return None
    cur = now or datetime.now(timezone.utc)
    retention_cutoff = cur - timedelta(days=Config.ATTESTATION_RETENTION_DAYS)
    with session_scope() as session:
        row = session.get(AttestationRow, attestation_id)
        if row is None:
            return None
        exp = _ensure_utc(row.expires_at)
        if exp < retention_cutoff and row.revoked_at is None:
            return None
        payload = dict(row.payload_json or {})
        revoked_at = _ensure_utc(row.revoked_at) if row.revoked_at else None
        is_revoked = revoked_at is not None
        is_expired = exp <= cur
        sig_ok, sig_err = verify_signed_attestation(payload)
        subj = dict(payload.get("subject") or {})
        cov = dict(payload.get("coverage") or {})
        res = dict(payload.get("result") or {})

        if is_revoked:
            badge_state = "REVOKED"
        elif is_expired:
            badge_state = "EXPIRED"
        elif subj.get("kind") == "archive":
            badge_state = "ARCHIVE"
        else:
            badge_state = "VERIFIED"

        return {
            "attestation_id": row.id,
            "payload": payload,
            "is_revoked": is_revoked,
            "revoked_at": utc_iso_second(revoked_at) if revoked_at else None,
            "revoked_reason_code": row.revoked_reason_code,
            "is_expired": is_expired,
            "signature_valid": sig_ok,
            "signature_error": sig_err,
            "badge_state": badge_state,
            "partial": bool(cov.get("partial", False)),
            "score": int(res.get("overall", 0)),
            "phase": str(res.get("phase", "Prototype")),
        }


def revoke_attestation(attestation_id: str, reason_code: str) -> Dict[str, Any]:
    if reason_code not in VALID_REVOCATION_REASONS:
        raise AttestError(400, "invalid_reason_code", f"reason_code must be one of {sorted(VALID_REVOCATION_REASONS)}.")
    now = datetime.now(timezone.utc).replace(microsecond=0)
    with session_scope() as session:
        row = session.get(AttestationRow, attestation_id)
        if row is None:
            raise AttestError(404, "not_found", "Attestation not found.")
        if row.revoked_at is None:
            row.revoked_at = now
        row.revoked_reason_code = reason_code
        return {
            "id": row.id,
            "revoked_at": utc_iso_second(_ensure_utc(row.revoked_at)),
            "reason_code": row.revoked_reason_code,
        }


def list_revocations() -> List[Dict[str, str]]:
    with session_scope() as session:
        rows = session.execute(
            select(AttestationRow).where(AttestationRow.revoked_at.is_not(None)).order_by(asc(AttestationRow.revoked_at))
        ).scalars().all()
        return [
            {
                "id": r.id,
                "revoked_at": utc_iso_second(_ensure_utc(r.revoked_at)),
                "reason_code": r.revoked_reason_code or "owner_request",
            }
            for r in rows
            if r.revoked_at is not None
        ]


def get_staleness_ahead_by(subject: Dict[str, Any]) -> Optional[int]:
    """Optional cached 1h check of commits ahead on default branch for verified GitHub subjects."""
    if subject.get("kind") != "git" or not subject.get("control_verified"):
        return None
    repo = str(subject.get("repo") or "")
    commit = str(subject.get("commit") or "")
    if not repo or not commit:
        return None
    key = f"{repo}@{commit}"
    now_m = time.monotonic()
    cached = _STALENESS_CACHE.get(key)
    if cached and (now_m - cached[0]) < _STALENESS_TTL_SECONDS:
        return cached[1]
    try:
        headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": "CODIT-Verify/3.0"}
        if Config.GITHUB_API_TOKEN:
            headers["Authorization"] = f"token {Config.GITHUB_API_TOKEN}"
        with httpx.Client(timeout=2.5) as client:
            resp = client.get(f"https://api.github.com/repos/{repo}/compare/{commit}...HEAD", headers=headers)
            if resp.status_code == 200:
                ahead = resp.json().get("ahead_by")
                if isinstance(ahead, int):
                    _STALENESS_CACHE[key] = (now_m, ahead)
                    return ahead
    except Exception:
        pass
    _STALENESS_CACHE[key] = (now_m, None)
    return None
