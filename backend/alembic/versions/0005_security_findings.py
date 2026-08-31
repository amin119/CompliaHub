"""Compliance scanner Phase 2: findings table, evidence.finding_id,
scans.findings_status/findings_error_message.

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-30
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "scans",
        sa.Column("findings_status", sa.String(), nullable=False, server_default="not_started"),
    )
    op.add_column("scans", sa.Column("findings_error_message", sa.Text(), nullable=True))

    op.create_table(
        "findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "scan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("framework", sa.String(), nullable=True),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("rule_id", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("confidence", sa.String(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("reasoning", sa.Text(), nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=True),
        sa.Column("automated", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("human_review_required", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_findings_scan_id", "findings", ["scan_id"])
    op.create_index("ix_findings_severity", "findings", ["severity"])
    op.create_index("ix_findings_category", "findings", ["category"])

    # Added after `findings` exists, since it references it.
    op.add_column(
        "evidence",
        sa.Column(
            "finding_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("findings.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_evidence_finding_id", "evidence", ["finding_id"])


def downgrade() -> None:
    op.drop_index("ix_evidence_finding_id", table_name="evidence")
    op.drop_column("evidence", "finding_id")

    op.drop_index("ix_findings_category", table_name="findings")
    op.drop_index("ix_findings_severity", table_name="findings")
    op.drop_index("ix_findings_scan_id", table_name="findings")
    op.drop_table("findings")

    op.drop_column("scans", "findings_error_message")
    op.drop_column("scans", "findings_status")
