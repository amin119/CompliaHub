"""Compliance scanner Phase 7 (Human Review): finding_reviews table.

Adds the one mechanism in this system that can ever write
VERIFIED/PARTIALLY_VERIFIED/NOT_APPLICABLE onto findings.status — every
prior phase (2-6) only ever produces POTENTIAL_NON_COMPLIANCE,
REQUIRES_HUMAN_REVIEW, or (ISO 27001 mapping only) NOT_VERIFIED. No change
to findings/evidence's own columns — purely a new, append-only table.

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-04
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "finding_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "scan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "finding_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("findings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("reviewer_name", sa.String(), nullable=True),
        sa.Column("decision", sa.String(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("previous_status", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_finding_reviews_scan_id", "finding_reviews", ["scan_id"])
    op.create_index("ix_finding_reviews_finding_id", "finding_reviews", ["finding_id"])


def downgrade() -> None:
    op.drop_index("ix_finding_reviews_finding_id", table_name="finding_reviews")
    op.drop_index("ix_finding_reviews_scan_id", table_name="finding_reviews")
    op.drop_table("finding_reviews")
