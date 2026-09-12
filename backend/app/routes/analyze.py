"""
Analysis execution route: orchestrates the full pipeline from ingestion manifest
to graph assembly, collectors, scoring, diagrams, and roadmap synthesis.
"""

from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.app.collectors import run_all_collectors
from backend.app.delivery.models import AuditReport
from backend.app.diagrams.mermaid_generator import (
    generate_architecture_diagram,
    generate_blast_radius_diagram,
)
from backend.app.graph.assembler import assemble_graph, load_and_activate_graph
from backend.app.ingestion.zip_extract import purge_extracted_files
from backend.app.parsers.ast.treesitter_walker import parse_codebase_ast
from backend.app.parsers.manifest import extract_manifests_and_signals
from backend.app.routes.ingest import get_active_codebase
from backend.app.scoring.roadmap_synthesis import generate_audit_roadmap
from backend.app.scoring.rules_engine import score_audit
from backend.app.services import graph_service

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analyze", tags=["analyze"])

_ACTIVE_REPORT: Optional[AuditReport] = None


def get_active_report() -> Optional[AuditReport]:
    return _ACTIVE_REPORT


class AnalyzeRequest(BaseModel):
    goal: Optional[str] = "production"  # "mvp" or "production"


@router.post("/run")
def run_full_analysis(payload: AnalyzeRequest = AnalyzeRequest()):
    global _ACTIVE_REPORT

    codebase = get_active_codebase()
    entries = codebase.get("entries", [])
    target_type = codebase.get("type", "demo")
    target_name = codebase.get("target", "Demo System")

    # If no files ingested yet, assemble from demo or return error
    if not entries and target_type != "demo":
        raise HTTPException(
            status_code=400,
            detail={"code": "no_codebase", "message": "No active codebase found. Ingest via /api/ingest first."},
        )

    # 1. Parse manifests & config signals (Module 2)
    deps, signals = extract_manifests_and_signals(entries)

    # 2. Parse source ASTs & internal imports (Module 3)
    ast_map = parse_codebase_ast(entries)

    # 3. Run audit collectors (Module 5)
    findings = run_all_collectors(entries, deps, ast_map)

    # 4. Deterministic scoring (Module 6a)
    scorecard = score_audit(findings)

    # 5. Graph Assembly & activation (Module 4)
    nodes, edges = load_and_activate_graph(entries, deps, signals, ast_map, findings)

    # 6. Generate Mermaid architecture diagram (Module 7)
    arch_diagram = generate_architecture_diagram(nodes, edges)

    # 7. Query criticality leaderboard from active graph (Module 4)
    leaderboard = graph_service.leaderboard(limit=8)

    # 8. Synthesize prioritized roadmap (Module 6b)
    roadmap = generate_audit_roadmap(
        scorecard=scorecard,
        findings=findings,
        critical_components=leaderboard,
        goal=payload.goal or "production",
    )

    # 9. Access tier resolution
    tier_map = {
        "public": "free_public",
        "private": "paid_private",
        "zip": "premium_zip",
        "demo": "free_public",
    }
    access_tier = tier_map.get(target_type, "free_public")

    # 10. Check Constraint 7: Immediate deletion of ZIP-uploaded source code
    source_deleted = False
    temp_dir = codebase.get("temp_dir")
    if target_type == "zip" and temp_dir and Path(temp_dir).exists():
        purge_extracted_files(Path(temp_dir))
        source_deleted = True
        log.info("Constraint 7 enforced: Purged ZIP source files from %s post-analysis", temp_dir)

    # 11. Compile canonical AuditReport
    report = AuditReport(
        report_id=f"audit-{uuid.uuid4().hex[:8]}",
        target_name=target_name,
        target_type=target_type,
        access_tier=access_tier,
        created_at=time.time(),
        scorecard=scorecard,
        findings=findings,
        roadmap=roadmap,
        architecture_diagram_mermaid=arch_diagram,
        criticality_leaderboard=leaderboard,
        stats=graph_service.stats(),
        source_deleted=source_deleted,
    )

    _ACTIVE_REPORT = report
    return {
        "status": "ok",
        "report_id": report.report_id,
        "score": scorecard.overall_score,
        "phase": scorecard.phase,
        "findings_count": len(findings),
        "source_deleted": source_deleted,
    }
