"""
Offline Ed25519 keygen and rotation helper for CODIT attestations (P8 / Section 14).

Security guarantees:
- Writes the private seed ONLY to a 0600 file path (`--key-out`); NEVER prints it to stdout or logs.
- Prints ONLY the public key metadata (`kid`, `alg`, `public_key`, `status`, `not_before`).
- With `--publish`, safely adds the new public key to `backend/app/attest/keys_public.json`
  and retires any previous `"active"` key to `"retired"` (never deleting historical public keys).
"""

from __future__ import annotations

import argparse
import base64
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_KEYS_PUBLIC = ROOT / "backend" / "app" / "attest" / "keys_public.json"


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def generate_keypair(
    *,
    kid: str,
    key_out: Path,
    keys_public_path: Path = DEFAULT_KEYS_PUBLIC,
    publish: bool = False,
) -> dict[str, str]:
    priv = Ed25519PrivateKey.generate()
    seed_b64 = base64.b64encode(priv.private_bytes_raw()).decode("ascii")
    pub_b64u = _b64url(priv.public_key().public_bytes_raw())
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    key_out.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(key_out), os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(f"ATTEST_KEY_ID={kid}\nATTEST_SIGNING_KEY={seed_b64}\n")

    pub_entry = {
        "kid": kid,
        "alg": "Ed25519",
        "public_key": pub_b64u,
        "status": "active",
        "not_before": now_iso,
    }

    if publish:
        if keys_public_path.exists():
            doc = json.loads(keys_public_path.read_text(encoding="utf-8-sig"))
        else:
            doc = {"keys": []}
        existing = list(doc.get("keys") or [])
        for entry in existing:
            if entry.get("status") == "active" and entry.get("kid") != kid:
                entry["status"] = "retired"
        updated = [pub_entry] + [e for e in existing if e.get("kid") != kid]
        keys_public_path.parent.mkdir(parents=True, exist_ok=True)
        keys_public_path.write_text(json.dumps({"keys": updated}, indent=2) + "\n", encoding="utf-8")

    return pub_entry


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline Ed25519 keygen/rotation for CODIT attestations.")
    parser.add_argument(
        "--kid",
        default=datetime.now(timezone.utc).strftime("%Y-%m-a"),
        help="Key identifier (default YYYY-MM-a)",
    )
    parser.add_argument(
        "--key-out",
        default=str(ROOT / ".secrets" / "attest_signing.key"),
        help="0600 file path to write ATTEST_SIGNING_KEY seed (never printed to stdout)",
    )
    parser.add_argument(
        "--keys-public",
        default=str(DEFAULT_KEYS_PUBLIC),
        help="Path to keys_public.json",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Rotate keys_public.json in-place (retiring prior active key, keeping all retired keys)",
    )
    args = parser.parse_args()
    pub_entry = generate_keypair(
        kid=args.kid,
        key_out=Path(args.key_out),
        keys_public_path=Path(args.keys_public),
        publish=args.publish,
    )
    print(f"Wrote private seed (mode 0600) to: {args.key_out}")
    print("Public key metadata (safe to publish):")
    print(json.dumps(pub_entry, indent=2))


if __name__ == "__main__":
    main()
