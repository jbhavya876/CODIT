"""Initial CODIT pivot schema (Section 9 tables).

Revision ID: 0001_pivot
Revises:
Create Date: 2026-11-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_pivot"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audits",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source_kind", sa.String(length=32), nullable=False),
        sa.Column("source_ref", sa.String(length=256), nullable=False),
        sa.Column("source_commit", sa.String(length=64), nullable=True),
        sa.Column("source_tree", sa.String(length=64), nullable=True),
        sa.Column("source_archive_sha256", sa.String(length=64), nullable=True),
        sa.Column("options_json", sa.JSON(), nullable=True),
        sa.Column("coverage_json", sa.JSON(), nullable=True),
        sa.Column("rubric_version", sa.String(length=32), nullable=False),
        sa.Column("engine_version", sa.String(length=32), nullable=False),
        sa.Column("scorecard_json", sa.JSON(), nullable=True),
        sa.Column("process_json", sa.JSON(), nullable=True),
        sa.Column("licenses_json", sa.JSON(), nullable=True),
        sa.Column("ownership_json", sa.JSON(), nullable=True),
        sa.Column("graph_json", sa.Text(), nullable=True),
        sa.Column("report_meta_json", sa.JSON(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("staged_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audits_expires_at", "audits", ["expires_at"])

    op.create_table(
        "audit_events",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False),
        sa.Column("audit_id", sa.String(length=64), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stage", sa.String(length=32), nullable=False),
        sa.Column("level", sa.String(length=16), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("data_json", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["audit_id"], ["audits.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_events_audit_id", "audit_events", ["audit_id"])

    op.create_table(
        "findings",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False),
        sa.Column("finding_uid", sa.String(length=128), nullable=False),
        sa.Column("audit_id", sa.String(length=64), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("rule_id", sa.String(length=64), nullable=False),
        sa.Column("dimension", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("confidence", sa.String(length=16), nullable=False),
        sa.Column("basis", sa.String(length=32), nullable=False),
        sa.Column("evidence_file", sa.String(length=512), nullable=False),
        sa.Column("evidence_line", sa.Integer(), nullable=True),
        sa.Column("commit_sha", sa.String(length=64), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("remediation", sa.Text(), nullable=False),
        sa.Column("component_id", sa.String(length=512), nullable=True),
        sa.Column("params_json", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["audit_id"], ["audits.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_findings_audit_severity", "findings", ["audit_id", "severity"])
    op.create_index("ix_findings_audit_rule", "findings", ["audit_id", "rule_id"])

    op.create_table(
        "blob_metrics",
        sa.Column("blob_sha", sa.String(length=64), nullable=False),
        sa.Column("analyzer_version", sa.String(length=32), nullable=False),
        sa.Column("metrics_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("blob_sha", "analyzer_version"),
    )

    op.create_table(
        "license_cache",
        sa.Column("system", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("version", sa.String(length=128), nullable=False),
        sa.Column("licenses_json", sa.JSON(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("system", "name", "version"),
    )

    op.create_table(
        "attestations",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("audit_id", sa.String(length=64), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("subject_json", sa.JSON(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("signature", sa.String(length=256), nullable=False),
        sa.Column("kid", sa.String(length=64), nullable=False),
        sa.Column("control_verified", sa.Boolean(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason_code", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["audit_id"], ["audits.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "attest_challenges",
        sa.Column("nonce", sa.String(length=128), nullable=False),
        sa.Column("repo", sa.String(length=256), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("nonce"),
    )


def downgrade() -> None:
    op.drop_table("attest_challenges")
    op.drop_table("attestations")
    op.drop_table("license_cache")
    op.drop_table("blob_metrics")
    op.drop_index("ix_findings_audit_rule", table_name="findings")
    op.drop_index("ix_findings_audit_severity", table_name="findings")
    op.drop_table("findings")
    op.drop_index("ix_audit_events_audit_id", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_audits_expires_at", table_name="audits")
    op.drop_table("audits")
