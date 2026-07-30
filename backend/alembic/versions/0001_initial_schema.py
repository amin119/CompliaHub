"""Initial schema: documents, chunks, processing_jobs + ltree extension.

Revision ID: 0001
Revises:
Create Date: 2026-07-29
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy_utils import LtreeType

from alembic import op

# revision identifiers, used by Alembic.
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ltree: Postgres extension for hierarchical "materialized path" data.
    # Our clause numbers (A.8.1.2, Article 32, ...) already *are* paths, so
    # this lets "everything under Annex A.8" be one indexed query instead of
    # a recursive CTE over a plain adjacency list.
    op.execute("CREATE EXTENSION IF NOT EXISTS ltree")

    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("sha256_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("minio_object_key", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "parent_chunk_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chunks.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("clause_number", sa.String(), nullable=True),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("path", LtreeType(), nullable=False),
        sa.Column("order_in_parent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_chunks_document_id", "chunks", ["document_id"])
    # GiST index is what makes ltree's <@ (descendant-of) / @> (ancestor-of)
    # operators fast — a plain btree index only helps equality/ordering.
    op.execute("CREATE INDEX ix_chunks_path_gist ON chunks USING GIST (path)")

    op.create_table(
        "processing_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("task_name", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_processing_jobs_document_id", "processing_jobs", ["document_id"])


def downgrade() -> None:
    op.drop_table("processing_jobs")
    op.drop_index("ix_chunks_path_gist", table_name="chunks")
    op.drop_index("ix_chunks_document_id", table_name="chunks")
    op.drop_table("chunks")
    op.drop_table("documents")
