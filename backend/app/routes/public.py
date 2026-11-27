"""Public unauthenticated verification surfaces (`/v/{id}`, `/badge/{id}.svg`, `/.well-known/*`)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape

from backend.app.attest.badge import render_badge_svg
from backend.app.attest.service import get_attestation_record, get_staleness_ahead_by, list_revocations
from backend.app.attest.signing import get_public_keys_document
from backend.app.delivery.profiles.shared import METHODOLOGY_PARAGRAPH

router = APIRouter(tags=["public-verify"])

_TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
_STATIC_DIR = Path(__file__).resolve().parents[1] / "static"

_JINJA_ENV = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(enabled_extensions=("html", "xml"), default=True),
)

_VERIFY_CSP = (
    "default-src 'none'; style-src 'self'; img-src 'self' data:; "
    "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
)


@router.get("/static/verify.css", include_in_schema=False)
def serve_verify_css():
    css_path = _STATIC_DIR / "verify.css"
    css_text = css_path.read_text(encoding="utf-8") if css_path.is_file() else ""
    return Response(
        content=css_text,
        media_type="text/css; charset=utf-8",
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "public, max-age=300"},
    )


@router.get("/.well-known/codit-keys.json")
def well_known_keys():
    return get_public_keys_document()


@router.get("/.well-known/codit-revocations.json")
def well_known_revocations():
    return {"revoked": list_revocations()}


@router.get("/badge/{attestation_id}.svg")
def get_attestation_badge(attestation_id: str):
    rec = get_attestation_record(attestation_id)
    if rec is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Attestation not found."})
    svg = render_badge_svg(
        state=rec["badge_state"],
        score=rec["score"],
        phase=rec["phase"],
        partial=rec["partial"],
    )
    return Response(
        content=svg,
        media_type="image/svg+xml; charset=utf-8",
        headers={
            "Cache-Control": "max-age=300",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/v/{attestation_id}", response_class=HTMLResponse)
def verify_attestation_page(attestation_id: str):
    rec = get_attestation_record(attestation_id)
    if rec is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Attestation not found."})

    payload: Dict[str, Any] = rec["payload"]
    subj = dict(payload.get("subject") or {})
    cov = dict(payload.get("coverage") or {})
    hist = dict(cov.get("history") or {})
    res = dict(payload.get("result") or {})
    sig = dict(payload.get("signature") or {})

    if subj.get("kind") == "git":
        subject_label = f"{subj.get('repo', '')} @ {str(subj.get('commit', ''))[:12]}"
        control_note = (
            "Repository control check passed: someone with write access placed the single-use .codit/verify token in this commit."
            if subj.get("control_verified")
            else "Repository control not verified."
        )
    else:
        sha = str(subj.get("sha256") or "")
        subject_label = f"Archive sha256:{sha[:16]}..."
        control_note = "Archive upload audit — source repository identity is not verified."

    history_stmt = (
        f"Process integrity: assessed ({hist.get('commits_analyzed', 0)} commits analyzed"
        + (", partial window" if hist.get("partial") else "")
        + ")"
        if hist.get("assessed")
        else "Process integrity: not assessed"
    )
    lic_pct = cov.get("licenses_resolved_pct")
    licenses_stmt = (
        "Dependency licenses: not applicable (no dependencies declared)"
        if lic_pct is None
        else f"Dependency licenses: {lic_pct}% resolved"
    )
    coverage_statements: List[str] = [
        f"Files scanned: {cov.get('files_scanned', 0)} / {cov.get('files_total', 0)}",
        history_stmt,
        licenses_stmt,
    ]
    ahead_by = get_staleness_ahead_by(subj) if (not rec["is_revoked"] and not rec["is_expired"]) else None

    template = _JINJA_ENV.get_template("verify.html")
    rendered = template.render(
        attestation_id=rec["attestation_id"],
        badge_state=rec["badge_state"],
        is_revoked=rec["is_revoked"],
        revoked_at=rec["revoked_at"],
        revoked_reason_code=rec["revoked_reason_code"],
        is_expired=rec["is_expired"],
        signature_valid=rec["signature_valid"],
        kid=sig.get("kid", ""),
        issued_at=payload.get("issued_at", ""),
        expires_at=payload.get("expires_at", ""),
        score=res.get("overall", 0),
        phase=res.get("phase", "Prototype"),
        qualifiers=res.get("phase_qualifiers") or [],
        blockers=res.get("blockers") or [],
        dimensions=res.get("dimensions") or {},
        rubric_version=(payload.get("rubric") or {}).get("version", "2.0.0"),
        subject_label=subject_label,
        control_note=control_note,
        coverage_statements=coverage_statements,
        ahead_by=ahead_by,
        findings_digest=payload.get("findings_digest", ""),
        methodology_text=(
            "Static analysis of repository contents and history. No code was executed. "
            "This is a score, not a certification or guarantee."
        ),
        full_methodology=METHODOLOGY_PARAGRAPH,
    )
    return HTMLResponse(
        content=rendered,
        headers={
            "Content-Security-Policy": _VERIFY_CSP,
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
        },
    )
