"""Platform Phase 7: the Celery task that actually runs an eval pass —
async, not synchronous, because 30-50 questions x up to 4 judge calls each
(with agent-classified questions already confirmed to take ~19s+
individually, see docs/phase-5-agentic-loop.md) would very likely exceed
any reasonable HTTP timeout. Mirrors the existing async-job pattern already
used for document ingestion and repository scans.

This is the only new Celery task Phase 7 adds — see `celery_app.py`'s
`task_routes` for the one-time dual-restart note that comes with it.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.pricing import estimate_cost_usd
from app.models.evaluation import EvalQuestion, EvalResult, EvalRun
from app.services import eval_aggregation, eval_metrics, query_orchestration
from app.tasks.celery_app import celery_app


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _score_question(
    question: EvalQuestion, result: query_orchestration.OrchestrationResult
) -> dict:
    """Runs all 4 metrics for one question's real answer, returning the
    fields `run_evaluation_task` writes onto its `EvalResult` row. Raises on
    any judge failure — the caller catches this per-question, so one bad
    question never aborts the whole run.
    """
    answer = result.response.answer
    context_texts = result.context_texts

    faithfulness = eval_metrics.score_faithfulness(answer, context_texts)
    answer_relevance = eval_metrics.score_answer_relevance(question.question, answer)
    context_precision = eval_metrics.score_context_precision(question.question, context_texts)
    context_recall = eval_metrics.score_context_recall(question.ground_truth_answer, context_texts)

    return {
        "faithfulness_score": faithfulness.score,
        "answer_relevance_score": answer_relevance.score,
        "context_precision_score": context_precision.score,
        "context_recall_score": context_recall.score,
        "metric_detail": {
            "faithfulness": faithfulness.detail,
            "answer_relevance": answer_relevance.detail,
            "context_precision": context_precision.detail,
            "context_recall": context_recall.detail,
        },
    }


@celery_app.task(name="eval.run_evaluation")
def run_evaluation_task(eval_run_id: str, question_ids: list[str] | None = None) -> str:
    db = SessionLocal()
    try:
        eval_run = db.get(EvalRun, uuid.UUID(eval_run_id))
        if eval_run is None:
            return eval_run_id

        query = select(EvalQuestion)
        if question_ids:
            query = query.where(EvalQuestion.id.in_([uuid.UUID(qid) for qid in question_ids]))
        questions = list(db.scalars(query))

        for question in questions:
            row = EvalResult(eval_run_id=eval_run.id, eval_question_id=question.id)
            try:
                orchestration_result = query_orchestration.run_query(question.question, db)
                response = orchestration_result.response
                usage = orchestration_result.token_usage
                scores = _score_question(question, orchestration_result)

                row.category = response.category
                row.iteration_count = response.iteration_count
                row.latency_ms = response.latency_ms
                row.prompt_tokens = usage.prompt_tokens
                row.completion_tokens = usage.completion_tokens
                row.estimated_cost_usd = estimate_cost_usd(
                    usage.prompt_tokens, usage.completion_tokens
                )
                row.generated_answer = response.answer
                row.retrieved_citations = [
                    {
                        "chunk_id": str(citation.chunk_id),
                        "document_id": str(citation.document_id),
                        "document_filename": citation.document_filename,
                        "clause_number": citation.clause_number,
                    }
                    for citation in response.citations
                ]
                for field, value in scores.items():
                    setattr(row, field, value)
            except Exception as exc:
                # One bad question (a transient LLM failure, exhausted
                # retries, a malformed judge response) must not abort the
                # whole run — recorded here, every score column stays null.
                row.error_message = str(exc)

            db.add(row)
            db.commit()

        all_results = list(
            db.scalars(select(EvalResult).where(EvalResult.eval_run_id == eval_run.id))
        )
        aggregate = eval_aggregation.aggregate_run(all_results)
        eval_run.status = "completed"
        eval_run.question_count = len(questions)
        eval_run.avg_faithfulness = aggregate.avg_faithfulness
        eval_run.avg_answer_relevance = aggregate.avg_answer_relevance
        eval_run.avg_context_precision = aggregate.avg_context_precision
        eval_run.avg_context_recall = aggregate.avg_context_recall
        eval_run.avg_latency_ms = aggregate.avg_latency_ms
        eval_run.total_estimated_cost_usd = aggregate.total_estimated_cost_usd
        eval_run.finished_at = _now()
        db.commit()
    except Exception as exc:
        db.rollback()
        eval_run = db.get(EvalRun, uuid.UUID(eval_run_id))
        if eval_run is not None:
            eval_run.status = "failed"
            eval_run.error_message = str(exc)
            eval_run.finished_at = _now()
            db.commit()
        raise
    finally:
        db.close()

    return eval_run_id
