"""Phase 3 schema: chunk_extractions cache table + documents.graph_status.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-05
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chunk_extractions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("extraction_result", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.add_column(
        "documents",
        sa.Column(
            "graph_status", sa.String(), nullable=False, server_default="not_started"
        ),
    )
    op.add_column("documents", sa.Column("graph_error_message", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "graph_error_message")
    op.drop_column("documents", "graph_status")
    op.drop_table("chunk_extractions")
