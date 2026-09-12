"""
Graph Assembler: Transforms parsed manifests, AST import graphs, and tech signals
into the unified property graph schema.

Preserves all labels and relationship conventions from Dependency-Detective.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.app.ingestion.models import FileEntry
from backend.app.parsers.ast.treesitter_walker import FileAstSummary
from backend.app.parsers.models import DependencyEntry, TechStackSignal
from backend.app.services import graph_service

log = logging.getLogger(__name__)


def assemble_graph(
    files: List[FileEntry],
    dependencies: List[DependencyEntry],
    tech_signals: List[TechStackSignal],
    ast_summaries: Dict[str, FileAstSummary],
    findings: Optional[List[Any]] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Assembles a complete, unified graph dataset from parsed codebase components.
    Returns:
      (nodes_list, edges_list)
    """
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    node_ids: Set[str] = set()

    def add_node(node_id: str, label: str, name: str, props: Dict[str, Any]):
        if node_id not in node_ids:
            node_ids.add(node_id)
            nodes.append({
                "id": node_id,
                "type": label,
                "labels": label,
                "name": name,
                **props,
            })

    # 1. Add internal Module nodes
    # Check test files to identify which implementation modules have tests
    test_file_stems = set()
    for f in files:
        stem = Path(f.path).stem
        if "test" in stem.lower():
            clean_stem = stem.lower().replace("test_", "").replace("_test", "").replace(".test", "").replace(".spec", "")
            test_file_stems.add(clean_stem)

    for f in files:
        loc = len(f.content.splitlines())
        stem = Path(f.path).stem.lower()
        has_tests = stem in test_file_stems or any(stem in t for t in test_file_stems)

        add_node(
            node_id=f.path,
            label="Module",
            name=Path(f.path).name,
            props={
                "path": f.path,
                "language": f.language,
                "loc": loc,
                "has_tests": has_tests,
            },
        )

    # 2. Add external Library nodes
    for dep in dependencies:
        lib_id = f"lib-{dep.ecosystem.lower()}-{dep.name.lower()}"
        add_node(
            node_id=lib_id,
            label="Library",
            name=dep.name,
            props={
                "version": dep.normalized_version,
                "raw_version": dep.raw_version,
                "ecosystem": dep.ecosystem,
                "dep_type": dep.dep_type,
            },
        )
        # Link manifest file -> Library
        if dep.evidence_file in node_ids:
            edges.append({
                "source_id": dep.evidence_file,
                "rel_type": "USES",
                "target_id": lib_id,
            })

    # 3. Add TechStack Database & Infrastructure nodes
    db_node_ids = []
    for sig in tech_signals:
        sig_id = f"{sig.category[:3]}-{sig.name.lower().replace(' ', '-')}"
        lbl = "Database" if sig.category in ("database", "cache") else "Infrastructure"
        add_node(
            node_id=sig_id,
            label=lbl,
            name=sig.name,
            props={
                "category": sig.category,
                "confidence": sig.confidence,
                "detail": sig.detail,
            },
        )
        if sig.category in ("database", "cache"):
            db_node_ids.append(sig_id)

        # Link evidencing file -> Tech node
        if sig.evidence_file in node_ids:
            edges.append({
                "source_id": sig.evidence_file,
                "rel_type": "USES" if lbl == "Database" else "DEPLOYED_ON",
                "target_id": sig_id,
            })

    # 4. Add Internal IMPORTS relationships between Modules
    for src_path, summary in ast_summaries.items():
        if src_path not in node_ids:
            continue

        for imp in summary.imports:
            if imp.resolved_path and imp.resolved_path in node_ids and imp.resolved_path != src_path:
                edges.append({
                    "source_id": src_path,
                    "rel_type": "IMPORTS",
                    "target_id": imp.resolved_path,
                })
            elif not imp.is_relative and imp.source:
                # Check if matches a known Library node
                lib_id_npm = f"lib-npm-{imp.source.lower()}"
                lib_id_pypi = f"lib-pypi-{imp.source.lower()}"
                target_lib = lib_id_npm if lib_id_npm in node_ids else (lib_id_pypi if lib_id_pypi in node_ids else None)
                if target_lib:
                    edges.append({
                        "source_id": src_path,
                        "rel_type": "USES",
                        "target_id": target_lib,
                    })

    # 5. Add Finding nodes and FLAGGED_BY relationships if findings are provided
    if findings:
        for f in findings:
            f_id = getattr(f, "id", str(f.get("id", "")))
            add_node(
                node_id=f_id,
                label="Finding",
                name=f_id,
                props={
                    "dimension": getattr(f, "dimension", f.get("dimension", "")),
                    "severity": getattr(f, "severity", f.get("severity", "")),
                    "confidence": getattr(f, "confidence", f.get("confidence", "")),
                    "description": getattr(f, "description", f.get("description", "")),
                    "evidence_file": getattr(f, "evidence_file", f.get("evidence_file", "")),
                    "evidence_line": getattr(f, "evidence_line", f.get("evidence_line", None)),
                },
            )
            ev_file = getattr(f, "evidence_file", f.get("evidence_file", ""))
            if ev_file in node_ids:
                edges.append({
                    "source_id": ev_file,
                    "rel_type": "FLAGGED_BY",
                    "target_id": f_id,
                })

    return nodes, edges


def load_and_activate_graph(
    files: List[FileEntry],
    dependencies: List[DependencyEntry],
    tech_signals: List[TechStackSignal],
    ast_summaries: Dict[str, FileAstSummary],
    findings: Optional[List[Any]] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Assembles and activates the codebase graph in the active graph engine.
    """
    nodes, edges = assemble_graph(
        files=files,
        dependencies=dependencies,
        tech_signals=tech_signals,
        ast_summaries=ast_summaries,
        findings=findings,
    )
    graph_service.load_assembled_graph(nodes, edges)
    log.info("Activated assembled graph: %d nodes, %d edges", len(nodes), len(edges))
    return nodes, edges
