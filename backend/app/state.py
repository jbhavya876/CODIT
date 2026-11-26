"""
Retired process-global state module.

All active codebase and audit report state now lives in SQLAlchemy via
`backend.app.services.audit_service` and per-audit `GraphHandle` instances.
"""

from __future__ import annotations

__all__: list[str] = []
