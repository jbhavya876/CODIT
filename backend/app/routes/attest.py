"""Attestation challenge and issuance routes (P8)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.app.attest.challenge import InvalidChallengeRepoError, create_challenge
from backend.app.attest.service import AttestError, get_attestation_record, issue_attestation
from backend.app.delivery.entitlements import enforce_entitlement
from backend.app.services import audit_service

router = APIRouter(tags=["attestation"])


class ChallengeRequest(BaseModel):
    repo: str


class AttestRequest(BaseModel):
    consent_publish: Optional[bool] = False


@router.post("/api/attest/challenge")
def post_attest_challenge(payload: ChallengeRequest):
    try:
        return create_challenge(payload.repo)
    except InvalidChallengeRepoError as exc:
        raise HTTPException(status_code=400, detail={"code": "invalid_repo", "message": str(exc)}) from exc


@router.post("/api/audits/{audit_id}/attest", status_code=201)
def post_issue_attestation(audit_id: str, payload: AttestRequest, request: Request):
    row = audit_service.get_audit_row(audit_id)
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Audit not found."})

    if payload.consent_publish is not True:
        raise HTTPException(
            status_code=400,
            detail={"code": "consent_required", "message": "Set consent_publish=true to publish this attestation."},
        )

    decision = enforce_entitlement(
        request,
        resource=f"/api/audits/{audit_id}/attest",
        required=True,
        audit_row=row,
    )
    if not decision.allowed:
        return JSONResponse(
            status_code=decision.status_code,
            content={"error": {"code": decision.code, "message": decision.message}, "payment_requirements": decision.challenge},
            headers=decision.headers,
        )

    try:
        return issue_attestation(audit_id, consent_publish=True)
    except AttestError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": exc.message}) from exc


@router.get("/api/attest/{attestation_id}")
def get_public_attestation_json(attestation_id: str):
    rec = get_attestation_record(attestation_id)
    if rec is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Attestation not found."})
    return rec["payload"]
