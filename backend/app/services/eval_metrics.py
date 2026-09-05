"""Phase 7 (Evaluation Harness): custom Gemini-based LLM-judge metrics —
faithfulness, answer relevance, context precision, context recall — the
user's own resolved decision (via `AskUserQuestion`) over integrating the
`ragas` pip package, so this is hand-implemented against the exact same
methodologies RAGAS itself uses, not a black box.

Same Protocol + `@lru_cache`d client + retry-with-backoff shape as
`query_classifier.py` (mirrored again by the scanner's `finding_validation.py`/
`finding_remediation.py`) — `_sdk_client` is deliberately duplicated here
rather than imported from any of those, matching this project's own
established "different prompt/schema, no shared call site" precedent for
phase modules with the same adapter shape. `_call_with_retry` is a new,
small shared helper *within this module only* (this is the third+ copy of
that identical retry loop in the codebase — a legitimate case for the
codebase's own "extract on reuse" rule, applied narrowly rather than
retrofitted onto the other modules, to avoid unrelated churn).
"""

import math
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable, Protocol, TypeVar

from google import genai
from google.genai import errors, types
from pydantic import BaseModel, ValidationError

from app.core.config import get_settings
from app.services import embedding, token_tracking

_MAX_RETRIES = 3
_RETRY_BASE_DELAY_SECONDS = 2.0

T = TypeVar("T")


@dataclass
class MetricResult:
    """`detail` always carries the judge's raw claims/verdicts — never trust
    a bare float, same discipline `finding_validation.py`'s `rationale`
    field established: a low score should be readable, not just believed.
    """

    score: float
    detail: dict


class ClaimVerdict(BaseModel):
    claim: str
    supported: bool


class ClaimJudgment(BaseModel):
    claims: list[ClaimVerdict]


class GeneratedQuestions(BaseModel):
    questions: list[str]  # exactly 3, per the system prompt


class ChunkRelevanceVerdicts(BaseModel):
    relevant: list[bool]  # same order/length as the context chunks given


class EvalRateLimited(Exception):
    """Mirrors query_classifier.ClassificationRateLimited — covers both
    actual rate limiting and transient server-side unavailability."""


class EvalJudgeClient(Protocol):
    def decompose_and_judge_claims(self, text: str, context: str) -> ClaimJudgment: ...

    def generate_hypothetical_questions(self, answer: str) -> GeneratedQuestions: ...

    def judge_chunk_relevance(
        self, question: str, context_texts: list[str]
    ) -> ChunkRelevanceVerdicts: ...


@lru_cache
def _sdk_client(api_key: str) -> genai.Client:
    return genai.Client(api_key=api_key)


_CLAIMS_SYSTEM_PROMPT = (
    "Decompose the given TEXT into a list of atomic, independently-checkable "
    "factual claims — one discrete assertion per claim, splitting compound "
    "sentences apart. For each claim, judge whether it is directly supported "
    "by the CONTEXT provided: supported=true only if the context actually "
    "states or clearly implies it; supported=false if the context is silent "
    "on it, contradicts it, or is only tangentially related. Be strict — do "
    "not mark a claim supported just because it sounds plausible."
)

_HYPOTHETICAL_QUESTIONS_SYSTEM_PROMPT = (
    "Given only an ANSWER (you are not told what question prompted it), "
    "write exactly 3 different questions this answer, taken on its own, "
    "would be a good direct response to. Infer purely from what the answer "
    "itself says — do not invent context beyond it."
)

_CHUNK_RELEVANCE_SYSTEM_PROMPT = (
    "You will be given a QUESTION and a numbered list of retrieved CONTEXT "
    "chunks, in their original rank order. For each chunk, in that exact "
    "order, judge whether it is actually relevant to answering the "
    "question: true only if the chunk meaningfully helps answer it, false "
    "if it is off-topic or only superficially related. Return exactly one "
    "boolean per chunk, in the same order they were given."
)


class _GeminiEvalJudgeClient:
    """Adapter around `google-genai`, narrowed to the three structured calls
    this module needs. Deliberately not sharing code with query_classifier's/
    finding_validation's adapters despite the identical shape: different
    prompts/schemas, no shared call site.
    """

    def __init__(self, api_key: str, model: str) -> None:
        self._client = _sdk_client(api_key)
        self._model = model

    def _generate(self, system_prompt: str, contents: str, schema: type[BaseModel]) -> BaseModel:
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                    response_schema=schema,
                ),
            )
        except errors.ClientError as exc:
            if exc.code == 429:
                raise EvalRateLimited(str(exc)) from exc
            raise
        except errors.ServerError as exc:
            raise EvalRateLimited(str(exc)) from exc

        token_tracking.record(response.usage_metadata)
        # Re-validate ourselves rather than trusting response.parsed — same
        # reasoning as every other Gemini adapter in this project.
        return schema.model_validate_json(response.text)

    def decompose_and_judge_claims(self, text: str, context: str) -> ClaimJudgment:
        contents = f"TEXT:\n{text}\n\nCONTEXT:\n{context}"
        result = self._generate(_CLAIMS_SYSTEM_PROMPT, contents, ClaimJudgment)
        assert isinstance(result, ClaimJudgment)
        return result

    def generate_hypothetical_questions(self, answer: str) -> GeneratedQuestions:
        result = self._generate(
            _HYPOTHETICAL_QUESTIONS_SYSTEM_PROMPT, f"ANSWER:\n{answer}", GeneratedQuestions
        )
        assert isinstance(result, GeneratedQuestions)
        return result

    def judge_chunk_relevance(
        self, question: str, context_texts: list[str]
    ) -> ChunkRelevanceVerdicts:
        numbered = "\n\n".join(f"[{i}] {text}" for i, text in enumerate(context_texts, start=1))
        contents = f"QUESTION:\n{question}\n\nCONTEXT CHUNKS:\n{numbered}"
        result = self._generate(_CHUNK_RELEVANCE_SYSTEM_PROMPT, contents, ChunkRelevanceVerdicts)
        assert isinstance(result, ChunkRelevanceVerdicts)
        return result


def get_gemini_judge_client() -> EvalJudgeClient:
    settings = get_settings()
    return _GeminiEvalJudgeClient(api_key=settings.gemini_api_key, model=settings.gemini_eval_model)


def _call_with_retry(fn: Callable[[], T]) -> T:
    """Shared retry loop for every metric below — same shape as
    `query_classifier.classify_query`'s, extracted here since this module
    alone calls it four times.
    """
    for attempt in range(_MAX_RETRIES):
        try:
            return fn()
        except EvalRateLimited:
            if attempt == _MAX_RETRIES - 1:
                raise
            time.sleep(_RETRY_BASE_DELAY_SECONDS * (2**attempt))
        except ValidationError:
            if attempt == _MAX_RETRIES - 1:
                raise
    raise AssertionError("unreachable")  # loop always returns or raises above


def score_faithfulness(
    answer: str, context_texts: list[str], client: EvalJudgeClient | None = None
) -> MetricResult:
    """Faithfulness: decomposes the *generated answer* into atomic claims,
    judges each against the retrieved context in the same call. Score =
    supported claims / total claims (0.0 if the answer yields zero claims —
    an empty/refusal answer is not vacuously "faithful").
    """
    client = client or get_gemini_judge_client()
    context = "\n\n".join(context_texts)
    judgment = _call_with_retry(lambda: client.decompose_and_judge_claims(answer, context))

    total = len(judgment.claims)
    if total == 0:
        return MetricResult(score=0.0, detail={"claims": []})
    supported = sum(1 for claim in judgment.claims if claim.supported)
    return MetricResult(
        score=supported / total,
        detail={"claims": [claim.model_dump() for claim in judgment.claims]},
    )


def score_context_recall(
    ground_truth_answer: str, context_texts: list[str], client: EvalJudgeClient | None = None
) -> MetricResult:
    """Context recall: how much of the *ground-truth* answer is attributable
    to the retrieved context — the same claim-decomposition-and-judge
    mechanism as `score_faithfulness`, applied to the ground truth instead of
    the model's own generated answer. A low score here means retrieval, not
    the answer model, is where quality is being lost for this question.
    """
    return score_faithfulness(ground_truth_answer, context_texts, client=client)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def score_answer_relevance(
    question: str,
    answer: str,
    client: EvalJudgeClient | None = None,
    embed_fn: Callable[..., list[list[float]]] | None = None,
) -> MetricResult:
    """Answer relevance: generates 3 hypothetical questions the *answer
    alone* would address (without showing the model the real question, to
    avoid leaking it), embeds them via the existing `embedding.embed_texts`
    (reused, not reimplemented), and averages cosine similarity against the
    real question's own embedding — RAGAS's actual method. A low-relevance,
    rambling, or off-topic answer produces hypothetical questions that drift
    from what was actually asked.
    """
    client = client or get_gemini_judge_client()
    embed_fn = embed_fn or embedding.embed_texts

    generated = _call_with_retry(lambda: client.generate_hypothetical_questions(answer))
    hypothetical_questions = generated.questions
    if not hypothetical_questions:
        return MetricResult(score=0.0, detail={"hypothetical_questions": []})

    vectors = embed_fn([question, *hypothetical_questions], input_type="query")
    question_vector, hypothetical_vectors = vectors[0], vectors[1:]

    similarities = [_cosine_similarity(question_vector, v) for v in hypothetical_vectors]
    return MetricResult(
        score=sum(similarities) / len(similarities),
        detail={"hypothetical_questions": hypothetical_questions, "similarities": similarities},
    )


def score_context_precision(
    question: str, context_texts: list[str], client: EvalJudgeClient | None = None
) -> MetricResult:
    """Context precision: judges every retrieved chunk (in rank order) as
    relevant/not, then computes RAGAS's actual weighted-average-precision
    formula — `sum(precision@k * relevant_k) / total_relevant` — so a
    relevant chunk ranked higher contributes more than one buried lower down.
    Score is 0.0 if there's no context, or if the judge found nothing
    relevant in it.
    """
    if not context_texts:
        return MetricResult(score=0.0, detail={"relevant": []})

    client = client or get_gemini_judge_client()
    verdicts = _call_with_retry(lambda: client.judge_chunk_relevance(question, context_texts))
    relevant = list(verdicts.relevant)

    # The judge is asked for exactly len(context_texts) booleans in order,
    # but structured-output length isn't schema-enforced — pad/truncate
    # defensively rather than let a mismatched zip silently misalign ranks.
    if len(relevant) < len(context_texts):
        relevant = relevant + [False] * (len(context_texts) - len(relevant))
    elif len(relevant) > len(context_texts):
        relevant = relevant[: len(context_texts)]

    total_relevant = sum(relevant)
    if total_relevant == 0:
        return MetricResult(score=0.0, detail={"relevant": relevant})

    relevant_so_far = 0
    precisions_at_k = []
    for k, is_relevant in enumerate(relevant, start=1):
        if is_relevant:
            relevant_so_far += 1
            precisions_at_k.append(relevant_so_far / k)

    return MetricResult(score=sum(precisions_at_k) / total_relevant, detail={"relevant": relevant})
