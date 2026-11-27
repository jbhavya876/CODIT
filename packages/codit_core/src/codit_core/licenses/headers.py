"""Source-header SPDX/license scanner (LIC-007) and vendored LICENSE checker (LIC-008)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Optional, Set, Tuple

from codit_core.classify import language_of
from codit_core.licenses.classify import match_license_file_text
from codit_core.licenses.spdx import normalize_license_string

_SPDX_HEADER_RE = re.compile(r"SPDX-License-Identifier:\s*([^\r\n*]+)", re.IGNORECASE)
_PHRASE_HINTS: Tuple[Tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"GNU Affero General Public License", re.IGNORECASE), "AGPL-3.0-only"),
    (re.compile(r"GNU General Public License", re.IGNORECASE), "GPL-3.0-only"),
    (re.compile(r"Licensed under the Apache License", re.IGNORECASE), "Apache-2.0"),
    (re.compile(r"\bMIT License\b", re.IGNORECASE), "MIT"),
    (re.compile(r"Mozilla Public License", re.IGNORECASE), "MPL-2.0"),
)


@dataclass(frozen=True)
class HeaderLicenseHit:
    path: str
    line: int
    spdx_id: str
    license_class: str


def _is_vendored_path(norm_path: str) -> bool:
    parts = [p.lower() for p in norm_path.split("/")]
    return any(p in ("vendor", "third_party", "node_modules") for p in parts)


def scan_source_header(path: str, content: str) -> Optional[HeaderLicenseHit]:
    """Scan first 30 lines of an in-scope source file for explicit SPDX header or license phrase."""
    norm = path.replace("\\", "/")
    if _is_vendored_path(norm) or language_of(norm) is None:
        return None

    lines = (content or "").splitlines()[:30]
    for idx, line in enumerate(lines, 1):
        m = _SPDX_HEADER_RE.search(line)
        if m:
            raw_expr = m.group(1).strip().rstrip("*/").strip()
            nl = normalize_license_string(raw_expr)
            return HeaderLicenseHit(path=norm, line=idx, spdx_id=nl.spdx_id, license_class=nl.license_class)
        for pat, spdx in _PHRASE_HINTS:
            if pat.search(line):
                nl = normalize_license_string(spdx)
                return HeaderLicenseHit(path=norm, line=idx, spdx_id=nl.spdx_id, license_class=nl.license_class)
    return None


def scan_vendored_license_files(
    files: Iterable[Tuple[str, str]],
    *,
    project_spdx: str,
    declared_dep_names: Set[str],
) -> List[HeaderLicenseHit]:
    """
    Detect LICENSE/COPYING inside `vendor/` or `third_party/` whose license differs
    from the project's and which is not a declared dependency (LIC-008).
    """
    hits: List[HeaderLicenseHit] = []
    for raw_p, content in files:
        norm = raw_p.replace("\\", "/")
        parts = [p.lower() for p in norm.split("/")]
        if not any(p in ("vendor", "third_party") for p in parts):
            continue
        fname = parts[-1]
        if not (fname.startswith("license") or fname.startswith("copying")):
            continue
        # Check whether directory name corresponds to a declared dependency
        parent_dir = parts[-2] if len(parts) >= 2 else ""
        if parent_dir and parent_dir in declared_dep_names:
            continue
        matched = match_license_file_text(content)
        if not matched:
            continue
        if project_spdx != "LicenseRef-unknown" and matched.lower() == project_spdx.lower():
            continue
        nl = normalize_license_string(matched)
        hits.append(HeaderLicenseHit(path=norm, line=1, spdx_id=nl.spdx_id, license_class=nl.license_class))
    return hits
