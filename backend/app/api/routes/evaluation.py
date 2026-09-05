import subprocess
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.evaluation import EvalQuestion, EvalResult, EvalRun
from app.schemas.evaluation import (
    EvalQuestionResponse,
    EvalQuestionUpdateRequest,
    EvalResultResponse,
    EvalRunCompareResponse,
    EvalRunCreateRequest,
    EvalRunResponse,
    MetricDelta,
    RegressedQuestion,
)
from app.services import eval_aggregation
from app.tasks.evaluation import run_evaluation_task

router = APIRouter(prefix="/eval", tags=["evaluation"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _git_commit() -> str | None:
    """Best-effort only, captured at run creation ("run start") — a "what
    code was this run against" breadcrumb, never required for the run to
    succeed.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5, check=True
        )
        return result.stdout.strip()
    except Exception:
        return None


@router.get("/questions", response_model=list[EvalQuestionResponse])
def list_eval_questions(
    human_reviewed: bool | None = Query(default=None),
    use_case_category: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    query = select(EvalQuestion)
    if human_reviewed is not None:
        query = query.where(EvalQuestion.human_reviewed == human_reviewed)
    if use_case_category is not None:
        query = query.where(EvalQuestion.use_case_category == use_case_category)
    return list(db.scalars(query.order_by(EvalQuestion.created_at)))


@router.patch("/questions/{question_id}", response_model=EvalQuestionResponse)
def update_eval_question(
    question_id: uuid.UUID, request: EvalQuestionUpdateRequest, db: Session = Depends(get_db)
):
    question = db.get(EvalQuestion, question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="eval question not found")

    updates = request.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(question, field, value)
    db.commit()
    db.refresh(question)
    return question


@router.post("/runs", response_model=EvalRunResponse, status_code=202)
def create_eval_run(request: EvalRunCreateRequest, db: Session = Depends(get_db)):
    if request.question_ids:
        target_ids = [str(qid) for qid in request.question_ids]
        question_count = len(
            list(
                db.scalars(
                    select(EvalQuestion.id).where(EvalQuestion.id.in_(request.question_ids))
                )
            )
        )
    else:
        target_ids = None
        question_count = len(list(db.scalars(select(EvalQuestion.id))))

    eval_run = EvalRun(
        label=request.label,
        git_commit=_git_commit(),
        status="running",
        question_count=question_count,
        started_at=_now(),
    )
    db.add(eval_run)
    db.commit()
    db.refresh(eval_run)

    run_evaluation_task.delay(str(eval_run.id), question_ids=target_ids)

    return eval_run


@router.get("/runs/compare", response_model=EvalRunCompareResponse)
def compare_eval_runs(a: uuid.UUID, b: uuid.UUID, db: Session = Depends(get_db)):
    run_a = db.get(EvalRun, a)
    run_b = db.get(EvalRun, b)
    if run_a is None or run_b is None:
        raise HTTPException(status_code=404, detail="one or both eval runs not found")

    results_a = list(db.scalars(select(EvalResult).where(EvalResult.eval_run_id == a)))
    results_b = list(db.scalars(select(EvalResult).where(EvalResult.eval_run_id == b)))

    deltas = eval_aggregation.compare_runs(run_a, run_b)
    regressed = eval_aggregation.find_regressed_questions(results_a, results_b)

    questions_by_id = {
        question.id: question
        for question in db.scalars(
            select(EvalQuestion).where(
                EvalQuestion.id.in_({r["eval_question_id"] for r in regressed})
            )
        )
    }

    return EvalRunCompareResponse(
        run_a=run_a,
        run_b=run_b,
        deltas=[MetricDelta(**delta) for delta in deltas],
        regressed_questions=[
            RegressedQuestion(
                eval_question_id=r["eval_question_id"],
                question=questions_by_id[r["eval_question_id"]].question,
                metric=r["metric"],
                run_a_score=r["run_a_score"],
                run_b_score=r["run_b_score"],
                drop=r["drop"],
            )
            for r in regressed
        ],
    )


@router.get("/runs/{run_id}", response_model=EvalRunResponse)
def get_eval_run(run_id: uuid.UUID, db: Session = Depends(get_db)):
    eval_run = db.get(EvalRun, run_id)
    if eval_run is None:
        raise HTTPException(status_code=404, detail="eval run not found")
    return eval_run


@router.get("/runs/{run_id}/results", response_model=list[EvalResultResponse])
def get_eval_run_results(run_id: uuid.UUID, db: Session = Depends(get_db)):
    if db.get(EvalRun, run_id) is None:
        raise HTTPException(status_code=404, detail="eval run not found")

    results = list(
        db.scalars(
            select(EvalResult)
            .where(EvalResult.eval_run_id == run_id)
            .order_by(EvalResult.created_at)
        )
    )
    questions_by_id = {
        question.id: question
        for question in db.scalars(
            select(EvalQuestion).where(
                EvalQuestion.id.in_({result.eval_question_id for result in results})
            )
        )
    }
    return [
        EvalResultResponse(
            id=result.id,
            eval_question_id=result.eval_question_id,
            question=questions_by_id[result.eval_question_id].question,
            category=result.category,
            iteration_count=result.iteration_count,
            latency_ms=result.latency_ms,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            estimated_cost_usd=result.estimated_cost_usd,
            generated_answer=result.generated_answer,
            faithfulness_score=result.faithfulness_score,
            answer_relevance_score=result.answer_relevance_score,
            context_precision_score=result.context_precision_score,
            context_recall_score=result.context_recall_score,
            metric_detail=result.metric_detail,
            retrieved_citations=result.retrieved_citations,
            error_message=result.error_message,
            created_at=result.created_at,
        )
        for result in results
    ]
