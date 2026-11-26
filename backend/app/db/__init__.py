"""Database package: SQLAlchemy 2 engine, session lifecycle, and ORM models."""

from backend.app.db.engine import get_engine, get_session_factory, init_db, reset_engine_for_tests, session_scope
from backend.app.db.models import (
    AttestChallengeRow,
    AttestationRow,
    AuditEventRow,
    AuditRow,
    Base,
    BlobMetricRow,
    FindingRow,
    LicenseCacheRow,
)

__all__ = [
    "AttestChallengeRow",
    "AttestationRow",
    "AuditEventRow",
    "AuditRow",
    "Base",
    "BlobMetricRow",
    "FindingRow",
    "LicenseCacheRow",
    "get_engine",
    "get_session_factory",
    "init_db",
    "reset_engine_for_tests",
    "session_scope",
]
