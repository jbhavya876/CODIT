"""
Report delivery and export routes for Dashboard, Markdown, and PDF/HTML.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import HTMLResponse, PlainTextResponse

from backend.app.delivery.pdf_export import generate_html_report, generate_markdown_report
from backend.app.diagrams.mermaid_generator import generate_blast_radius_diagram
from backend.app.routes.analyze import get_active_report, run_full_analysis
from backend.app.services import graph_service

router = APIRouter(prefix="/api/report", tags=["report"])


def _ensure_report():
    report = get_active_report()
    if report is None:
        run_full_analysis()
        report = get_active_report()
    return report


@router.get("")
def get_report_json():
    report = _ensure_report()
    if not report:
        raise HTTPException(status_code=404, detail={"code": "no_report", "message": "No report available."})
    return report.to_dict()


@router.get("/markdown")
def export_markdown_report():
    report = _ensure_report()
    if not report:
        raise HTTPException(status_code=404, detail={"code": "no_report", "message": "No report available."})
    content = generate_markdown_report(report)
    return PlainTextResponse(
        content=content,
        headers={"Content-Disposition": f"attachment; filename=audit-report-{report.report_id}.md"},
    )


@router.get("/html")
def export_html_report():
    report = _ensure_report()
    if not report:
        raise HTTPException(status_code=404, detail={"code": "no_report", "message": "No report available."})
    content = generate_html_report(report)
    return HTMLResponse(content=content)


@router.get("/diagram/impact/{component_id}")
def get_component_blast_radius_diagram(component_id: str):
    impact_data = graph_service.impact(component_id)
    diagram = generate_blast_radius_diagram(component_id, impact_data)
    return {"component_id": component_id, "mermaid": diagram}
