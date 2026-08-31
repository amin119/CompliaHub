"""Compliance scanner Phase 4 (AI / ISO 42001 analyzer): scans.ai_status/
ai_error_message.

The `findings` table already carries a nullable `framework` column and an
index on it (added in 0005/0006) — Phase 4 starts writing
`framework="ISO42001"` rows, so no schema change is needed there. This
migration only adds the fourth independent status track on `scans`,
mirroring 0006's `privacy_status`/`privacy_error_message` pair.

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-31
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "scans",
        sa.Column("ai_status", sa.String(), nullable=False, server_default="not_started"),
    )
    op.add_column("scans", sa.Column("ai_error_message", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("scans", "ai_error_message")
    op.drop_column("scans", "ai_status")
