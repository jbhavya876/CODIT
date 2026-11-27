"""Admin attestation revocation endpoint (P8), strictly guarded by ADMIN_TOKEN."""

from __future__ import annotations

import hmac
import os
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from backend.app.attest.service import AttestError, revoke_attestation
from backend.app.config import Config

router = APIRouter(prefix="/api/admin", tags=["admin"])


class RevokeRequest(BaseModel):
    reason_code: str


@router.post("/attest/{attestation_id}/revoke")
def post_revoke_attestation(
    attestation_id: str,
    payload: RevokeRequest,
    authorization: Optional[str] = Header(default=None),
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
):
    expected = (os.getenv("ADMIN_TOKEN") or Config.ADMIN_TOKEN or "").strip()
    if not expected:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Resource not found."})

    supplied = (x_admin_token or "").strip()
    if not supplied and authorization and authorization.lower().startswith("bearer "):
        supplied = authorization[7:].strip()

    if not supplied or not hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8")):
        raise HTTPException(status_code=401, detail={"code": "unauthorized", "message": "Invalid admin token."})

    try:
        return revoke_attestation(attestation_id, payload.reason_code)
    except AttestError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": exc.message}) from exc
