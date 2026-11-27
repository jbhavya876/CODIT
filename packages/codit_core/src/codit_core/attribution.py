"""Signal-based AI agent attribution (P2)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

import yaml

ATTRIBUTION_LIMITATION = (
    "Attribution reflects declarations in commit metadata. "
    "Commits without a declaration are unknown, not human-authored."
)

_TRAILER_LINE_RE = re.compile(r"^([A-Za-z][A-Za-z0-9-]*)\s*:\s*(.+)$")


@dataclass(frozen=True)
class CommitAttribution:
    agent_id: Optional[str]
    basis: Literal["trailer", "bot_account", "footer", "none"]
    confidence: Literal["high", "none"]
    has_agent_trailer: bool

    @property
    def status(self) -> str:
        return "declared" if self.agent_id is not None else "unknown"


@lru_cache(maxsize=1)
def load_signatures_config() -> Dict[str, Any]:
    sig_path = Path(__file__).with_name("signatures.yaml")
    data = yaml.safe_load(sig_path.read_text(encoding="utf-8")) or {}
    compiled_sigs: List[Dict[str, Any]] = []
    for entry in data.get("signatures", []):
        compiled_sigs.append({
            "agent_id": entry["agent_id"],
            "kind": entry["kind"],
            "key": (entry.get("key") or "").lower(),
            "regex": re.compile(entry["match"]),
            "notes": entry.get("notes", ""),
            "last_verified": entry.get("last_verified", ""),
        })
    return {
        "signatures": compiled_sigs,
        "tooling_files": list(data.get("tooling_files", [])),
    }


def extract_final_paragraph_lines(message: str) -> List[str]:
    """Return un-quoted, un-indented lines of the final non-empty paragraph."""
    raw_lines = (message or "").replace("\r\n", "\n").rstrip("\n").splitlines()
    # Strip trailing blank lines
    while raw_lines and not raw_lines[-1].strip():
        raw_lines.pop()
    if not raw_lines:
        return []

    para: List[str] = []
    for line in reversed(raw_lines):
        if not line.strip():
            break
        para.append(line)
    para.reverse()

    clean: List[str] = []
    for line in para:
        # Ignore quoted blocks and indented blocks (adversarial fake trailers)
        if line.startswith(">") or (line and line[0].isspace()):
            continue
        clean.append(line.strip())
    return clean


def parse_final_paragraph_trailers(message: str) -> List[Tuple[str, str]]:
    """Parse git Key: value trailers strictly from the final non-quoted paragraph."""
    lines = extract_final_paragraph_lines(message)
    trailers: List[Tuple[str, str]] = []
    for line in lines:
        m = _TRAILER_LINE_RE.match(line)
        if m:
            trailers.append((m.group(1).lower(), m.group(2).strip()))
    return trailers


def attribute_commit(message: str, author_raw: str = "") -> CommitAttribution:
    """
    Evaluate real commit metadata signals cleanly against signatures.yaml.
    Priority: trailer -> bot_account -> footer -> unknown (none).
    Never emits 'human' or infers from style/timing.
    """
    cfg = load_signatures_config()
    sigs = cfg["signatures"]

    trailers = parse_final_paragraph_trailers(message)
    for sig in sigs:
        if sig["kind"] == "trailer":
            expected_key = sig["key"]
            for k, val in trailers:
                if (not expected_key or k == expected_key) and sig["regex"].search(val):
                    return CommitAttribution(
                        agent_id=sig["agent_id"],
                        basis="trailer",
                        confidence="high",
                        has_agent_trailer=True,
                    )

    for sig in sigs:
        if sig["kind"] == "bot_account" and author_raw:
            if sig["regex"].search(author_raw):
                return CommitAttribution(
                    agent_id=sig["agent_id"],
                    basis="bot_account",
                    confidence="high",
                    has_agent_trailer=False,
                )

    final_lines = extract_final_paragraph_lines(message)
    for sig in sigs:
        if sig["kind"] == "footer":
            for line in final_lines:
                if sig["regex"].search(line):
                    return CommitAttribution(
                        agent_id=sig["agent_id"],
                        basis="footer",
                        confidence="high",
                        has_agent_trailer=True,
                    )

    return CommitAttribution(
        agent_id=None,
        basis="none",
        confidence="none",
        has_agent_trailer=False,
    )
