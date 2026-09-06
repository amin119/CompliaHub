"""Platform Phase 8 (Scaling & Hardening): ingestion-side cost tracking.

Extends Phase 7's `token_tracking.py` pattern from the `/query` path to
ingestion — two new nullable columns on `processing_jobs`, written from
`token_tracking.current()` in `pipeline_stage`'s success path (a no-op when
nothing was tracked, e.g. non-LLM stages like parse/chunk/embed).

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-06
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("processing_jobs", sa.Column("prompt_tokens", sa.Integer(), nullable=True))
    op.add_column("processing_jobs", sa.Column("completion_tokens", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("processing_jobs", "completion_tokens")
    op.drop_column("processing_jobs", "prompt_tokens")
