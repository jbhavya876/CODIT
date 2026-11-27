"""
Ed25519 attestation signing and public-key registry loader (P8).

Security invariants:
- `ATTEST_SIGNING_KEY` (base64/base64url 32-byte Ed25519 seed) is read strictly from env/config
  and is NEVER logged, persisted, or returned in any HTTP response.
- Fail-closed: missing/invalid signing key raises `AttestationUnavailableError` -> 503.
- `keys_public.json` retains retired public keys forever so historical attestations verify.
"""

from __future__ import annotations

import base64
import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from backend.app.attest.canonical import canonical_attestation_bytes, utc_iso_second
from backend.app.config import Config


class AttestationUnavailableError(RuntimeError):
    """Raised when Ed25519 signing key material is absent or invalid (503)."""


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64_decode_any(raw_str: str) -> bytes:
    cleaned = raw_str.strip()
    if not cleaned:
        raise ValueError("empty key")
    # Support standard base64 or base64url with/without padding
    padded = cleaned + "=" * (-len(cleaned) % 4)
    try:
        return base64.urlsafe_b64decode(padded.encode("ascii"))
    except Exception:
        return base64.b64decode(padded.encode("ascii"))


def _load_active_private_key() -> Tuple[str, Ed25519PrivateKey]:
    raw_seed = os.getenv("ATTEST_SIGNING_KEY") or Config.ATTEST_SIGNING_KEY
    if not raw_seed:
        raise AttestationUnavailableError("Attestation signing key is not configured.")
    kid = (os.getenv("ATTEST_KEY_ID") or Config.ATTEST_KEY_ID or "default").strip()
    try:
        seed_bytes = _b64_decode_any(raw_seed)
        if len(seed_bytes) != 32:
            raise ValueError("Ed25519 seed must be 32 bytes")
        priv = Ed25519PrivateKey.from_private_bytes(seed_bytes)
        return kid, priv
    except Exception as exc:
        raise AttestationUnavailableError("Invalid attestation signing key format.") from exc


def sign_attestation_payload(payload_without_sig: Dict[str, Any]) -> Dict[str, Any]:
    """Attach canonical Ed25519 signature envelope to payload."""
    kid, priv = _load_active_private_key()
    msg_bytes = canonical_attestation_bytes(payload_without_sig)
    sig_bytes = priv.sign(msg_bytes)
    signed = dict(payload_without_sig)
    signed["signature"] = {
        "alg": "Ed25519",
        "kid": kid,
        "sig": _b64url_encode(sig_bytes),
    }
    return signed


def get_public_keys_document() -> Dict[str, Any]:
    """
    Return `{keys: [...]}` combining permanent published public keys in `keys_public.json`
    with the currently configured active public key (derived in memory from ATTEST_SIGNING_KEY).
    Never exposes private material.
    """
    keys_path = Path(__file__).with_name("keys_public.json")
    try:
        doc = json.loads(keys_path.read_text(encoding="utf-8-sig"))
    except Exception:
        doc = {"keys": []}
    entries: List[Dict[str, Any]] = list(doc.get("keys") or [])
    known_kids = {k.get("kid") for k in entries if k.get("kid")}

    try:
        kid, priv = _load_active_private_key()
        pub_raw = priv.public_key().public_bytes_raw()
        pub_b64u = _b64url_encode(pub_raw)
        if kid not in known_kids:
            entries.insert(
                0,
                {
                    "kid": kid,
                    "alg": "Ed25519",
                    "public_key": pub_b64u,
                    "status": "active",
                    "not_before": utc_iso_second(__import__("datetime").datetime.now(__import__("datetime").timezone.utc)),
                },
            )
    except AttestationUnavailableError:
        pass

    return {"keys": entries}


def verify_signed_attestation(payload: Dict[str, Any], keys_doc: Optional[Dict[str, Any]] = None) -> Tuple[bool, Optional[str]]:
    """Verify Ed25519 signature server-side against published/active public keys."""
    sig_obj = payload.get("signature") or {}
    if sig_obj.get("alg") != "Ed25519":
        return False, "unsupported_alg"
    kid = sig_obj.get("kid")
    sig_b64 = sig_obj.get("sig")
    if not kid or not sig_b64:
        return False, "missing_signature"

    doc = keys_doc or get_public_keys_document()
    key_entry = next((k for k in doc.get("keys", []) if k.get("kid") == kid), None)
    if key_entry is None:
        return False, "unknown_kid"

    try:
        pub_bytes = _b64_decode_any(str(key_entry["public_key"]))
        pub = Ed25519PublicKey.from_public_bytes(pub_bytes)
        msg_bytes = canonical_attestation_bytes(payload)
        sig_bytes = _b64_decode_any(str(sig_b64))
        pub.verify(sig_bytes, msg_bytes)
        return True, None
    except Exception:
        return False, "invalid_signature"
