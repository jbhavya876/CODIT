"""
Report delivery and export routes for Dashboard, Markdown, and PDF/HTML.
Backed by per-audit persisted state via signed `codit_audit` cookies.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, PlainTextResponse

from backend.app.delivery.pdf_export import generate_html_report, generate_markdown_report
from backend.app.diagrams.mermaid_generator import generate_blast_radius_diagram
from backend.app.services import audit_service, graph_service

router = APIRouter(prefix="/api/report", tags=["report"])


def _ensure_report(request: Request, response: Response):
    audit_id = audit_service.get_audit_id_from_request(request)
    if audit_id:
        report = audit_service.get_report_for_audit(audit_id)
        if report is not None:
            return report
        staged = audit_service.get_staged_codebase(audit_id)
        if staged is not None:
            return audit_service.run_audit_pipeline(
                audit_id=audit_id,
                entries=staged.get("entries", []),
                target_name=staged.get("target", "Demo System"),
                target_type=staged.get("type", "demo"),
                temp_dir=staged.get("temp_dir"),
            )

    # Fresh demo audit if client has no cookie yet
    demo_audit_id = audit_service.create_audit(source_kind="demo", source_ref="Demo System", status="queued")
    report = audit_service.run_audit_pipeline(
        audit_id=demo_audit_id,
        entries=[],
        target_name="Demo System",
        target_type="demo",
    )
    audit_service.set_audit_cookie(response, demo_audit_id)
    return report


@router.get("")
def get_report_json(request: Request, response: Response):
    report = _ensure_report(request, response)
    if not report:
        raise HTTPException(status_code=404, detail={"code": "no_report", "message": "No report available."})
    return report.to_dict()


@router.get("/markdown")
def export_markdown_report(request: Request, response: Response):
    report = _ensure_report(request, response)
    if not report:
        raise HTTPException(status_code=404, detail={"code": "no_report", "message": "No report available."})
    content = generate_markdown_report(report)
    return PlainTextResponse(
        content=content,
        headers={"Content-Disposition": f"attachment; filename=audit-report-{report.report_id}.md"},
    )


@router.get("/html")
def export_html_report(request: Request, response: Response):
    report = _ensure_report(request, response)
    if not report:
        raise HTTPException(status_code=404, detail={"code": "no_report", "message": "No report available."})
    content = generate_html_report(report)
    return HTMLResponse(content=content)


@router.get("/diagram/impact/{component_id:path}")
def get_component_blast_radius_diagram(component_id: str, request: Request):
    audit_id = audit_service.get_audit_id_from_request(request)
    graph = audit_service.get_graph_for_audit(audit_id)
    impact_data = graph_service.impact(component_id, graph=graph)
    diagram = generate_blast_radius_diagram(component_id, impact_data)
    return {"component_id": component_id, "mermaid": diagram}
