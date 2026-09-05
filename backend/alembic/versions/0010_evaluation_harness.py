"""Platform Phase 7 (Evaluation Harness): eval_questions/eval_runs/
eval_results tables.

Bundles all three of this feature's tables in one migration, same style as
0004's scanner-foundation bundle. Purely additive — no existing table is
touched.

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-05
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "eval_questions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("use_case_category", sa.String(), nullable=False),
        sa.Column("ground_truth_answer", sa.Text(), nullable=False),
        sa.Column(
            "ground_truth_citations",
            postgresql.JSONB(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("source", sa.String(), nullable=False, server_default="llm_drafted"),
        sa.Column("human_reviewed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("reviewer_name", sa.String(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_eval_questions_use_case_category", "eval_questions", ["use_case_category"]
    )
    op.create_index("ix_eval_questions_human_reviewed", "eval_questions", ["human_reviewed"])

    op.create_table(
        "eval_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("label", sa.String(), nullable=True),
        sa.Column("git_commit", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="running"),
        sa.Column("question_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_faithfulness", sa.Float(), nullable=True),
        sa.Column("avg_answer_relevance", sa.Float(), nullable=True),
        sa.Column("avg_context_precision", sa.Float(), nullable=True),
        sa.Column("avg_context_recall", sa.Float(), nullable=True),
        sa.Column("avg_latency_ms", sa.Float(), nullable=True),
        sa.Column("total_estimated_cost_usd", sa.Float(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "eval_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "eval_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("eval_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "eval_question_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("eval_questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column("iteration_count", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("generated_answer", sa.Text(), nullable=True),
        sa.Column("faithfulness_score", sa.Float(), nullable=True),
        sa.Column("answer_relevance_score", sa.Float(), nullable=True),
        sa.Column("context_precision_score", sa.Float(), nullable=True),
        sa.Column("context_recall_score", sa.Float(), nullable=True),
        sa.Column("metric_detail", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("retrieved_citations", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_eval_results_eval_run_id", "eval_results", ["eval_run_id"])
    op.create_index("ix_eval_results_eval_question_id", "eval_results", ["eval_question_id"])


def downgrade() -> None:
    op.drop_index("ix_eval_results_eval_question_id", table_name="eval_results")
    op.drop_index("ix_eval_results_eval_run_id", table_name="eval_results")
    op.drop_table("eval_results")
    op.drop_table("eval_runs")
    op.drop_index("ix_eval_questions_human_reviewed", table_name="eval_questions")
    op.drop_index("ix_eval_questions_use_case_category", table_name="eval_questions")
    op.drop_table("eval_questions")
