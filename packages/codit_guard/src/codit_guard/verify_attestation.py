"""Offline Ed25519 verification helper for `codit-guard attest verify` (P4/P8)."""

from __future__ import annotations

import base64
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Tuple


def canonical_attestation_bytes(payload: Dict[str, Any]) -> bytes:
    """Produce deterministic canonical UTF-8 JSON bytes matching ADR-0003."""
    clean = {k: v for k, v in payload.items() if k != "signature"}
    _reject_floats(clean)
    return json.dumps(clean, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _reject_floats(obj: Any) -> None:
    if isinstance(obj, float):
        raise ValueError("Floating-point values are forbidden in codit.attestation.v1 payloads.")
    if isinstance(obj, dict):
        for v in obj.values():
            _reject_floats(v)
    elif isinstance(obj, list):
        for v in obj:
            _reject_floats(v)


def _load_json_source(url_or_file: str) -> Dict[str, Any]:
    if url_or_file.startswith(("https://", "http://")):
        with urllib.request.urlopen(url_or_file, timeout=5) as resp:
            return json.loads(resp.read(1024 * 1024).decode("utf-8"))
    return json.loads(Path(url_or_file).read_text(encoding="utf-8-sig"))


def _b64url_decode(data: str) -> bytes:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def verify_attestation_file(
    att_file: Path,
    *,
    keys_source: str,
    revocations_source: str | None = None,
    now: datetime | None = None,
) -> Tuple[bool, str]:
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError as exc:  # pragma: no cover
        return False, "Install codit-guard[verify] (cryptography) to verify attestations."

    payload = json.loads(att_file.read_text(encoding="utf-8-sig"))
    sig_obj = payload.get("signature") or {}
    kid = sig_obj.get("kid")
    sig_b64 = sig_obj.get("sig")
    if sig_obj.get("alg") != "Ed25519" or not kid or not sig_b64:
        return False, "Missing or unsupported Ed25519 signature envelope."

    keys_doc = _load_json_source(keys_source)
    key_entry = next((k for k in keys_doc.get("keys", []) if k.get("kid") == kid), None)
    if key_entry is None:
        return False, f"Unknown signing key id '{kid}'."

    pub_bytes = _b64url_decode(key_entry["public_key"])
    pub_key = Ed25519PublicKey.from_public_bytes(pub_bytes)
    try:
        msg_bytes = canonical_attestation_bytes(payload)
        pub_key.verify(_b64url_decode(sig_b64), msg_bytes)
    except Exception:
        return False, "Invalid Ed25519 signature (payload modified or wrong key)."

    cur_dt = now or datetime.now(timezone.utc)
    exp_raw = payload.get("expires_at")
    if exp_raw:
        exp_dt = datetime.fromisoformat(exp_raw.replace("Z", "+00:00"))
        if exp_dt <= cur_dt:
            return False, f"Attestation expired at {exp_raw}."

    if revocations_source:
        try:
            rev_doc = _load_json_source(revocations_source)
            revoked_ids = {r.get("id"): r.get("reason_code") for r in rev_doc.get("revoked", [])}
            att_id = payload.get("attestation_id")
            if att_id in revoked_ids:
                return False, f"Attestation revoked ({revoked_ids[att_id]})."
        except Exception:
            pass

    return True, f"Valid Ed25519 signature (kid={kid}, id={payload.get('attestation_id')})."
