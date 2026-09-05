"""Unit tests for Phase 7's custom LLM-judge metrics — fake `EvalJudgeClient`
implementations (same DI pattern `query_classifier.py`'s own tests use), no
network calls. Each test asserts an exact, hand-computed expected score.
"""

import pytest
from pydantic import BaseModel, ValidationError

from app.services import eval_metrics
from app.services.eval_metrics import (
    ChunkRelevanceVerdicts,
    ClaimJudgment,
    ClaimVerdict,
    EvalRateLimited,
    GeneratedQuestions,
)


class _FakeJudgeClient:
    def __init__(self, claims=None, questions=None, relevant=None):
        self._claims = claims or []
        self._questions = questions or []
        self._relevant = relevant or []

    def decompose_and_judge_claims(self, text, context):
        return ClaimJudgment(claims=self._claims)

    def generate_hypothetical_questions(self, answer):
        return GeneratedQuestions(questions=self._questions)

    def judge_chunk_relevance(self, question, context_texts):
        return ChunkRelevanceVerdicts(relevant=self._relevant)


def test_faithfulness_scores_supported_fraction():
    client = _FakeJudgeClient(
        claims=[
            ClaimVerdict(claim="a", supported=True),
            ClaimVerdict(claim="b", supported=True),
            ClaimVerdict(claim="c", supported=False),
            ClaimVerdict(claim="d", supported=False),
        ]
    )
    result = eval_metrics.score_faithfulness("answer text", ["context"], client=client)
    assert result.score == 0.5
    assert len(result.detail["claims"]) == 4


def test_faithfulness_zero_claims_scores_zero_not_vacuously_perfect():
    client = _FakeJudgeClient(claims=[])
    result = eval_metrics.score_faithfulness("", ["context"], client=client)
    assert result.score == 0.0


def test_faithfulness_all_supported_scores_one():
    client = _FakeJudgeClient(claims=[ClaimVerdict(claim="a", supported=True)])
    result = eval_metrics.score_faithfulness("answer", ["context"], client=client)
    assert result.score == 1.0


def test_context_recall_delegates_to_faithfulness_shape():
    # Same claim-decomposition-and-judge mechanism, applied to the ground
    # truth answer instead of the model's generated answer.
    client = _FakeJudgeClient(
        claims=[
            ClaimVerdict(claim="a", supported=True),
            ClaimVerdict(claim="b", supported=False),
        ]
    )
    result = eval_metrics.score_context_recall("ground truth text", ["context"], client=client)
    assert result.score == 0.5


def _fake_embed_fn(vectors_by_text):
    def embed(texts, input_type):
        return [vectors_by_text[text] for text in texts]

    return embed


def test_answer_relevance_averages_cosine_similarity():
    client = _FakeJudgeClient(questions=["q1", "q2"])
    embed_fn = _fake_embed_fn(
        {
            "real question": [1.0, 0.0],
            "q1": [1.0, 0.0],  # identical direction -> similarity 1.0
            "q2": [0.0, 1.0],  # orthogonal -> similarity 0.0
        }
    )
    result = eval_metrics.score_answer_relevance(
        "real question", "some answer", client=client, embed_fn=embed_fn
    )
    assert result.score == pytest.approx(0.5)
    assert result.detail["hypothetical_questions"] == ["q1", "q2"]


def test_answer_relevance_zero_hypothetical_questions_scores_zero():
    client = _FakeJudgeClient(questions=[])
    result = eval_metrics.score_answer_relevance(
        "q", "a", client=client, embed_fn=_fake_embed_fn({})
    )
    assert result.score == 0.0


def test_context_precision_weighted_average_precision_formula():
    # Ranked [relevant, not relevant, relevant] -> AP = (1/1 + 2/3) / 2
    client = _FakeJudgeClient(relevant=[True, False, True])
    result = eval_metrics.score_context_precision(
        "question", ["chunk1", "chunk2", "chunk3"], client=client
    )
    expected = (1 / 1 + 2 / 3) / 2
    assert result.score == pytest.approx(expected)


def test_context_precision_no_relevant_chunks_scores_zero():
    client = _FakeJudgeClient(relevant=[False, False])
    result = eval_metrics.score_context_precision("q", ["c1", "c2"], client=client)
    assert result.score == 0.0


def test_context_precision_empty_context_scores_zero_without_calling_client():
    class _ExplodingClient:
        def judge_chunk_relevance(self, question, context_texts):
            raise AssertionError("must not be called with empty context")

    result = eval_metrics.score_context_precision("q", [], client=_ExplodingClient())
    assert result.score == 0.0


def test_context_precision_pads_short_judge_response():
    # Judge returned fewer booleans than chunks given — must not raise or
    # silently misalign via zip; padded with False for the missing ranks.
    client = _FakeJudgeClient(relevant=[True])
    result = eval_metrics.score_context_precision("q", ["c1", "c2", "c3"], client=client)
    assert result.detail["relevant"] == [True, False, False]
    assert result.score == pytest.approx(1.0)


def test_context_precision_truncates_long_judge_response():
    client = _FakeJudgeClient(relevant=[True, True, True, True])
    result = eval_metrics.score_context_precision("q", ["c1", "c2"], client=client)
    assert result.detail["relevant"] == [True, True]


def test_call_with_retry_retries_on_rate_limit_then_succeeds():
    attempts = {"count": 0}

    def flaky():
        attempts["count"] += 1
        if attempts["count"] < 2:
            raise EvalRateLimited("rate limited")
        return "ok"

    assert eval_metrics._call_with_retry(flaky) == "ok"
    assert attempts["count"] == 2


def test_call_with_retry_raises_after_exhausting_retries():
    def always_fails():
        raise EvalRateLimited("still limited")

    with pytest.raises(EvalRateLimited):
        eval_metrics._call_with_retry(always_fails)


class _StrictModel(BaseModel):
    x: int


def test_call_with_retry_retries_on_validation_error():
    attempts = {"count": 0}

    def flaky():
        attempts["count"] += 1
        if attempts["count"] < 2:
            try:
                _StrictModel.model_validate({"x": "not-a-number"})
            except ValidationError:
                raise
        return "ok"

    assert eval_metrics._call_with_retry(flaky) == "ok"
    assert attempts["count"] == 2
