"""x402-paid resources backed by a GoPlausible-compatible facilitator."""

from __future__ import annotations

import base64
import binascii
import json
from typing import Any

import httpx
from fastapi import APIRouter, Header, HTTPException, Response

from backend.app.config import Config
from backend.app.routes.report import _ensure_report

router = APIRouter(prefix="/api/payments", tags=["payments"])


def _requirements() -> dict[str, Any]:
    if not Config.X402_PAY_TO:
        raise HTTPException(
            status_code=503,
            detail={"code": "payment_not_configured", "message": "Set X402_PAY_TO to the Algorand receiving address."},
        )
    return {
        "scheme": "exact",
        "network": Config.X402_NETWORK,
        "maxAmountRequired": Config.X402_AMOUNT,
        "payTo": Config.X402_PAY_TO,
        "asset": Config.X402_ASSET,
        "maxTimeoutSeconds": Config.X402_MAX_TIMEOUT_SECONDS,
    }


def _payment_required() -> dict[str, Any]:
    return {
        "x402Version": 2,
        "accepts": [_requirements()],
        "resource": {
            "url": "/api/payments/report",
            "description": "CODIT audit report",
            "mimeType": "application/json",
        },
    }


def _encode_header(value: dict[str, Any]) -> str:
    encoded = json.dumps(value, separators=(",", ":")).encode()
    return base64.b64encode(encoded).decode()


def _decode_payment_header(value: str) -> dict[str, Any]:
    try:
        payload = json.loads(base64.b64decode(value, validate=True))
    except (ValueError, TypeError, binascii.Error, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_payment_signature", "message": "PAYMENT-SIGNATURE is not valid base64 JSON."},
        ) from exc
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_payment_signature", "message": "PAYMENT-SIGNATURE must contain a JSON object."},
        )
    return payload


async def _facilitator_call(path: str, payment_payload: dict[str, Any], requirements: dict[str, Any]) -> dict[str, Any]:
    if not Config.X402_FACILITATOR_URL:
        raise HTTPException(
            status_code=503,
            detail={"code": "facilitator_not_configured", "message": "Set X402_FACILITATOR_URL to the GoPlausible facilitator URL."},
        )
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            facilitator_response = await client.post(
                f"{Config.X402_FACILITATOR_URL}/{path}",
                json={
                    "x402Version": 2,
                    "paymentPayload": payment_payload,
                    "paymentRequirements": requirements,
                },
                headers={"Accept": "application/json"},
            )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "facilitator_unavailable", "message": "The x402 facilitator could not be reached."},
        ) from exc

    try:
        body = facilitator_response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail={"code": "invalid_facilitator_response", "message": "The facilitator returned invalid JSON."},
        ) from exc
    if facilitator_response.status_code >= 400 or not isinstance(body, dict):
        raise HTTPException(
            status_code=502,
            detail={"code": "facilitator_error", "message": "The facilitator rejected the payment request."},
        )
    return body


@router.get("/requirements")
def payment_requirements():
    """Return the x402 challenge a client uses to construct its payment group."""
    return _payment_required()


@router.get("/report")
async def paid_report(
    response: Response,
    payment_signature: str | None = Header(default=None, alias="PAYMENT-SIGNATURE"),
    legacy_payment: str | None = Header(default=None, alias="X-PAYMENT"),
):
    """Return the audit report after facilitator verification and settlement."""
    challenge = _payment_required()
    if not payment_signature and not legacy_payment:
        response.status_code = 402
        response.headers["PAYMENT-REQUIRED"] = _encode_header(challenge)
        return {"error": {"code": "payment_required", "message": "A valid Algorand payment is required."}, **challenge}

    payment_payload = _decode_payment_header(payment_signature or legacy_payment or "")
    requirements = challenge["accepts"][0]
    verification = await _facilitator_call("verify", payment_payload, requirements)
    if verification.get("isValid") is not True and verification.get("valid") is not True:
        response.status_code = 402
        response.headers["PAYMENT-REQUIRED"] = _encode_header(challenge)
        return {"error": {"code": "payment_invalid", "message": "The facilitator rejected the payment."}, **verification}

    report = _ensure_report()
    settlement = await _facilitator_call("settle", payment_payload, requirements)
    if settlement.get("success") is not True:
        response.status_code = 402
        response.headers["PAYMENT-REQUIRED"] = _encode_header(challenge)
        return {"error": {"code": "payment_unsettled", "message": "The facilitator could not settle the payment."}, **settlement}

    response.headers["PAYMENT-RESPONSE"] = _encode_header(settlement)
    return report.to_dict()