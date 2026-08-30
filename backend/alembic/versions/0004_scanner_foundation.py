"""Compliance scanner Phase 1: scans, repository_files,
scan_processing_jobs, evidence.

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-30
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("repository_name", sa.String(), nullable=True),
        sa.Column("source_type", sa.String(), nullable=False, server_default="zip"),
        sa.Column("original_filename", sa.String(), nullable=False),
        sa.Column("sha256_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("archive_object_key", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("file_count", sa.Integer(), nullable=True),
        sa.Column("total_size_bytes", sa.Integer(), nullable=True),
        sa.Column(
            "detected_languages", postgresql.JSONB(), nullable=False, server_default="[]"
        ),
        sa.Column(
            "detected_frameworks", postgresql.JSONB(), nullable=False, server_default="[]"
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "repository_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "scan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("relative_path", sa.String(), nullable=False),
        sa.Column("language", sa.String(), nullable=True),
        sa.Column("component_type", sa.String(), nullable=False, server_default="unknown"),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("content_stored", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("minio_object_key", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_repository_files_scan_id", "repository_files", ["scan_id"])
    op.create_index(
        "ix_repository_files_component_type", "repository_files", ["component_type"]
    )

    op.create_table(
        "scan_processing_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "scan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("task_name", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_scan_processing_jobs_scan_id", "scan_processing_jobs", ["scan_id"]
    )

    op.create_table(
        "evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "scan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "repository_file_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("repository_files.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source_type", sa.String(), nullable=True),
        sa.Column("rule_id", sa.String(), nullable=True),
        sa.Column("file_path", sa.String(), nullable=True),
        sa.Column("line_start", sa.Integer(), nullable=True),
        sa.Column("line_end", sa.Integer(), nullable=True),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("confidence", sa.String(), nullable=True),
        sa.Column("evidence_metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_evidence_scan_id", "evidence", ["scan_id"])
    op.create_index("ix_evidence_repository_file_id", "evidence", ["repository_file_id"])


def downgrade() -> None:
    op.drop_index("ix_evidence_repository_file_id", table_name="evidence")
    op.drop_index("ix_evidence_scan_id", table_name="evidence")
    op.drop_table("evidence")

    op.drop_index("ix_scan_processing_jobs_scan_id", table_name="scan_processing_jobs")
    op.drop_table("scan_processing_jobs")

    op.drop_index("ix_repository_files_component_type", table_name="repository_files")
    op.drop_index("ix_repository_files_scan_id", table_name="repository_files")
    op.drop_table("repository_files")

    op.drop_table("scans")
