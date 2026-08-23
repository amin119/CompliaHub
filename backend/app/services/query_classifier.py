import time
from enum import Enum
from typing import Protocol

from google import genai
from google.genai import errors, types
from pydantic import BaseModel, ValidationError

from app.core.config import get_settings

_SYSTEM_PROMPT = (
    "You are routing a question about ISO 27001, ISO 42001, or GDPR "
    "compliance to the cheapest retrieval strategy that can actually "
    "answer it. Categories:\n"
    '- "vector": a simple factual lookup answerable from one or a few '
    "clauses directly (e.g. \"what does clause 6.1.2 require?\").\n"
    '- "graph": the question is about a *relationship* between specific '
    'named things — requirements, controls, risks, roles — where the '
    'answer depends on how they connect (e.g. "what controls mitigate '
    'this risk?", "what does this control require?").\n'
    '- "agent": the question is broad, thematic, comparative across '
    "standards, or requires multiple steps to answer confidently (e.g. "
    '"what does ISO 42001 require that ISO 27001 doesn\'t?", "summarize '
    'the main themes around risk management").\n'
    "Pick exactly one category — when unsure between vector and graph, "
    "prefer graph; when unsure between graph and agent, prefer agent, "
    "since agent mode can still fall back to a single retrieval pass."
)

_MAX_RETRIES = 3
_RETRY_BASE_DELAY_SECONDS = 2.0


class QueryCategory(str, Enum):
    VECTOR = "vector"
    GRAPH = "graph"
    AGENT = "agent"


class QueryClassification(BaseModel):
    """Which retrieval strategy this question needs."""

    category: QueryCategory


class ClassificationRateLimited(Exception):
    """Mirrors extraction.py's ExtractionRateLimited — covers both actual
    rate limiting and transient server-side unavailability, since both call
    for the same response: back off and retry.
    """


class ClassifierClient(Protocol):
    def classify(self, question: str) -> QueryClassification: ...


class _GeminiClassifierClient:
    """Same adapter shape as extraction.py/community_summary.py's Gemini
    adapters — forced schema, re-validated via `model_validate_json`
    rather than trusting `.parsed`. Deliberately not sharing code with
    those adapters despite the identical shape: different prompt/schema,
    no shared call site.
    """

    def __init__(self, api_key: str, model: str) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def classify(self, question: str) -> QueryClassification:
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=question,
                config=types.GenerateContentConfig(
                    system_instruction=_SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_schema=QueryClassification,
                ),
            )
        except errors.ClientError as exc:
            if exc.code == 429:
                raise ClassificationRateLimited(str(exc)) from exc
            raise
        except errors.ServerError as exc:
            raise ClassificationRateLimited(str(exc)) from exc

        return QueryClassification.model_validate_json(response.text)


def get_gemini_client() -> ClassifierClient:
    settings = get_settings()
    return _GeminiClassifierClient(
        api_key=settings.gemini_api_key, model=settings.gemini_extraction_model
    )


def classify_query(question: str, client: ClassifierClient | None = None) -> QueryClassification:
    """Classifies a question into the retrieval strategy that should handle
    it. `client` defaults to the real Gemini-backed adapter; pass a fake
    `ClassifierClient` in tests to exercise the retry logic without a
    network call.

    Retries on rate limits/transient server errors and on schema-validation
    failure, same shape as `extraction.extract_chunk_text`.
    """
    client = client or get_gemini_client()

    for attempt in range(_MAX_RETRIES):
        try:
            return client.classify(question)
        except ClassificationRateLimited:
            if attempt == _MAX_RETRIES - 1:
                raise
            time.sleep(_RETRY_BASE_DELAY_SECONDS * (2**attempt))
        except ValidationError:
            if attempt == _MAX_RETRIES - 1:
                raise
    raise AssertionError("unreachable")  # loop always returns or raises above
