"""
Analysis execution route: orchestrates the audit pipeline against an isolated
per-audit record and GraphHandle via `audit_service`.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from backend.app.services import audit_service

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analyze", tags=["analyze"])


class AnalyzeRequest(BaseModel):
    goal: Optional[str] = "production"  # "mvp" or "production"


@router.post("/run")
def run_full_analysis(
    request: Request,
    response: Response,
    payload: AnalyzeRequest = AnalyzeRequest(),
):
    audit_id = audit_service.get_audit_id_from_request(request)
    staged = audit_service.get_staged_codebase(audit_id) if audit_id else None

    if audit_id and staged is None:
        # Check if this audit already ran (re-run or demo)
        existing_row = audit_service.get_audit_row(audit_id)
        if existing_row is not None and existing_row.source_kind != "demo" and existing_row.status != "completed":
            raise HTTPException(
                status_code=400,
                detail={"code": "no_codebase", "message": "No active codebase found. Ingest via /api/ingest first."},
            )
        if existing_row is not None and existing_row.status == "completed":
            existing_report = audit_service.get_report_for_audit(audit_id)
            if existing_report is not None:
                return {
                    "status": "ok",
                    "audit_id": audit_id,
                    "report_id": existing_report.report_id,
                    "score": existing_report.scorecard.overall_score,
                    "phase": existing_report.scorecard.phase,
                    "findings_count": len(existing_report.findings),
                    "source_deleted": existing_report.source_deleted,
                    "onnx_fragility": existing_report.ml_insights.get("onnx_metrics", {}).get("fragility_score"),
                    "shap_baseline": existing_report.ml_insights.get("shap_explainability", {}).get("baseline_score"),
                }

    if staged is not None:
        entries = staged.get("entries", [])
        target_type = staged.get("type", "demo")
        target_name = staged.get("target", "Demo System")
        temp_dir = staged.get("temp_dir")
    else:
        audit_id = audit_service.create_audit(source_kind="demo", source_ref="Demo System", status="queued")
        entries = []
        target_type = "demo"
        target_name = "Demo System"
        temp_dir = None

    if not entries and target_type != "demo":
        raise HTTPException(
            status_code=400,
            detail={"code": "no_codebase", "message": "No active codebase found. Ingest via /api/ingest first."},
        )

    assert audit_id is not None
    report = audit_service.run_audit_pipeline(
        audit_id=audit_id,
        entries=entries,
        target_name=target_name,
        target_type=target_type,
        goal=payload.goal or "production",
        temp_dir=temp_dir,
    )

    if response is not None:
        audit_service.set_audit_cookie(response, audit_id)

    onnx_metrics = report.ml_insights.get("onnx_metrics", {})
    shap_explainability = report.ml_insights.get("shap_explainability", {})
    return {
        "status": "ok",
        "audit_id": audit_id,
        "report_id": report.report_id,
        "score": report.scorecard.overall_score,
        "phase": report.scorecard.phase,
        "findings_count": len(report.findings),
        "source_deleted": report.source_deleted,
        "onnx_fragility": onnx_metrics.get("fragility_score"),
        "shap_baseline": shap_explainability.get("baseline_score"),
    }
