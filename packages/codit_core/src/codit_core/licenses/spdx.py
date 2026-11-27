"""SPDX license normalization and expression resolution via `license-expression`."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional, Tuple

import yaml

CLASS_RANK: Dict[str, int] = {
    "permissive": 0,
    "weak_copyleft": 1,
    "source_available": 2,
    "strong_copyleft": 3,
    "network_copyleft": 4,
    "unknown": 5,
    "proprietary": 6,
}

_COMMON_ALIASES: Dict[str, str] = {
    "mit": "MIT",
    "mit license": "MIT",
    "the mit license": "MIT",
    "expat": "MIT",
    "apache 2.0": "Apache-2.0",
    "apache-2": "Apache-2.0",
    "apache 2": "Apache-2.0",
    "apache license 2.0": "Apache-2.0",
    "apache software license": "Apache-2.0",
    "asl 2.0": "Apache-2.0",
    "bsd": "BSD-3-Clause",
    "bsd license": "BSD-3-Clause",
    "bsd 3-clause": "BSD-3-Clause",
    "3-clause bsd": "BSD-3-Clause",
    "new bsd license": "BSD-3-Clause",
    "bsd 2-clause": "BSD-2-Clause",
    "isc": "ISC",
    "isc license": "ISC",
    "0bsd": "0BSD",
    "unlicense": "Unlicense",
    "the unlicense": "Unlicense",
    "cc0": "CC0-1.0",
    "cc0-1.0": "CC0-1.0",
    "zlib": "Zlib",
    "psf": "PSF-2.0",
    "psf-2.0": "PSF-2.0",
    "python software foundation license": "PSF-2.0",
    "mpl 2.0": "MPL-2.0",
    "mpl-2.0": "MPL-2.0",
    "mozilla public license 2.0": "MPL-2.0",
    "lgpl-2.1": "LGPL-2.1-only",
    "lgpl-2.1+": "LGPL-2.1-or-later",
    "lgpl-3.0": "LGPL-3.0-only",
    "lgpl-3.0+": "LGPL-3.0-or-later",
    "gpl-2.0": "GPL-2.0-only",
    "gplv2": "GPL-2.0-only",
    "gpl-2.0+": "GPL-2.0-or-later",
    "gpl-3.0": "GPL-3.0-only",
    "gplv3": "GPL-3.0-only",
    "gpl-3.0+": "GPL-3.0-or-later",
    "agpl-3.0": "AGPL-3.0-only",
    "agplv3": "AGPL-3.0-only",
    "agpl-3.0+": "AGPL-3.0-or-later",
    "sspl-1.0": "SSPL-1.0",
    "epl-1.0": "EPL-1.0",
    "epl-2.0": "EPL-2.0",
    "cddl-1.0": "CDDL-1.0",
    "cddl-1.1": "CDDL-1.1",
    "busl-1.1": "BUSL-1.1",
    "elastic-2.0": "Elastic-2.0",
}


@dataclass(frozen=True)
class NormalizedLicense:
    spdx_id: str
    license_class: str
    confidence: str  # "high" | "low"
    note: Optional[str] = None


@lru_cache(maxsize=1)
def _load_classes_map() -> Tuple[Dict[str, str], Dict[str, Tuple[str, ...]]]:
    data = yaml.safe_load(Path(__file__).with_name("classes.yaml").read_text(encoding="utf-8")) or {}
    exact: Dict[str, str] = {}
    for cls_name, ids in (data.get("classes") or {}).items():
        for sid in ids or []:
            exact[sid.lower()] = cls_name
    prefixes: Dict[str, Tuple[str, ...]] = {}
    for cls_name, pref_list in (data.get("prefixes") or {}).items():
        prefixes[cls_name] = tuple(p.lower() for p in (pref_list or []))
    return exact, prefixes


def classify_spdx_symbol(symbol: str) -> str:
    norm = symbol.strip()
    low = norm.lower()
    if low == "proprietary":
        return "proprietary"
    exact, prefixes = _load_classes_map()
    if low in exact:
        return exact[low]
    # Handle + suffix (e.g. GPL-3.0+) or base matching
    if low.endswith("+"):
        base = low[:-1] + "-or-later"
        if base in exact:
            return exact[base]
    for cls_name, pref_tuple in prefixes.items():
        if any(low.startswith(p) for p in pref_tuple):
            return cls_name
    return "unknown"


def _pre_normalize_string(raw: str) -> Optional[str]:
    if not raw:
        return None
    s = raw.strip()
    low = s.lower()
    if not s or low in ("none", "unknown", "custom", "unspecified") or low.startswith("see license in "):
        return None
    if low == "proprietary":
        return "proprietary"
    # Handle PyPI trove classifiers cleanly
    if "license :: osi approved ::" in low:
        tail = s.split("::")[-1].strip().lower()
        return _COMMON_ALIASES.get(tail, tail)
    if low in _COMMON_ALIASES:
        return _COMMON_ALIASES[low]
    # Normalize deprecated SPDX tokens inside expressions (e.g. `GPL-2.0 OR MIT`)
    s = re.sub(r"\bLGPL-2\.1\+", "LGPL-2.1-or-later", s, flags=re.IGNORECASE)
    s = re.sub(r"\bLGPL-3\.0\+", "LGPL-3.0-or-later", s, flags=re.IGNORECASE)
    s = re.sub(r"\bGPL-2\.0\+", "GPL-2.0-or-later", s, flags=re.IGNORECASE)
    s = re.sub(r"\bGPL-3\.0\+", "GPL-3.0-or-later", s, flags=re.IGNORECASE)
    s = re.sub(r"\bAGPL-3\.0\+", "AGPL-3.0-or-later", s, flags=re.IGNORECASE)
    s = re.sub(r"\bGPL-2\.0\b(?!-)", "GPL-2.0-only", s, flags=re.IGNORECASE)
    s = re.sub(r"\bGPL-3\.0\b(?!-)", "GPL-3.0-only", s, flags=re.IGNORECASE)
    s = re.sub(r"\bAGPL-3\.0\b(?!-)", "AGPL-3.0-only", s, flags=re.IGNORECASE)
    s = re.sub(r"\bLGPL-2\.1\b(?!-)", "LGPL-2.1-only", s, flags=re.IGNORECASE)
    s = re.sub(r"\bLGPL-3\.0\b(?!-)", "LGPL-3.0-only", s, flags=re.IGNORECASE)
    return s


def _eval_expr_node(node) -> NormalizedLicense:
    from license_expression import AND, OR, LicenseWithExceptionSymbol

    if isinstance(node, LicenseWithExceptionSymbol):
        base_sym = str(node.license_symbol.key)
        base_cls = classify_spdx_symbol(base_sym)
        if base_cls == "strong_copyleft":
            return NormalizedLicense(
                spdx_id=f"{base_sym} WITH {node.exception_symbol.key}",
                license_class="weak_copyleft",
                confidence="low",
                note="linking_exception",
            )
        return NormalizedLicense(
            spdx_id=f"{base_sym} WITH {node.exception_symbol.key}",
            license_class=base_cls,
            confidence="low",
            note="linking_exception",
        )

    if isinstance(node, OR):
        branches = [_eval_expr_node(ch) for ch in node.args]
        chosen = min(branches, key=lambda b: CLASS_RANK.get(b.license_class, 5))
        return NormalizedLicense(
            spdx_id=chosen.spdx_id,
            license_class=chosen.license_class,
            confidence=chosen.confidence,
            note=chosen.note or "dual_license_least_restrictive",
        )

    if isinstance(node, AND):
        branches = [_eval_expr_node(ch) for ch in node.args]
        chosen = max(branches, key=lambda b: CLASS_RANK.get(b.license_class, 5))
        return NormalizedLicense(
            spdx_id=str(node),
            license_class=chosen.license_class,
            confidence=chosen.confidence,
            note=chosen.note or "conjunctive_most_restrictive",
        )

    sym = str(getattr(node, "key", node))
    cls = classify_spdx_symbol(sym)
    return NormalizedLicense(spdx_id=sym, license_class=cls, confidence="high")


def normalize_license_string(raw: Optional[str]) -> NormalizedLicense:
    """
    Normalize a raw license declaration to an SPDX expression & class.
    Unparseable inputs become LicenseRef-unknown without retaining raw text.
    """
    pre = _pre_normalize_string(raw or "")
    if pre is None:
        return NormalizedLicense(spdx_id="LicenseRef-unknown", license_class="unknown", confidence="high")
    if pre == "proprietary":
        return NormalizedLicense(spdx_id="proprietary", license_class="proprietary", confidence="high")

    from license_expression import get_spdx_licensing

    licensing = get_spdx_licensing()
    try:
        parsed = licensing.parse(pre, validate=False)
        if parsed is None:
            return NormalizedLicense(spdx_id="LicenseRef-unknown", license_class="unknown", confidence="high")
        # Check whether unknown arbitrary tokens were injected when single unvalidated symbol
        res = _eval_expr_node(parsed)
        # Validate single leaves against known classes or SPDX table
        if res.license_class == "unknown":
            valid = licensing.parse(pre, validate=True)
            if valid is None:
                return NormalizedLicense(spdx_id="LicenseRef-unknown", license_class="unknown", confidence="high")
        return res
    except Exception:
        return NormalizedLicense(spdx_id="LicenseRef-unknown", license_class="unknown", confidence="high")
