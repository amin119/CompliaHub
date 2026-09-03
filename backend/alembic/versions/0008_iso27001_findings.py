"""Compliance scanner Phase 5 (ISO 27001 mapping): scans.iso27001_status/
iso27001_error_message.

The `findings` table already carries a nullable `framework` column and an
index on it — Phase 5 starts writing `framework="ISO27001"` rows, so no
schema change is needed there. This migration only adds the fifth
independent status track on `scans`, mirroring 0007's `ai_status`/
`ai_error_message` pair.

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-31
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "scans",
        sa.Column("iso27001_status", sa.String(), nullable=False, server_default="not_started"),
    )
    op.add_column("scans", sa.Column("iso27001_error_message", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("scans", "iso27001_error_message")
    op.drop_column("scans", "iso27001_status")
