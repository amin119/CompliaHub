"""Unit tests for Phase 7's pure run-aggregation/comparison logic — plain
fake objects (no DB, no ORM), matching this project's "test the pure logic
without the infra it normally runs against" pattern.
"""

import uuid
from dataclasses import dataclass, field

import pytest

from app.services import eval_aggregation


@dataclass
class _FakeResult:
    eval_question_id: uuid.UUID = field(default_factory=uuid.uuid4)
    faithfulness_score: float | None = None
    answer_relevance_score: float | None = None
    context_precision_score: float | None = None
    context_recall_score: float | None = None
    latency_ms: float | None = None
    estimated_cost_usd: float = 0.0
    error_message: str | None = None


@dataclass
class _FakeRun:
    avg_faithfulness: float | None = None
    avg_answer_relevance: float | None = None
    avg_context_precision: float | None = None
    avg_context_recall: float | None = None
    avg_latency_ms: float | None = None


def test_aggregate_run_averages_scored_rows():
    results = [
        _FakeResult(faithfulness_score=1.0, latency_ms=100.0, estimated_cost_usd=0.01),
        _FakeResult(faithfulness_score=0.5, latency_ms=200.0, estimated_cost_usd=0.02),
    ]
    aggregate = eval_aggregation.aggregate_run(results)
    assert aggregate.avg_faithfulness == 0.75
    assert aggregate.avg_latency_ms == 150.0
    assert aggregate.total_estimated_cost_usd == 0.03


def test_aggregate_run_excludes_errored_rows_from_score_averages():
    results = [
        _FakeResult(faithfulness_score=1.0, latency_ms=100.0, estimated_cost_usd=0.01),
        _FakeResult(error_message="judge failed", estimated_cost_usd=0.0),
    ]
    aggregate = eval_aggregation.aggregate_run(results)
    assert aggregate.avg_faithfulness == 1.0
    # The errored row's (zero) cost still counts toward the total.
    assert aggregate.total_estimated_cost_usd == 0.01


def test_aggregate_run_empty_results_is_all_none():
    aggregate = eval_aggregation.aggregate_run([])
    assert aggregate.avg_faithfulness is None
    assert aggregate.avg_latency_ms is None
    assert aggregate.total_estimated_cost_usd == 0.0


def test_compare_runs_computes_signed_delta():
    run_a = _FakeRun(avg_faithfulness=0.5, avg_latency_ms=100.0)
    run_b = _FakeRun(avg_faithfulness=0.8, avg_latency_ms=150.0)
    deltas = eval_aggregation.compare_runs(run_a, run_b)
    faithfulness_delta = next(d for d in deltas if d["metric"] == "faithfulness")
    assert faithfulness_delta["run_a"] == 0.5
    assert faithfulness_delta["run_b"] == 0.8
    assert faithfulness_delta["delta"] == pytest.approx(0.3)


def test_compare_runs_none_when_either_side_missing():
    run_a = _FakeRun(avg_faithfulness=None)
    run_b = _FakeRun(avg_faithfulness=0.8)
    deltas = eval_aggregation.compare_runs(run_a, run_b)
    faithfulness_delta = next(d for d in deltas if d["metric"] == "faithfulness")
    assert faithfulness_delta["delta"] is None


def test_find_regressed_questions_flags_drop_above_threshold():
    question_id = uuid.uuid4()
    results_a = [_FakeResult(eval_question_id=question_id, faithfulness_score=0.9)]
    results_b = [_FakeResult(eval_question_id=question_id, faithfulness_score=0.5)]

    regressed = eval_aggregation.find_regressed_questions(results_a, results_b)
    assert len(regressed) == 1
    assert regressed[0]["eval_question_id"] == question_id
    assert regressed[0]["metric"] == "faithfulness"
    assert regressed[0]["drop"] == pytest.approx(0.4)


def test_find_regressed_questions_ignores_small_drops():
    question_id = uuid.uuid4()
    results_a = [_FakeResult(eval_question_id=question_id, faithfulness_score=0.9)]
    results_b = [_FakeResult(eval_question_id=question_id, faithfulness_score=0.8)]

    regressed = eval_aggregation.find_regressed_questions(results_a, results_b)
    assert regressed == []


def test_find_regressed_questions_ignores_questions_missing_from_either_run():
    results_a = [_FakeResult(faithfulness_score=0.9)]
    results_b = [_FakeResult(faithfulness_score=0.1)]  # different eval_question_id
    assert eval_aggregation.find_regressed_questions(results_a, results_b) == []
