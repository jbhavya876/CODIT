"""
SSRF-hardened dependency license resolver with SQLAlchemy cache and budget enforcement (P5).

Resolution order:
  1. Lockfile-embedded license field
  2. SQLAlchemy `license_cache` (7-day TTL)
  3. `https://api.deps.dev/v3/systems/{npm|pypi}/packages/{name}/versions/{version}`
  4. Fallbacks: `registry.npmjs.org` or `pypi.org`
"""

from __future__ import annotations

import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote, urlparse

import httpx

from codit_core.licenses.spdx import NormalizedLicense, normalize_license_string

from backend.app.config import Config
from backend.app.db.engine import session_scope
from backend.app.db.models import LicenseCacheRow
from backend.app.parsers.manifest.lockfiles import LockDependency

log = logging.getLogger(__name__)

ALLOWED_LICENSE_HOSTS = frozenset({"api.deps.dev", "registry.npmjs.org", "pypi.org"})
NPM_NAME_RE = re.compile(r"^(@[a-z0-9-~][a-z0-9-._~]*/)?[a-z0-9-~][a-z0-9-._~]*$")
PYPI_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,127}$")
MAX_RESPONSE_BYTES = 1024 * 1024
CACHE_TTL_DAYS = 7


class LicenseLookupSecurityError(ValueError):
    """Raised when a package name, version, or URL violates SSRF guardrails."""


@dataclass(frozen=True)
class ResolvedPackageLicense:
    spdx_id: str
    license_class: str
    confidence: str
    source: str  # "lockfile" | "cache" | "depsdev" | "npm" | "pypi" | "unresolved"
    note: Optional[str] = None


def validate_package_coordinates(ecosystem: str, name: str, version: str) -> Tuple[str, str]:
    """Validate ecosystem & package name/version strictly before URL construction (SSRF control)."""
    eco = ecosystem.lower()
    if eco not in ("npm", "pypi"):
        raise LicenseLookupSecurityError(f"Unsupported ecosystem: {ecosystem!r}")
    if ".." in name or "//" in name or "\\" in name or any(ch.isspace() for ch in name):
        raise LicenseLookupSecurityError(f"Unsafe package name: {name!r}")
    if eco == "npm":
        if not NPM_NAME_RE.match(name):
            raise LicenseLookupSecurityError(f"Invalid npm package name: {name!r}")
    else:
        if not PYPI_NAME_RE.match(name):
            raise LicenseLookupSecurityError(f"Invalid PyPI package name: {name!r}")
    if not VERSION_RE.match(version) or ".." in version or "/" in version:
        raise LicenseLookupSecurityError(f"Invalid package version: {version!r}")
    return eco, name


def validate_outbound_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_LICENSE_HOSTS:
        raise LicenseLookupSecurityError(f"Disallowed license lookup host or scheme: {parsed.hostname!r}")
    return url


def _safe_get_json(client: httpx.Client, url: str) -> Optional[dict]:
    validate_outbound_url(url)
    resp = client.get(url, timeout=5.0, follow_redirects=False)
    if resp.status_code in (301, 302, 303, 307, 308):
        # Never follow redirects to external hosts
        return None
    if resp.status_code != 200:
        return None
    if len(resp.content) > MAX_RESPONSE_BYTES:
        return None
    return resp.json()


def _cache_get(system: str, name: str, version: str) -> Optional[NormalizedLicense]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=CACHE_TTL_DAYS)
    try:
        with session_scope() as session:
            row = session.get(LicenseCacheRow, {"system": system, "name": name, "version": version})
            if row is None:
                return None
            ts = row.fetched_at
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts < cutoff:
                return None
            data = row.licenses_json or {}
            return NormalizedLicense(
                spdx_id=data.get("spdx_id", "LicenseRef-unknown"),
                license_class=data.get("license_class", "unknown"),
                confidence=data.get("confidence", "high"),
                note=data.get("note"),
            )
    except Exception:
        return None


def _cache_put(system: str, name: str, version: str, norm: NormalizedLicense) -> None:
    try:
        with session_scope() as session:
            row = session.get(LicenseCacheRow, {"system": system, "name": name, "version": version})
            payload = {
                "spdx_id": norm.spdx_id,
                "license_class": norm.license_class,
                "confidence": norm.confidence,
                "note": norm.note,
            }
            now = datetime.now(timezone.utc)
            if row is None:
                session.add(
                    LicenseCacheRow(
                        system=system,
                        name=name,
                        version=version,
                        licenses_json=payload,
                        fetched_at=now,
                    )
                )
            else:
                row.licenses_json = payload
                row.fetched_at = now
    except Exception:
        pass


def _resolve_single_remote(
    dep: LockDependency,
    client: httpx.Client,
    depsdev_base: str,
) -> ResolvedPackageLicense:
    try:
        eco, safe_name = validate_package_coordinates(dep.ecosystem, dep.name, dep.version)
    except LicenseLookupSecurityError:
        return ResolvedPackageLicense("LicenseRef-unknown", "unknown", "high", "unresolved", note="invalid_coordinate")

    enc_name = quote(safe_name, safe="")
    enc_ver = quote(dep.version, safe="")

    # (c) api.deps.dev
    try:
        depsdev_url = f"{depsdev_base}/v3/systems/{eco}/packages/{enc_name}/versions/{enc_ver}"
        data = _safe_get_json(client, depsdev_url)
        if data and isinstance(data.get("licenses"), list) and data["licenses"]:
            expr = " AND ".join(str(x) for x in data["licenses"] if x)
            nl = normalize_license_string(expr)
            if nl.spdx_id != "LicenseRef-unknown":
                _cache_put(eco, safe_name, dep.version, nl)
                return ResolvedPackageLicense(nl.spdx_id, nl.license_class, nl.confidence, "depsdev", nl.note)
    except LicenseLookupSecurityError:
        raise
    except Exception:
        pass

    # (d) Registry fallback
    try:
        if eco == "npm":
            npm_name = f"@{quote(safe_name[1:].split('/')[0], safe='')}/{quote(safe_name.split('/')[1], safe='')}" if safe_name.startswith("@") else enc_name
            npm_url = f"https://registry.npmjs.org/{npm_name}/{enc_ver}"
            data = _safe_get_json(client, npm_url)
            if data:
                raw_lic = data.get("license")
                if isinstance(raw_lic, dict):
                    raw_lic = raw_lic.get("type")
                if isinstance(raw_lic, str) and raw_lic.strip():
                    nl = normalize_license_string(raw_lic)
                    if nl.spdx_id != "LicenseRef-unknown":
                        _cache_put(eco, safe_name, dep.version, nl)
                        return ResolvedPackageLicense(nl.spdx_id, nl.license_class, nl.confidence, "npm", nl.note)
        else:
            pypi_url = f"https://pypi.org/pypi/{enc_name}/{enc_ver}/json"
            data = _safe_get_json(client, pypi_url)
            if data and isinstance(data.get("info"), dict):
                info = data["info"]
                cand = info.get("license_expression") or info.get("license")
                if isinstance(cand, str) and cand.strip():
                    nl = normalize_license_string(cand)
                    if nl.spdx_id != "LicenseRef-unknown":
                        _cache_put(eco, safe_name, dep.version, nl)
                        return ResolvedPackageLicense(nl.spdx_id, nl.license_class, nl.confidence, "pypi", nl.note)
                for clf in info.get("classifiers") or []:
                    if "License :: OSI Approved ::" in str(clf):
                        nl = normalize_license_string(str(clf))
                        if nl.spdx_id != "LicenseRef-unknown":
                            _cache_put(eco, safe_name, dep.version, nl)
                            return ResolvedPackageLicense(nl.spdx_id, nl.license_class, nl.confidence, "pypi", nl.note)
    except LicenseLookupSecurityError:
        raise
    except Exception:
        pass

    return ResolvedPackageLicense("LicenseRef-unknown", "unknown", "high", "unresolved")


def resolve_dependency_licenses(
    deps: List[LockDependency],
    *,
    client: Optional[httpx.Client] = None,
    budget_seconds: Optional[float] = None,
    concurrency: Optional[int] = None,
    offline: bool = False,
) -> Dict[Tuple[str, str, str], ResolvedPackageLicense]:
    """Resolve licenses for locked dependencies cleanly respecting concurrency & wall budget."""
    results: Dict[Tuple[str, str, str], ResolvedPackageLicense] = {}
    to_fetch: List[LockDependency] = []

    for d in deps:
        key = (d.ecosystem, d.name, d.version)
        if d.lockfile_license:
            nl = normalize_license_string(d.lockfile_license)
            if nl.spdx_id != "LicenseRef-unknown":
                results[key] = ResolvedPackageLicense(nl.spdx_id, nl.license_class, nl.confidence, "lockfile", nl.note)
                continue
        cached = _cache_get(d.ecosystem.lower(), d.name, d.version)
        if cached is not None:
            results[key] = ResolvedPackageLicense(cached.spdx_id, cached.license_class, cached.confidence, "cache", cached.note)
            continue
        if offline:
            results[key] = ResolvedPackageLicense("LicenseRef-unknown", "unknown", "high", "unresolved")
        else:
            to_fetch.append(d)

    if not to_fetch:
        return results

    total_budget = float(budget_seconds if budget_seconds is not None else Config.LICENSE_LOOKUP_BUDGET_SECONDS)
    max_workers = max(1, int(concurrency if concurrency is not None else Config.LICENSE_LOOKUP_CONCURRENCY))
    deadline = time.monotonic() + total_budget
    depsdev_base = Config.DEPSDEV_BASE_URL

    own_client = client is None
    http_client = client or httpx.Client(timeout=5.0, headers={"User-Agent": "CODIT-License-Resolver/3.0"})
    try:
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futs = {}
            for d in to_fetch:
                if time.monotonic() >= deadline:
                    results[(d.ecosystem, d.name, d.version)] = ResolvedPackageLicense(
                        "LicenseRef-unknown", "unknown", "high", "unresolved", note="budget_exhausted"
                    )
                    continue
                futs[pool.submit(_resolve_single_remote, d, http_client, depsdev_base)] = d

            for fut in as_completed(futs):
                d = futs[fut]
                key = (d.ecosystem, d.name, d.version)
                if time.monotonic() > deadline:
                    results.setdefault(
                        key,
                        ResolvedPackageLicense("LicenseRef-unknown", "unknown", "high", "unresolved", note="budget_exhausted"),
                    )
                    continue
                try:
                    results[key] = fut.result(timeout=max(0.1, deadline - time.monotonic()))
                except Exception:
                    results[key] = ResolvedPackageLicense("LicenseRef-unknown", "unknown", "high", "unresolved")
    finally:
        if own_client:
            http_client.close()

    # Ensure every dependency has an entry
    for d in deps:
        key = (d.ecosystem, d.name, d.version)
        results.setdefault(key, ResolvedPackageLicense("LicenseRef-unknown", "unknown", "high", "unresolved"))

    return results
