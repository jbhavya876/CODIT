"""SQLAlchemy 2 ORM models for CODIT pivot tables (Section 9)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


_AUTO_BIGINT = BigInteger().with_variant(Integer, "sqlite")


class Base(DeclarativeBase):
    pass


class AuditRow(Base):
    __tablename__ = "audits"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False)
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    source_ref: Mapped[str] = mapped_column(String(256), nullable=False)
    source_commit: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    source_tree: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    source_archive_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    options_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    coverage_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    rubric_version: Mapped[str] = mapped_column(String(32), default="1.0.0", nullable=False)
    engine_version: Mapped[str] = mapped_column(String(32), default="3.0.0", nullable=False)
    scorecard_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    process_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    licenses_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    ownership_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    graph_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    report_meta_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    staged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    events: Mapped[list["AuditEventRow"]] = relationship(
        back_populates="audit",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    findings: Mapped[list["FindingRow"]] = relationship(
        back_populates="audit",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (Index("ix_audits_expires_at", "expires_at"),)


class AuditEventRow(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(_AUTO_BIGINT, primary_key=True, autoincrement=True)
    audit_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("audits.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    level: Mapped[str] = mapped_column(String(16), default="info", nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    data_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    audit: Mapped[AuditRow] = relationship(back_populates="events")


class FindingRow(Base):
    __tablename__ = "findings"

    id: Mapped[int] = mapped_column(_AUTO_BIGINT, primary_key=True, autoincrement=True)
    finding_uid: Mapped[str] = mapped_column(String(128), nullable=False)
    audit_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("audits.id", ondelete="CASCADE"),
        nullable=False,
    )
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    rule_id: Mapped[str] = mapped_column(String(64), nullable=False)
    dimension: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    confidence: Mapped[str] = mapped_column(String(16), nullable=False)
    basis: Mapped[str] = mapped_column(String(32), default="AST PROOF", nullable=False)
    evidence_file: Mapped[str] = mapped_column(String(512), nullable=False)
    evidence_line: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    commit_sha: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    remediation: Mapped[str] = mapped_column(Text, default="", nullable=False)
    component_id: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    params_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    audit: Mapped[AuditRow] = relationship(back_populates="findings")

    __table_args__ = (
        Index("ix_findings_audit_severity", "audit_id", "severity"),
        Index("ix_findings_audit_rule", "audit_id", "rule_id"),
    )


class BlobMetricRow(Base):
    __tablename__ = "blob_metrics"

    blob_sha: Mapped[str] = mapped_column(String(64), primary_key=True)
    analyzer_version: Mapped[str] = mapped_column(String(32), primary_key=True)
    metrics_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class LicenseCacheRow(Base):
    __tablename__ = "license_cache"

    system: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), primary_key=True)
    version: Mapped[str] = mapped_column(String(128), primary_key=True)
    licenses_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class AttestationRow(Base):
    __tablename__ = "attestations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    audit_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        ForeignKey("audits.id", ondelete="SET NULL"),
        nullable=True,
    )
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    subject_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    signature: Mapped[str] = mapped_column(String(256), nullable=False)
    kid: Mapped[str] = mapped_column(String(64), nullable=False)
    control_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_reason_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)


class AttestChallengeRow(Base):
    __tablename__ = "attest_challenges"

    nonce: Mapped[str] = mapped_column(String(128), primary_key=True)
    repo: Mapped[str] = mapped_column(String(256), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
