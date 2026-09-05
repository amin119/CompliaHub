"""Phase 7: pure aggregation/comparison logic for eval runs — no DB, no
LLM calls, operates on any object exposing the right attributes (real
`EvalResult` ORM rows or plain fakes in tests), matching this project's
"test the pure logic without the infra it normally runs against" pattern.
"""

from dataclasses import dataclass

_SCORE_FIELDS = (
    "faithfulness_score",
    "answer_relevance_score",
    "context_precision_score",
    "context_recall_score",
)

# How much an individual question's score may drop between two runs before
# it's flagged as a regression — an empirical starting point, same
# "tune against real use" spirit as every other constant like this in this
# project (e.g. agent.py's DEFAULT_MAX_ITERATIONS).
REGRESSION_THRESHOLD = 0.15


def _avg(values: list[float]) -> float | None:
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


@dataclass
class RunAggregate:
    avg_faithfulness: float | None
    avg_answer_relevance: float | None
    avg_context_precision: float | None
    avg_context_recall: float | None
    avg_latency_ms: float | None
    total_estimated_cost_usd: float


def aggregate_run(results: list) -> RunAggregate:
    """Computes one run's rollup fields from its per-question result rows.
    Rows with `error_message` set never got scored — excluded from every
    score/latency average, but their (zero) cost still counts toward the
    total, same as a successfully-scored row's.
    """
    scored = [r for r in results if r.error_message is None]
    return RunAggregate(
        avg_faithfulness=_avg([r.faithfulness_score for r in scored]),
        avg_answer_relevance=_avg([r.answer_relevance_score for r in scored]),
        avg_context_precision=_avg([r.context_precision_score for r in scored]),
        avg_context_recall=_avg([r.context_recall_score for r in scored]),
        avg_latency_ms=_avg([r.latency_ms for r in scored]),
        total_estimated_cost_usd=sum(r.estimated_cost_usd or 0.0 for r in results),
    )


def compare_runs(run_a, run_b) -> list[dict]:
    """`run_a`/`run_b` are two `EvalRun`-shaped objects (or fakes) already
    carrying their own `avg_*` fields — this just computes the per-metric
    delta (`run_b - run_a`), it doesn't re-aggregate from raw results (see
    `EvalRun`'s own docstring for why those are denormalized rollups).
    """
    metric_names = [
        "faithfulness",
        "answer_relevance",
        "context_precision",
        "context_recall",
        "latency_ms",
    ]
    field_names = [f"avg_{name}" for name in metric_names[:-1]] + ["avg_latency_ms"]
    deltas = []
    for metric, field in zip(metric_names, field_names):
        a_value = getattr(run_a, field)
        b_value = getattr(run_b, field)
        delta = (b_value - a_value) if (a_value is not None and b_value is not None) else None
        deltas.append({"metric": metric, "run_a": a_value, "run_b": b_value, "delta": delta})
    return deltas


def find_regressed_questions(
    run_a_results: list, run_b_results: list, threshold: float = REGRESSION_THRESHOLD
) -> list[dict]:
    """Questions present in both runs whose score dropped by more than
    `threshold` on any of the 4 metrics — a comparison capability, not a
    pass/fail gate (no CI-wired regression gating is in scope for this
    phase, see docs/phase-7-evaluation.md's "explicitly out of scope").
    """
    by_question_a = {r.eval_question_id: r for r in run_a_results}
    by_question_b = {r.eval_question_id: r for r in run_b_results}
    shared_ids = set(by_question_a) & set(by_question_b)

    regressed = []
    for question_id in shared_ids:
        result_a, result_b = by_question_a[question_id], by_question_b[question_id]
        for field in _SCORE_FIELDS:
            score_a, score_b = getattr(result_a, field), getattr(result_b, field)
            if score_a is None or score_b is None:
                continue
            drop = score_a - score_b
            if drop > threshold:
                regressed.append(
                    {
                        "eval_question_id": question_id,
                        "metric": field.removesuffix("_score"),
                        "run_a_score": score_a,
                        "run_b_score": score_b,
                        "drop": drop,
                    }
                )
    return regressed
