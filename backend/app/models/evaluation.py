import uuid
from datetime import datetime, timezone

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import DateTime

from app.core.db import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def _now() -> datetime:
    return datetime.now(timezone.utc)


class EvalQuestion(Base):
    """A ground-truth question/answer/citation triple for Phase 7's
    evaluation harness. Deliberately a Postgres table, not a JSON fixture —
    needs the same mutable, auditable, endpoint-editable row `FindingReview`
    established for the scanner's human-review discipline (see
    docs/scanner-phase-7-human-review.md); a static fixture can't support
    that review workflow without inventing a separate mechanism anyway.

    `human_reviewed` mirrors that same discipline: an LLM-drafted row (see
    `scripts/generate_eval_questions.py`) starts unreviewed and must never
    be silently treated as trustworthy ground truth until a person confirms
    it via `PATCH /eval/questions/{id}`.
    """

    __tablename__ = "eval_questions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    # cross_standard_mapping | gap_analysis | multi_hop_traversal |
    # audit_evidence_lookup | impact_analysis — the roadmap's own 5 use-case
    # categories (docs/phase-7-evaluation.md), not `QueryCategory`'s
    # vector/graph/agent routing labels (that's `EvalResult.category`).
    use_case_category: Mapped[str] = mapped_column(String, nullable=False)
    ground_truth_answer: Mapped[str] = mapped_column(Text, nullable=False)
    # [{document_filename, clause_number}, ...] — denormalized, not FK'd to
    # chunks.id: chunk ids churn on re-ingestion, but a citation's
    # document/clause identity is stable enough to review by eye.
    ground_truth_citations: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    source: Mapped[str] = mapped_column(String, nullable=False, default="llm_drafted")
    human_reviewed: Mapped[bool] = mapped_column(default=False)
    reviewer_name: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class EvalRun(Base):
    """One execution of the eval question set against the real, live
    `/query` pipeline (via `query_orchestration.run_query`) — aggregate
    columns are denormalized rollups computed once when the run finishes,
    so comparing runs never re-aggregates `EvalResult` rows on every read
    (the same "cheap to query trends over time" reasoning the roadmap gives
    for picking Postgres over Langfuse in the first place).
    """

    __tablename__ = "eval_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    label: Mapped[str | None] = mapped_column(String, nullable=True)
    git_commit: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="running")
    question_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_faithfulness: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_answer_relevance: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_context_precision: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_context_recall: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_estimated_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EvalResult(Base):
    """One question's real outcome within one `EvalRun` — never mutated
    after being written (a re-run creates new `EvalRun`/`EvalResult` rows,
    same clear-and-rebuild-with-new-UUIDs convention used everywhere else in
    this codebase, not an update-in-place).
    """

    __tablename__ = "eval_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    eval_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("eval_runs.id", ondelete="CASCADE"), nullable=False
    )
    eval_question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("eval_questions.id", ondelete="CASCADE"), nullable=False
    )
    # The real routing path this question actually took (query_classifier's
    # QueryCategory value) — distinct from EvalQuestion.use_case_category,
    # which is the roadmap's use-case taxonomy, not the retrieval strategy.
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    iteration_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    generated_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    faithfulness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    answer_relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    context_precision_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    context_recall_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    metric_detail: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    retrieved_citations: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # One bad question (a transient LLM failure, a malformed judge response
    # after retries) must not abort the whole run — recorded here instead,
    # leaving every score column null for this row.
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
