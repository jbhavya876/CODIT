"""
Entitlement provider abstraction gating commercial profiles (`diligence`, `executive`,
`underwriting`) and attestation issuance without hard-wiring x402 as the only rail.
"""

from __future__ import annotations

import base64
import binascii
import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import httpx
from fastapi import Request

from backend.app.config import Config
from backend.app.db.models import AuditRow


@dataclass
class EntitlementDecision:
    allowed: bool
    status_code: int = 200
    code: str = "ok"
    message: str = ""
    headers: Dict[str, str] = field(default_factory=dict)
    challenge: Optional[Dict[str, Any]] = None


def build_price_metadata(resource_path: str = "/api/audits/report") -> Dict[str, Any]:
    """Return machine-readable payment/price metadata matching the existing x402 flow."""
    pay_to = Config.X402_PAY_TO or "UNCONFIGURED"
    return {
        "x402Version": 2,
        "accepts": [
            {
                "scheme": "exact",
                "network": Config.X402_NETWORK,
                "amount": Config.X402_AMOUNT,
                "payTo": pay_to,
                "asset": Config.X402_ASSET,
                "maxTimeoutSeconds": Config.X402_MAX_TIMEOUT_SECONDS,
                "extra": {
                    "decimals": Config.X402_DECIMALS,
                    **({"feePayer": Config.X402_FEE_PAYER} if Config.X402_FEE_PAYER else {}),
                },
            }
        ],
        "resource": {
            "url": Config.X402_RESOURCE_URL or resource_path,
            "description": "CODIT assurance profile / attestation",
            "mimeType": "application/json",
        },
    }


def _b64_json(val: Dict[str, Any]) -> str:
    return base64.b64encode(json.dumps(val, separators=(",", ":")).encode("utf-8")).decode("ascii")


class EntitlementProvider(ABC):
    """Interface for plugging payment or plan entitlement rails cleanly."""

    @abstractmethod
    def check_entitlement(
        self,
        request: Optional[Request],
        resource: str,
        audit_row: Optional[AuditRow] = None,
    ) -> EntitlementDecision:
        ...


class FreeTierProvider(EntitlementProvider):
    """Grants access without payment (local/self-hosted/free-tier mode)."""

    def check_entitlement(
        self,
        request: Optional[Request],
        resource: str,
        audit_row: Optional[AuditRow] = None,
    ) -> EntitlementDecision:
        return EntitlementDecision(allowed=True, status_code=200, code="free_tier")


class X402Provider(EntitlementProvider):
    """Verifies and settles x402 payment headers against the GoPlausible-compatible facilitator."""

    def check_entitlement(
        self,
        request: Optional[Request],
        resource: str,
        audit_row: Optional[AuditRow] = None,
    ) -> EntitlementDecision:
        challenge = build_price_metadata(resource_path=resource)
        if not Config.X402_PAY_TO:
            return EntitlementDecision(
                allowed=False,
                status_code=402,
                code="entitlement_required",
                message="Payment or entitlement required to access this profile.",
                headers={"PAYMENT-REQUIRED": _b64_json(challenge)},
                challenge=challenge,
            )

        sig_header = None
        if request is not None:
            sig_header = request.headers.get("PAYMENT-SIGNATURE") or request.headers.get("X-PAYMENT")
        if not sig_header:
            return EntitlementDecision(
                allowed=False,
                status_code=402,
                code="entitlement_required",
                message="A valid payment authorization is required for this profile.",
                headers={"PAYMENT-REQUIRED": _b64_json(challenge)},
                challenge=challenge,
            )

        try:
            payment_payload = json.loads(base64.b64decode(sig_header, validate=True))
            if not isinstance(payment_payload, dict):
                raise ValueError("not an object")
        except (ValueError, TypeError, binascii.Error, json.JSONDecodeError):
            return EntitlementDecision(
                allowed=False,
                status_code=400,
                code="invalid_payment_signature",
                message="PAYMENT-SIGNATURE is not valid base64 JSON.",
                challenge=challenge,
            )

        if not Config.X402_FACILITATOR_URL:
            return EntitlementDecision(
                allowed=False,
                status_code=503,
                code="facilitator_not_configured",
                message="Set X402_FACILITATOR_URL to verify x402 payments.",
                challenge=challenge,
            )

        requirements = challenge["accepts"][0]
        try:
            with httpx.Client(timeout=15.0) as client:
                v_resp = client.post(
                    f"{Config.X402_FACILITATOR_URL}/verify",
                    json={"x402Version": 2, "paymentPayload": payment_payload, "paymentRequirements": requirements},
                    headers={"Accept": "application/json"},
                )
                v_body = v_resp.json()
                if v_resp.status_code >= 400 or (v_body.get("isValid") is not True and v_body.get("valid") is not True):
                    return EntitlementDecision(
                        allowed=False,
                        status_code=402,
                        code="entitlement_required",
                        message=str(v_body.get("invalidReason") or "Payment verification failed."),
                        headers={"PAYMENT-REQUIRED": _b64_json(challenge)},
                        challenge=challenge,
                    )
                s_resp = client.post(
                    f"{Config.X402_FACILITATOR_URL}/settle",
                    json={"x402Version": 2, "paymentPayload": payment_payload, "paymentRequirements": requirements},
                    headers={"Accept": "application/json"},
                )
                s_body = s_resp.json()
                if s_resp.status_code >= 400 or s_body.get("success") is not True:
                    return EntitlementDecision(
                        allowed=False,
                        status_code=402,
                        code="entitlement_required",
                        message="Payment settlement did not succeed.",
                        headers={"PAYMENT-REQUIRED": _b64_json(challenge)},
                        challenge=challenge,
                    )
                return EntitlementDecision(
                    allowed=True,
                    status_code=200,
                    code="x402_settled",
                    headers={"PAYMENT-RESPONSE": _b64_json(s_body)},
                )
        except httpx.HTTPError:
            return EntitlementDecision(
                allowed=False,
                status_code=503,
                code="facilitator_unavailable",
                message="The payment facilitator could not be reached.",
                challenge=challenge,
            )


def get_entitlement_provider(request: Optional[Request] = None) -> Optional[EntitlementProvider]:
    """
    Resolve active EntitlementProvider from app.state override or ENV configuration.
    `ENTITLEMENT_MODE=none` explicitly simulates no active provider (403 entitlement_required).
    """
    if request is not None and hasattr(request.app.state, "entitlement_provider"):
        return request.app.state.entitlement_provider

    mode = os.getenv("ENTITLEMENT_MODE", "").strip().lower()
    if mode == "none":
        return None
    if mode == "free":
        return FreeTierProvider()
    if mode == "x402":
        return X402Provider()

    # Default: use X402Provider when x402 is configured, otherwise FreeTierProvider in dev/test
    if Config.X402_PAY_TO:
        return X402Provider()
    if Config.ENV == "production":
        return None
    return FreeTierProvider()


def enforce_entitlement(
    request: Optional[Request],
    *,
    resource: str,
    required: bool,
    audit_row: Optional[AuditRow] = None,
) -> EntitlementDecision:
    if not required:
        return EntitlementDecision(allowed=True)
    provider = get_entitlement_provider(request)
    if provider is None:
        challenge = build_price_metadata(resource_path=resource)
        return EntitlementDecision(
            allowed=False,
            status_code=403,
            code="entitlement_required",
            message="Entitlement provider is required for commercial profiles and attestations.",
            challenge=challenge,
        )
    return provider.check_entitlement(request, resource, audit_row)
