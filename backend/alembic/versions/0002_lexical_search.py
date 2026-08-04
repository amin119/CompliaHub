"""Lexical search: generated tsvector column + GIN index on chunks.

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-02
"""


from alembic import op

# revision identifiers, used by Alembic.
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # STORED generated column: Postgres keeps this in sync with `text` on
    # every write, so lexical search never reads stale tokens. `to_tsvector`
    # + `ts_rank_cd` is Postgres's built-in full-text search — not literally
    # BM25 (no document-length normalization), but the pragmatic "good
    # enough at this corpus size" lexical half of hybrid search, per the
    # phase-2 plan.
    op.execute(
        """
        ALTER TABLE chunks
        ADD COLUMN text_search_vector tsvector
        GENERATED ALWAYS AS (to_tsvector('english', text)) STORED
        """
    )
    op.execute(
        "CREATE INDEX ix_chunks_text_search_vector_gin "
        "ON chunks USING GIN (text_search_vector)"
    )


def downgrade() -> None:
    op.drop_index("ix_chunks_text_search_vector_gin", table_name="chunks")
    op.drop_column("chunks", "text_search_vector")
