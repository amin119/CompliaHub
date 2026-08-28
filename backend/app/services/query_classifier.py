import time
from enum import Enum
from functools import lru_cache
from typing import Protocol

from google import genai
from google.genai import errors, types
from pydantic import BaseModel, Field, ValidationError

from app.core.config import get_settings

_SYSTEM_PROMPT = (
    "You are routing a question to the cheapest retrieval strategy that can "
    "actually answer it. Categories:\n"
    '- "off_topic": the question is a greeting, small talk, or is about '
    'anything other than ISO 27001, ISO 42001, or GDPR compliance (e.g. '
    '"hi, how are you?", "what\'s the weather?", "write me a poem"). Use '
    "this whenever the question isn't a compliance question at all — not "
    "just when you're unsure which *retrieval strategy* fits a compliance "
    "question (that's what the tie-breaking rule below is for).\n"
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
    "since agent mode can still fall back to a single retrieval pass. Only "
    'use "off_topic" when the question plainly isn\'t about compliance — '
    "never as a fallback for a compliance question you're just unsure "
    "how to route.\n\n"
    'When (and only when) category is "off_topic", also write `reply`: a '
    "short, warm, natural response that actually acknowledges what the "
    "user said (answer a greeting like a greeting, decline a request like "
    '"write me a poem" gracefully, etc.) before inviting them to ask about '
    "ISO 27001, ISO 42001, or GDPR instead. Vary your wording — never reuse "
    "the same stock sentence for every off-topic message. Leave `reply` "
    "null for every other category."
)

_MAX_RETRIES = 3
_RETRY_BASE_DELAY_SECONDS = 2.0


class QueryCategory(str, Enum):
    OFF_TOPIC = "off_topic"
    VECTOR = "vector"
    GRAPH = "graph"
    AGENT = "agent"


class QueryClassification(BaseModel):
    """Which retrieval strategy this question needs."""

    category: QueryCategory
    # Generated in the same call as the category itself — not a second LLM
    # round-trip — so an off-topic reply costs nothing extra over just
    # classifying it, while still being a real, varied response to what the
    # user actually said instead of one hardcoded sentence every time. Only
    # meaningful when category is OFF_TOPIC; routes fall back to a fixed
    # default if the model leaves this empty.
    reply: str | None = Field(
        default=None,
        description=(
            "Only when category is off_topic: a short, warm, varied reply "
            "to what the user actually said, then inviting them to ask "
            "about ISO 27001/42001/GDPR. Null for every other category."
        ),
    )


class ClassificationRateLimited(Exception):
    """Mirrors extraction.py's ExtractionRateLimited — covers both actual
    rate limiting and transient server-side unavailability, since both call
    for the same response: back off and retry.
    """


class ClassifierClient(Protocol):
    def classify(self, question: str) -> QueryClassification: ...


# Latency fix (post-Phase 6): measured `genai.Client(api_key=...)`
# construction alone at ~1s, *every single call* — every classifier call
# used to pay this even though nothing about the client actually changes
# between requests (same api_key for the process's whole lifetime, same as
# `get_settings()`'s own `lru_cache` reasoning). Cached here, keyed by
# api_key so it still rebuilds if the key ever legitimately changes, rather
# than made a bare module-level global.
@lru_cache
def _sdk_client(api_key: str) -> genai.Client:
    return genai.Client(api_key=api_key)


class _GeminiClassifierClient:
    """Same adapter shape as extraction.py/community_summary.py's Gemini
    adapters — forced schema, re-validated via `model_validate_json`
    rather than trusting `.parsed`. Deliberately not sharing code with
    those adapters despite the identical shape: different prompt/schema,
    no shared call site.
    """

    def __init__(self, api_key: str, model: str) -> None:
        self._client = _sdk_client(api_key)
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
                    # Classifying into one of four fixed labels needs zero
                    # reasoning depth — "thinking" only adds latency here,
                    # measured live to shave ~0.5-1s off an otherwise
                    # multi-second call for no quality gain on this task.
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
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
