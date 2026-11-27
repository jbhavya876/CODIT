"""Project license detection from .codit.yml, LICENSE/COPYING texts, and manifests."""

from __future__ import annotations

import difflib
import json
import re
from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Tuple

from codit_core.licenses.spdx import NormalizedLicense, normalize_license_string

try:
    import tomllib
except ImportError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

CANONICAL_LICENSE_SNIPPETS: Dict[str, str] = {
    "MIT": (
        "permission is hereby granted free of charge to any person obtaining a copy "
        "of this software and associated documentation files the software to deal "
        "in the software without restriction including without limitation the rights "
        "to use copy modify merge publish distribute sublicense and or sell copies"
    ),
    "Apache-2.0": (
        "apache license version 2.0 january 2004 terms and conditions for use "
        "reproduction and distribution grant of copyright license grant of patent license"
    ),
    "BSD-3-Clause": (
        "redistribution and use in source and binary forms with or without modification "
        "are permitted provided that the following conditions are met neither the name of "
        "the copyright holder nor the names of its contributors may be used to endorse"
    ),
    "BSD-2-Clause": (
        "redistribution and use in source and binary forms with or without modification "
        "are permitted provided that the following conditions are met redistributions of "
        "source code must retain the above copyright notice"
    ),
    "ISC": (
        "permission to use copy modify and or distribute this software for any purpose "
        "with or without fee is hereby granted provided that the above copyright notice "
        "and this permission notice appear in all copies"
    ),
    "MPL-2.0": (
        "mozilla public license version 2.0 exhibits a b incompatible with secondary licenses "
        "covered software larger work"
    ),
    "GPL-3.0-only": (
        "gnu general public license version 3 29 june 2007 everyone is permitted to copy "
        "and distribute verbatim copies of this license document but changing it is not allowed"
    ),
    "GPL-2.0-only": (
        "gnu general public license version 2 june 1991 free software foundation inc "
        "everyone is permitted to copy and distribute verbatim copies of this license document"
    ),
    "AGPL-3.0-only": (
        "gnu affero general public license version 3 19 november 2007 remote network interaction"
    ),
    "Unlicense": (
        "this is free and unencumbered software released into the public domain anyone is free "
        "to copy modify publish use compile sell or distribute this software"
    ),
}

_MARKER_HINTS: Tuple[Tuple[str, str], ...] = (
    ("gnu affero general public license", "AGPL-3.0-only"),
    ("gnu general public license version 3", "GPL-3.0-only"),
    ("gnu general public license version 2", "GPL-2.0-only"),
    ("apache license version 2.0", "Apache-2.0"),
    ("mozilla public license version 2.0", "MPL-2.0"),
    ("permission is hereby granted free of charge", "MIT"),
    ("permission to use copy modify and or distribute this software for any purpose with or without fee", "ISC"),
    ("free and unencumbered software released into the public domain", "Unlicense"),
    ("neither the name of", "BSD-3-Clause"),
    ("redistributions of source code must retain the above copyright notice", "BSD-2-Clause"),
)


def _normalize_prose(text: str) -> str:
    return re.sub(r"[^a-z0-9.]+", " ", (text or "").lower()).strip()


def match_license_file_text(text: str) -> Optional[str]:
    """Match a LICENSE/COPYING file using canonical normalized text similarity >= 0.90 or exact header."""
    norm = _normalize_prose(text)
    if not norm:
        return None

    for phrase, spdx in _MARKER_HINTS:
        if phrase in norm:
            # Verify snippet similarity or canonical presence
            snippet = CANONICAL_LICENSE_SNIPPETS.get(spdx, "")
            if len(norm) >= 60:
                ratio = difflib.SequenceMatcher(None, norm[: len(snippet) + 120], snippet).ratio()
                if ratio >= 0.90 or phrase in norm[:300]:
                    return spdx
            return spdx

    best_id: Optional[str] = None
    best_ratio = 0.0
    for spdx, snippet in CANONICAL_LICENSE_SNIPPETS.items():
        r = difflib.SequenceMatcher(None, norm[: len(snippet) + 80], snippet).ratio()
        if r >= 0.90 and r > best_ratio:
            best_ratio = r
            best_id = spdx
    return best_id


@dataclass(frozen=True)
class ProjectLicenseInfo:
    spdx_id: str
    license_class: str
    source: str  # "config" | "license_file" | "manifest" | "unknown"
    evidence_file: str


def resolve_project_license(
    files: Iterable[Tuple[str, str]],
    *,
    config_project_license: Optional[str] = None,
) -> ProjectLicenseInfo:
    """
    Determine project license in priority order:
    1) `.codit.yml` `project_license`
    2) Root LICENSE/COPYING file
    3) Manifest license field (package.json / pyproject.toml)
    4) unknown
    """
    if config_project_license:
        nl = normalize_license_string(config_project_license)
        return ProjectLicenseInfo(
            spdx_id=nl.spdx_id,
            license_class=nl.license_class,
            source="config",
            evidence_file=".codit.yml",
        )

    file_list = [(p.replace("\\", "/"), c) for p, c in files]

    # Check root LICENSE / COPYING files
    for p, content in file_list:
        low = p.lower()
        if "/" not in low and (low.startswith("license") or low.startswith("copying")):
            matched = match_license_file_text(content)
            if matched:
                nl = normalize_license_string(matched)
                return ProjectLicenseInfo(
                    spdx_id=nl.spdx_id,
                    license_class=nl.license_class,
                    source="license_file",
                    evidence_file=p,
                )

    # Check root manifest license fields
    for p, content in file_list:
        low = p.lower()
        if low == "package.json":
            try:
                doc = json.loads(content)
                lic_val = doc.get("license")
                if isinstance(lic_val, str) and lic_val.strip():
                    nl = normalize_license_string(lic_val)
                    if nl.spdx_id != "LicenseRef-unknown":
                        return ProjectLicenseInfo(
                            spdx_id=nl.spdx_id,
                            license_class=nl.license_class,
                            source="manifest",
                            evidence_file=p,
                        )
            except Exception:
                pass
        elif low == "pyproject.toml":
            try:
                doc = tomllib.loads(content)
                lic_obj = (doc.get("project") or {}).get("license")
                lic_str = lic_obj.get("text") if isinstance(lic_obj, dict) else lic_obj
                if isinstance(lic_str, str) and lic_str.strip():
                    nl = normalize_license_string(lic_str)
                    if nl.spdx_id != "LicenseRef-unknown":
                        return ProjectLicenseInfo(
                            spdx_id=nl.spdx_id,
                            license_class=nl.license_class,
                            source="manifest",
                            evidence_file=p,
                        )
            except Exception:
                pass

    return ProjectLicenseInfo(
        spdx_id="LicenseRef-unknown",
        license_class="unknown",
        source="unknown",
        evidence_file="package.json",
    )
