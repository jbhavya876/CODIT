"""Canonical JSON serialization (ADR-0003), float rejection, and findings digest."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Tuple


def reject_floats(obj: Any) -> None:
    """Reject floating-point values anywhere in an attestation payload (ADR-0003)."""
    if isinstance(obj, float):
        raise ValueError("Floating-point values are forbidden in codit.attestation.v1 payloads.")
    if isinstance(obj, dict):
        for v in obj.values():
            reject_floats(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            reject_floats(v)


def canonical_attestation_bytes(payload: Dict[str, Any]) -> bytes:
    """Canonical UTF-8 bytes excluding `signature`, keys sorted, compact separators, no floats."""
    clean = {k: v for k, v in payload.items() if k != "signature"}
    reject_floats(clean)
    return json.dumps(clean, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def utc_iso_second(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def compute_findings_digest(findings: Iterable[Tuple[str, str, str]]) -> str:
    """Compute sha256:<hex> over sorted canonical JSON of [(rule_id, fingerprint, severity)]."""
    ordered: List[List[str]] = sorted([str(r), str(fp), str(sev)] for r, fp, sev in findings)
    raw = json.dumps(ordered, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"
