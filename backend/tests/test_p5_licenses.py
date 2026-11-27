"""P5 License & IP Lens tests: lockfiles, SPDX, SSRF/recording egress, matrix, LIC-001..008, audit persistence."""

from __future__ import annotations

import json
from typing import List
from unittest.mock import patch

import httpx
import pytest

from codit_core.licenses import LICENSE_DISCLAIMER
from codit_core.licenses.spdx import normalize_license_string

from backend.app.collectors.licenses import run_licenses_collector
from backend.app.ingestion.models import FileEntry
from backend.app.licenses.resolve import (
    LicenseLookupSecurityError,
    resolve_dependency_licenses,
    validate_outbound_url,
    validate_package_coordinates,
)
from backend.app.parsers.manifest.lockfiles import LockDependency, parse_all_lockfiles
from backend.app.services.audit_service import create_audit, get_audit_row, run_audit_pipeline


def test_lockfile_parsers_all_six_formats_and_unpinned_and_malformed():
    files = [
        FileEntry(
            path="package.json",
            content=json.dumps({"dependencies": {"lodash": "^4.17.21"}, "devDependencies": {"vitest": "^1.0.0"}}),
            language="json",
            size=80,
        ),
        FileEntry(
            path="package-lock.json",
            content=json.dumps(
                {
                    "lockfileVersion": 3,
                    "packages": {
                        "": {"name": "demo"},
                        "node_modules/lodash": {"version": "4.17.21", "license": "MIT"},
                        "node_modules/vitest": {"version": "1.2.0", "dev": True, "license": "MIT"},
                    },
                }
            ),
            language="json",
            size=200,
        ),
        FileEntry(
            path="yarn.lock",
            content='left-pad@^1.3.0:\n  version "1.3.0"\n',
            language="text",
            size=40,
        ),
        FileEntry(
            path="pnpm-lock.yaml",
            content="lockfileVersion: '6.0'\npackages:\n  /ms/2.1.3:\n    resolution: {integrity: sha512-x}\n",
            language="yaml",
            size=80,
        ),
        FileEntry(
            path="poetry.lock",
            content='[[package]]\nname = "requests"\nversion = "2.31.0"\ncategory = "main"\n',
            language="toml",
            size=70,
        ),
        FileEntry(
            path="Pipfile.lock",
            content=json.dumps(
                {
                    "default": {"flask": {"version": "==3.0.2"}},
                    "develop": {"pytest": {"version": "==8.1.0"}},
                }
            ),
            language="json",
            size=120,
        ),
        FileEntry(
            path="requirements.txt",
            content="uvicorn==0.28.0\nfastapi>=0.110.0\nbad-spec\n",
            language="text",
            size=50,
        ),
        # Malformed lockfile should not crash parsing
        FileEntry(path="sub/package-lock.json", content="{not json", language="json", size=9),
    ]

    locked, unpinned = parse_all_lockfiles(files)
    by_name = {(d.ecosystem, d.name, d.version): d for d in locked}
    assert ("npm", "lodash", "4.17.21") in by_name
    assert by_name[("npm", "lodash", "4.17.21")].scope == "prod"
    assert by_name[("npm", "lodash", "4.17.21")].lockfile_license == "MIT"
    assert ("npm", "vitest", "1.2.0") in by_name
    assert by_name[("npm", "vitest", "1.2.0")].scope == "dev"
    assert ("npm", "left-pad", "1.3.0") in by_name
    assert ("npm", "ms", "2.1.3") in by_name
    assert ("PyPI", "requests", "2.31.0") in by_name
    assert ("PyPI", "flask", "3.0.2") in by_name
    assert by_name[("PyPI", "pytest", "8.1.0")].scope == "dev"
    assert ("PyPI", "uvicorn", "0.28.0") in by_name

    # Unpinned requirements.txt specs are never guessed
    unpinned_names = {(u.name, u.reason) for u in unpinned}
    assert ("fastapi", "unpinned") in unpinned_names
    assert ("bad-spec", "unpinned") in unpinned_names
    assert all(d.name != "fastapi" for d in locked)


def test_spdx_expressions_or_and_with_deprecated_and_see_license():
    # OR picks permissive option cleanly
    or_res = normalize_license_string("(GPL-3.0-only OR MIT)")
    assert or_res.license_class == "permissive"

    # AND picks most restrictive option conservatively
    and_res = normalize_license_string("(MIT AND GPL-3.0-only)")
    assert and_res.license_class == "strong_copyleft"

    # WITH classpath/exception reduces copyleft risk or normalizes cleanly
    with_res = normalize_license_string("GPL-2.0-only WITH Classpath-exception-2.0")
    assert with_res.spdx_id != "LicenseRef-unknown"
    assert with_res.license_class in ("weak_copyleft", "permissive")

    # Deprecated alias GPL-3.0+
    dep_res = normalize_license_string("GPL-3.0+")
    assert dep_res.license_class == "strong_copyleft"
    assert "GPL-3.0" in dep_res.spdx_id

    # SEE LICENSE IN ... -> never permissive, marked LicenseRef-custom/unknown
    see_res = normalize_license_string("SEE LICENSE IN NOTICE.txt")
    assert see_res.license_class == "unknown"
    assert see_res.spdx_id.startswith("LicenseRef-")


def test_ssrf_controls_and_recording_transport():
    for bad_eco, bad_name, bad_ver in [
        ("npm", "../etc/passwd", "1.0.0"),
        ("npm", "//evil.com/pkg", "1.0.0"),
        ("npm", "https://evil.com/foo", "1.0.0"),
        ("pypi", "pkg name space", "1.0.0"),
        ("npm", "lodash", "../../etc"),
        ("maven", "org.foo:bar", "1.0.0"),
    ]:
        with pytest.raises(LicenseLookupSecurityError):
            validate_package_coordinates(bad_eco, bad_name, bad_ver)

    for bad_url in [
        "http://api.deps.dev/v3/systems/npm/packages/lodash/versions/4.17.21",
        "https://evil.com/secret",
        "https://169.254.169.254/latest/meta-data",
        "file:///etc/passwd",
    ]:
        with pytest.raises(LicenseLookupSecurityError):
            validate_outbound_url(bad_url)

    from backend.app.db.engine import session_scope
    from backend.app.db.models import LicenseCacheRow

    with session_scope() as session:
        session.query(LicenseCacheRow).filter(LicenseCacheRow.name == "my-safe-pkg").delete()

    seen_urls: List[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_urls.append(str(request.url))
        assert request.url.host in ("api.deps.dev", "registry.npmjs.org", "pypi.org")
        assert "secret-repo-name" not in str(request.url)
        if request.url.host == "api.deps.dev" and "evil" not in str(request.url):
            return httpx.Response(200, json={"licenses": ["Apache-2.0"]})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    deps = [
        LockDependency("my-safe-pkg", "1.2.3", "npm", "prod", True, "package-lock.json", 5),
        # Invalid coordinate never touches HTTP transport
        LockDependency("https://evil.com/steal", "1.0.0", "npm", "prod", True, "package-lock.json", 9),
    ]
    with httpx.Client(transport=transport) as client:
        resolved = resolve_dependency_licenses(deps, client=client, budget_seconds=5.0, offline=False)

    assert len(seen_urls) == 1
    assert seen_urls[0].startswith("https://api.deps.dev/v3/systems/npm/packages/my-safe-pkg/versions/1.2.3")
    assert resolved[("npm", "my-safe-pkg", "1.2.3")].spdx_id == "Apache-2.0"
    assert resolved[("npm", "https://evil.com/steal", "1.0.0")].license_class == "unknown"

    # Second call uses SQLAlchemy license_cache without making any HTTP requests
    with httpx.Client(transport=transport) as client:
        cached_resolved = resolve_dependency_licenses(deps[:1], client=client, budget_seconds=5.0, offline=False)
    assert len(seen_urls) == 1
    assert cached_resolved[("npm", "my-safe-pkg", "1.2.3")].source == "cache"
    assert cached_resolved[("npm", "my-safe-pkg", "1.2.3")].spdx_id == "Apache-2.0"


def test_budget_exhaustion_graceful_unresolved():
    deps = [
        LockDependency("budget-pkg", "1.0.0", "npm", "prod", True, "package-lock.json", 3),
    ]

    def slow_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"licenses": ["MIT"]})

    with httpx.Client(transport=httpx.MockTransport(slow_handler)) as client:
        # 0s budget expires immediately before remote requests run
        resolved = resolve_dependency_licenses(deps, client=client, budget_seconds=0.0, offline=False)
    assert resolved[("npm", "budget-pkg", "1.0.0")].source == "unresolved"
    assert resolved[("npm", "budget-pkg", "1.0.0")].license_class == "unknown"


def test_lic_001_to_008_and_disclaimer_and_dev_downgrade():
    files = [
        FileEntry(path="LICENSE", content="MIT License\nPermission is hereby granted, free of charge...", language="text", size=60),
        FileEntry(
            path="package.json",
            content=json.dumps({
                "license": "MIT",
                "dependencies": {
                    "gpl-prod": "1.0.0",
                    "agpl-prod": "1.0.0",
                    "lgpl-prod": "1.0.0",
                    "bsl-prod": "1.0.0",
                    "unknown-prod": "1.0.0",
                },
                "devDependencies": {
                    "gpl-dev": "1.0.0",
                    "unknown-dev": "1.0.0",
                },
            }),
            language="json",
            size=250,
        ),
        FileEntry(
            path="package-lock.json",
            content=json.dumps({
                "lockfileVersion": 3,
                "packages": {
                    "": {"name": "app"},
                    "node_modules/gpl-prod": {"version": "1.0.0", "license": "GPL-3.0-only"},
                    "node_modules/agpl-prod": {"version": "1.0.0", "license": "AGPL-3.0-only"},
                    "node_modules/lgpl-prod": {"version": "1.0.0", "license": "LGPL-2.1-only"},
                    "node_modules/bsl-prod": {"version": "1.0.0", "license": "BUSL-1.1"},
                    "node_modules/unknown-prod": {"version": "1.0.0"},
                    "node_modules/gpl-dev": {"version": "1.0.0", "dev": True, "license": "GPL-3.0-only"},
                    "node_modules/unknown-dev": {"version": "1.0.0", "dev": True},
                },
            }),
            language="json",
            size=400,
        ),
        FileEntry(
            path="src/copied.py",
            content="# SPDX-License-Identifier: GPL-3.0-only\ndef f():\n    return 1\n",
            language="python",
            size=70,
        ),
        FileEntry(
            path="vendor/thirdparty/LICENSE",
            content="GNU GENERAL PUBLIC LICENSE\nVersion 3, 29 June 2007\nEveryone is permitted to copy...",
            language="text",
            size=90,
        ),
    ]

    findings, report, coverage = run_licenses_collector(files, [], source_kind="public", offline=True)
    assert report["disclaimer"] == LICENSE_DISCLAIMER
    assert coverage["total"] == 7
    assert coverage["resolved"] == 5
    assert coverage["unresolved"] == 2
    assert coverage["resolved_pct"] == 71

    by_rule_pkg = {(f.rule_id, f.params.get("name")): f for f in findings}
    assert by_rule_pkg[("LIC-001", "gpl-prod")].severity == "high"
    assert by_rule_pkg[("LIC-001", "gpl-dev")].severity == "medium"  # downgraded
    assert by_rule_pkg[("LIC-002", "agpl-prod")].severity == "high"
    assert by_rule_pkg[("LIC-003", "lgpl-prod")].severity == "low"
    assert by_rule_pkg[("LIC-004", "unknown-prod")].severity == "medium"
    assert ("LIC-004", "unknown-dev") not in by_rule_pkg
    assert by_rule_pkg[("LIC-005", "bsl-prod")].severity == "high"

    rules = {f.rule_id for f in findings}
    assert "LIC-007" in rules
    assert "LIC-008" in rules

    # Proprietary override escalates GPL & AGPL to critical, and missing LICENSE triggers LIC-006
    no_lic_files = [f for f in files if f.path != "LICENSE" and f.path != "package.json"] + [
        FileEntry(
            path="package.json",
            content=json.dumps({"dependencies": {"gpl-prod": "1.0.0", "agpl-prod": "1.0.0"}}),
            language="json",
            size=80,
        )
    ]
    prop_findings, _, _ = run_licenses_collector(
        no_lic_files, [], source_kind="public", project_license_override="PROPRIETARY", offline=True
    )
    prop_by_rule = {(f.rule_id, f.params.get("name")): f for f in prop_findings}
    assert prop_by_rule[("LIC-001", "gpl-prod")].severity == "critical"
    assert prop_by_rule[("LIC-002", "agpl-prod")].severity == "critical"

    missing_lic_files = [f for f in no_lic_files if f.path == "src/copied.py"]
    missing_findings, _, _ = run_licenses_collector(missing_lic_files, [], source_kind="public", offline=True)
    lic006 = [f for f in missing_findings if f.rule_id == "LIC-006"]
    assert len(lic006) == 1 and lic006[0].severity == "medium"


def test_audit_service_persists_licenses_json_and_coverage():
    files = [
        FileEntry(path="LICENSE", content="MIT License\nPermission is hereby granted, free of charge...", language="text", size=60),
        FileEntry(
            path="package-lock.json",
            content=json.dumps({
                "lockfileVersion": 3,
                "packages": {
                    "": {"name": "demo"},
                    "node_modules/gpl-pkg": {"version": "1.0.0", "license": "GPL-3.0-only"},
                },
            }),
            language="json",
            size=120,
        ),
        FileEntry(path="index.js", content="export const x = 1;\n", language="javascript", size=20),
    ]
    audit_id = create_audit(source_kind="zip", source_ref="lic-demo")
    run_audit_pipeline(audit_id, files, "lic-demo", "zip")

    row = get_audit_row(audit_id)
    assert row is not None
    assert row.licenses_json is not None
    assert row.licenses_json["disclaimer"] == LICENSE_DISCLAIMER
    assert row.licenses_json["project_license"]["spdx_id"] == "MIT"
    assert row.coverage_json["licenses"]["total"] == 1
    assert row.coverage_json["licenses"]["resolved"] == 1
