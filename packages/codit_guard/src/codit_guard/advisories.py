"""Optional network-backed advisory lookups for newly added dependencies (fail-open, 2s budget)."""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from codit_core.delta import CommitDelta
from codit_core.findings import CoreFinding
from codit_core.fingerprint import compute_fingerprint

OSV_BATCH_URL = "https://api.osv.dev/v1/querybatch"
TOTAL_BUDGET_SECONDS = 2.0

_REQ_PIN_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([A-Za-z0-9._+-]+)")


def _extract_added_coords(deltas: List[CommitDelta]) -> List[Tuple[str, str, str, str, int]]:
    """Return [(ecosystem, name, version, path, lineno)] from added manifest/lockfile lines."""
    coords: List[Tuple[str, str, str, str, int]] = []
    seen: set[Tuple[str, str, str]] = set()
    for cd in deltas:
        for fd in cd.files:
            fname = fd.path.replace("\\", "/").lower().rsplit("/", 1)[-1]
            if fname == "requirements.txt":
                for al in fd.added:
                    m = _REQ_PIN_RE.match(al.text.strip())
                    if m:
                        name, ver = m.group(1), m.group(2)
                        key = ("PyPI", name, ver)
                        if key not in seen:
                            seen.add(key)
                            coords.append(("PyPI", name, ver, fd.path, al.lineno))
            elif fname == "package.json":
                for al in fd.added:
                    m = re.match(r'^"([^"]+)"\s*:\s*"[\^~]?(\d+\.\d+\.\d+[^"]*)"', al.text.strip())
                    if m:
                        name, ver = m.group(1), m.group(2)
                        if name not in ("version", "name"):
                            key = ("npm", name, ver)
                            if key not in seen:
                                seen.add(key)
                                coords.append(("npm", name, ver, fd.path, al.lineno))
    return coords


def lookup_added_advisories(
    deltas: List[CommitDelta],
    *,
    offline: bool = False,
) -> Tuple[List[CoreFinding], List[Dict[str, Optional[str]]]]:
    """
    Query OSV querybatch ONLY with `(ecosystem, name, version)` for added packages.
    Never uploads source; never blocks on network error (always fails open to not_assessed).
    """
    if offline:
        return [], []

    coords = _extract_added_coords(deltas)
    if not coords:
        return [], []

    payload = {
        "queries": [
            {"package": {"ecosystem": eco, "name": name}, "version": ver}
            for eco, name, ver, _p, _ln in coords[:50]
        ]
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        OSV_BATCH_URL,
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": "codit-guard/3.0.0"},
        method="POST",
    )

    deadline = time.monotonic() + TOTAL_BUDGET_SECONDS
    try:
        remaining = max(0.2, deadline - time.monotonic())
        with urllib.request.urlopen(req, timeout=remaining) as resp:
            raw = resp.read(1024 * 1024)
        parsed = json.loads(raw.decode("utf-8", errors="replace"))
    except Exception:
        return [], [{"check": "advisories", "reason": "lookup_unavailable", "path": None}]

    results = parsed.get("results") or []
    findings: List[CoreFinding] = []
    for coord, res_item in zip(coords, results):
        eco, name, ver, path, lineno = coord
        vulns = res_item.get("vulns") or []
        for v in vulns[:2]:
            vid = str(v.get("id") or "OSV-ADVISORY")
            fp = compute_fingerprint(vid, path, f"{eco}:{name}@{ver}")
            findings.append(
                CoreFinding(
                    id=f"adv-{fp[:8]}-{lineno}",
                    dimension="security",
                    severity="high",
                    confidence="high",
                    description=f"Added dependency {name}=={ver} ({eco}) matches advisory {vid}.",
                    evidence_file=path,
                    evidence_line=lineno,
                    rule_id=vid,
                    remediation=f"Upgrade {name} to a non-vulnerable release.",
                    component_id=path,
                    fingerprint=fp,
                    basis="PATTERN",
                )
            )
    return findings, []
