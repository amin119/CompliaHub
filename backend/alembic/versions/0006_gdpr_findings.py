"""Compliance scanner Phase 3 (GDPR analyzer): scans.privacy_status/
privacy_error_message.

The `findings` table already carries a nullable `framework` column (added
in 0005, unused until now) — Phase 3 starts writing `framework="GDPR"`
rows to it, so no schema change is needed there. This migration only adds
the third independent status track on `scans`, mirroring 0005's
`findings_status`/`findings_error_message` pair.

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-31
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "scans",
        sa.Column("privacy_status", sa.String(), nullable=False, server_default="not_started"),
    )
    op.add_column("scans", sa.Column("privacy_error_message", sa.Text(), nullable=True))

    # A framework index makes the per-framework idempotent-clear
    # (`DELETE ... WHERE scan_id = ? AND framework [IS NULL | = 'GDPR']`) and
    # the new `?framework=` API filter cheap once both frameworks' rows
    # share the table.
    op.create_index("ix_findings_framework", "findings", ["framework"])


def downgrade() -> None:
    op.drop_index("ix_findings_framework", table_name="findings")
    op.drop_column("scans", "privacy_error_message")
    op.drop_column("scans", "privacy_status")
