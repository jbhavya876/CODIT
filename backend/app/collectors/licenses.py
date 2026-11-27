"""
License & IP Provenance Collector (P5): evaluates LIC-001 through LIC-008.

Produces deterministic AuditFindings, structured register entries, coverage
metrics (`resolved`, `total`, `unresolved`, `resolved_pct`), and always includes
the fixed non-legal-advice disclaimer.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import httpx

from codit_core.detectors.rules_catalog import render_finding_description
from codit_core.fingerprint import compute_fingerprint
from codit_core.licenses import LICENSE_DISCLAIMER
from codit_core.licenses.classify import resolve_project_license
from codit_core.licenses.headers import scan_source_header, scan_vendored_license_files
from codit_core.licenses.matrix import evaluate_dependency_license_rule

from backend.app.collectors.models import AuditFinding
from backend.app.ingestion.models import FileEntry
from backend.app.licenses.resolve import ResolvedPackageLicense, resolve_dependency_licenses
from backend.app.parsers.manifest.lockfiles import LockDependency, parse_all_lockfiles
from backend.app.parsers.models import DependencyEntry

log = logging.getLogger(__name__)


def run_licenses_collector(
    files: List[FileEntry],
    dependencies: List[DependencyEntry],
    *,
    source_kind: str = "zip",
    project_license_override: Optional[str] = None,
    http_client: Optional[httpx.Client] = None,
    offline: bool = False,
) -> Tuple[List[AuditFinding], Dict[str, Any], Dict[str, Any]]:
    """
    Evaluate lockfile/manifest licenses, project license, compatibility matrix,
    source SPDX headers, and vendored license files.

    Returns (findings, licenses_register_dict, licenses_coverage_dict).
    """
    findings: List[AuditFinding] = []
    file_pairs = [(f.path, f.content or "") for f in files]

    # 1. Resolve project license
    proj_lic = resolve_project_license(file_pairs, config_project_license=project_license_override)
    if proj_lic.license_class == "unknown" and files:
        sev = "medium" if source_kind == "public" else "info"
        fp = compute_fingerprint("LIC-006", proj_lic.evidence_file, "no_project_license")
        findings.append(
            AuditFinding(
                id=f"lic-006-{fp[:8]}",
                dimension="licenses",
                severity=sev,
                confidence="high",
                description=render_finding_description("LIC-006", {"path": proj_lic.evidence_file}),
                evidence_file=proj_lic.evidence_file,
                evidence_line=1,
                rule_id="LIC-006",
                remediation="Add a LICENSE file or declare `project_license` in `.codit.yml`.",
                component_id=proj_lic.evidence_file,
                fingerprint=fp,
                basis="PATTERN",
            )
        )

    # 2. Extract lockfile dependencies + fall back to manifest exact pins if no lockfile
    locked_deps, unpinned_deps = parse_all_lockfiles(files)
    if not locked_deps and dependencies:
        for dep in dependencies:
            if dep.normalized_version and not any(ch in dep.raw_version for ch in ("^", "~", ">", "<", "*")):
                scope = "dev" if "dev" in dep.dep_type.lower() else "prod"
                locked_deps.append(
                    LockDependency(
                        name=dep.name,
                        version=dep.normalized_version,
                        ecosystem=dep.ecosystem,
                        scope=scope,
                        direct=True,
                        source_file=dep.evidence_file,
                        line=dep.evidence_line or 1,
                    )
                )

    resolved_map = resolve_dependency_licenses(
        locked_deps,
        client=http_client,
        offline=offline,
    )

    register: List[Dict[str, Any]] = []
    resolved_count = 0
    unresolved_count = 0
    prod_total = 0
    prod_resolved = 0

    for d in locked_deps:
        res: ResolvedPackageLicense = resolved_map[(d.ecosystem, d.name, d.version)]
        is_resolved = res.license_class != "unknown"
        if is_resolved:
            resolved_count += 1
        else:
            unresolved_count += 1
        if d.scope == "prod":
            prod_total += 1
            if is_resolved:
                prod_resolved += 1

        rule_eval = evaluate_dependency_license_rule(
            spdx_id=res.spdx_id,
            license_class=res.license_class,
            scope=d.scope,
            project_spdx=proj_lic.spdx_id,
            project_class=proj_lic.license_class,
        )
        rule_id = rule_eval[0] if rule_eval else None
        if rule_eval:
            rid, sev = rule_eval
            fp = compute_fingerprint(rid, d.source_file, f"{d.ecosystem}:{d.name}@{d.version}")
            findings.append(
                AuditFinding(
                    id=f"{rid.lower()}-{fp[:8]}",
                    dimension="licenses",
                    severity=sev,
                    confidence=res.confidence,
                    description=render_finding_description(
                        rid,
                        {"name": d.name, "version": d.version, "spdx": res.spdx_id, "path": d.source_file},
                    ),
                    evidence_file=d.source_file,
                    evidence_line=d.line,
                    rule_id=rid,
                    remediation="Review license terms and compatibility with counsel.",
                    component_id=f"lib-{d.ecosystem.lower()}-{d.name.lower()}",
                    fingerprint=fp,
                    basis="PATTERN",
                    params={
                        "name": d.name,
                        "version": d.version,
                        "ecosystem": d.ecosystem,
                        "spdx": res.spdx_id,
                        "license_class": res.license_class,
                        "scope": d.scope,
                        "direct": d.direct,
                    },
                )
            )

        register.append({
            "package": d.name,
            "version": d.version,
            "ecosystem": d.ecosystem,
            "scope": d.scope,
            "direct": d.direct,
            "spdx_id": res.spdx_id,
            "license_class": res.license_class,
            "confidence": res.confidence,
            "source": res.source,
            "rule_id": rule_id,
            "evidence_file": d.source_file,
            "evidence_line": d.line,
            "note": res.note,
        })

    # 3. Source header checks (LIC-007) & vendored licenses (LIC-008)
    for f in files:
        hit = scan_source_header(f.path, f.content or "")
        if hit is not None:
            differs = (
                proj_lic.spdx_id == "LicenseRef-unknown"
                or hit.spdx_id.lower() != proj_lic.spdx_id.lower()
            )
            if differs:
                is_copyleft = hit.license_class in ("strong_copyleft", "network_copyleft", "weak_copyleft")
                proj_non_copyleft = proj_lic.license_class in ("permissive", "proprietary", "unknown")
                sev = "high" if (is_copyleft and proj_non_copyleft) else "medium"
                fp = compute_fingerprint("LIC-007", hit.path, hit.spdx_id)
                findings.append(
                    AuditFinding(
                        id=f"lic-007-{fp[:8]}",
                        dimension="licenses",
                        severity=sev,
                        confidence="high",
                        description=render_finding_description("LIC-007", {"path": hit.path, "spdx": hit.spdx_id}),
                        evidence_file=hit.path,
                        evidence_line=hit.line,
                        rule_id="LIC-007",
                        remediation="Verify origin and compatibility of source file license header.",
                        component_id=hit.path,
                        fingerprint=fp,
                        basis="PATTERN",
                        params={"spdx": hit.spdx_id, "license_class": hit.license_class},
                    )
                )

    declared_names = {d.name.lower() for d in locked_deps} | {d.name.lower() for d in dependencies}
    for v_hit in scan_vendored_license_files(
        file_pairs,
        project_spdx=proj_lic.spdx_id,
        declared_dep_names=declared_names,
    ):
        fp = compute_fingerprint("LIC-008", v_hit.path, v_hit.spdx_id)
        findings.append(
            AuditFinding(
                id=f"lic-008-{fp[:8]}",
                dimension="licenses",
                severity="medium",
                confidence="high",
                description=render_finding_description("LIC-008", {"path": v_hit.path, "spdx": v_hit.spdx_id}),
                evidence_file=v_hit.path,
                evidence_line=v_hit.line,
                rule_id="LIC-008",
                remediation="Document or remove conflicting vendored component license.",
                component_id=v_hit.path,
                fingerprint=fp,
                basis="PATTERN",
                params={"spdx": v_hit.spdx_id, "license_class": v_hit.license_class},
            )
        )

    total_deps = len(locked_deps)
    resolved_pct = int((resolved_count * 100) / total_deps) if total_deps else 100
    prod_resolved_pct = int((prod_resolved * 100) / prod_total) if prod_total else 100

    licenses_coverage = {
        "total": total_deps,
        "resolved": resolved_count,
        "unresolved": unresolved_count,
        "resolved_pct": resolved_pct,
        "prod_total": prod_total,
        "prod_resolved": prod_resolved,
        "prod_resolved_pct": prod_resolved_pct,
        "unpinned": [
            {"name": u.name, "ecosystem": u.ecosystem, "source_file": u.source_file, "line": u.line, "reason": u.reason}
            for u in unpinned_deps
        ],
        "not_applicable": total_deps == 0 and len(unpinned_deps) == 0,
    }
    licenses_report = {
        "disclaimer": LICENSE_DISCLAIMER,
        "project_license": {
            "spdx_id": proj_lic.spdx_id,
            "license_class": proj_lic.license_class,
            "source": proj_lic.source,
            "evidence_file": proj_lic.evidence_file,
        },
        "coverage": licenses_coverage,
        "register": register,
    }
    return findings, licenses_report, licenses_coverage
