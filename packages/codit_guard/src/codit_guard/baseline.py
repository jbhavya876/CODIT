"""Guard baseline storage (`.codit/baseline.json`) for incremental adoption."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Set

from codit_core.findings import CoreFinding

BASELINE_REL_PATH = ".codit/baseline.json"


def parse_baseline_json(raw: str) -> Set[str]:
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError:
        return set()
    entries = doc.get("entries", []) if isinstance(doc, dict) else []
    return {e["fingerprint"] for e in entries if isinstance(e, dict) and e.get("fingerprint")}


def load_baseline_from_disk(repo_root: Path) -> Set[str]:
    bp = repo_root / BASELINE_REL_PATH
    if not bp.exists():
        return set()
    return parse_baseline_json(bp.read_text(encoding="utf-8-sig"))


def save_baseline(repo_root: Path, findings: List[CoreFinding], *, merge_existing: bool = False) -> Path:
    bp = repo_root / BASELINE_REL_PATH
    bp.parent.mkdir(parents=True, exist_ok=True)
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    entries_by_fp: Dict[str, Dict[str, Any]] = {}
    if merge_existing and bp.exists():
        try:
            old = json.loads(bp.read_text(encoding="utf-8-sig"))
            for item in old.get("entries", []):
                if isinstance(item, dict) and item.get("fingerprint"):
                    entries_by_fp[item["fingerprint"]] = item
        except json.JSONDecodeError:
            pass

    for f in findings:
        if f.fingerprint and f.fingerprint not in entries_by_fp:
            entries_by_fp[f.fingerprint] = {
                "fingerprint": f.fingerprint,
                "rule_id": f.rule_id,
                "path": f.evidence_file,
                "first_seen": now_iso,
            }

    payload = {
        "version": 1,
        "created": now_iso,
        "entries": sorted(entries_by_fp.values(), key=lambda e: (e["path"], e["rule_id"], e["fingerprint"])),
    }
    bp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return bp
