import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EvalQuestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    question: str
    use_case_category: str
    ground_truth_answer: str
    ground_truth_citations: list[dict]
    source: str
    human_reviewed: bool
    reviewer_name: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class EvalQuestionUpdateRequest(BaseModel):
    """All fields optional — a review pass typically only sets
    `human_reviewed`/`reviewer_name`, but can also correct the LLM-drafted
    question/answer/citations text itself.
    """

    question: str | None = None
    ground_truth_answer: str | None = None
    ground_truth_citations: list[dict] | None = None
    human_reviewed: bool | None = None
    reviewer_name: str | None = None
    notes: str | None = None


class EvalRunCreateRequest(BaseModel):
    label: str | None = None
    # None means "every row currently in eval_questions" — pass explicit
    # ids to run only the reviewed subset (fetch them first via
    # GET /eval/questions?human_reviewed=true) or to iterate on the harness
    # itself against a small handful before the full set is reviewed.
    question_ids: list[uuid.UUID] | None = None


class EvalRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    label: str | None
    git_commit: str | None
    status: str
    question_count: int
    avg_faithfulness: float | None
    avg_answer_relevance: float | None
    avg_context_precision: float | None
    avg_context_recall: float | None
    avg_latency_ms: float | None
    total_estimated_cost_usd: float | None
    error_message: str | None
    started_at: datetime
    finished_at: datetime | None


class EvalResultResponse(BaseModel):
    id: uuid.UUID
    eval_question_id: uuid.UUID
    question: str
    category: str | None
    iteration_count: int | None
    latency_ms: float | None
    prompt_tokens: int
    completion_tokens: int
    estimated_cost_usd: float
    generated_answer: str | None
    faithfulness_score: float | None
    answer_relevance_score: float | None
    context_precision_score: float | None
    context_recall_score: float | None
    metric_detail: dict
    retrieved_citations: list
    error_message: str | None
    created_at: datetime


class MetricDelta(BaseModel):
    metric: str
    run_a: float | None
    run_b: float | None
    delta: float | None


class RegressedQuestion(BaseModel):
    eval_question_id: uuid.UUID
    question: str
    metric: str
    run_a_score: float
    run_b_score: float
    drop: float


class EvalRunCompareResponse(BaseModel):
    run_a: EvalRunResponse
    run_b: EvalRunResponse
    deltas: list[MetricDelta]
    regressed_questions: list[RegressedQuestion]
