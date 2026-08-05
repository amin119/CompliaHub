import time
from typing import Protocol

import anthropic
from pydantic import ValidationError

from app.core.config import get_settings
from app.services.ontology import ChunkExtraction

_TOOL_NAME = "record_extraction"

_SYSTEM_PROMPT = (
    "You are extracting entities and relations from one clause of a "
    "compliance standard (ISO 27001, ISO 42001, or GDPR) for a knowledge "
    "graph. Only extract entities and relations that are actually stated or "
    "clearly implied in the text — do not invent facts. Every relation's "
    "source and target must also appear in your own entities list. If the "
    "text doesn't contain a clear entity or relation, return empty lists "
    "rather than guessing."
)

_MAX_RETRIES = 3
_RETRY_BASE_DELAY_SECONDS = 2.0


class ExtractionRateLimited(Exception):
    """Our own abstraction of "the extraction provider rate-limited us" —
    mirrors embedding.py's RateLimitExceeded, so the retry logic below
    doesn't depend on which provider is behind ExtractionClient.
    """


class ExtractionClient(Protocol):
    def extract(self, chunk_text: str) -> ChunkExtraction: ...


class _AnthropicExtractionClient:
    """Adapter around anthropic.Anthropic: forces a single tool call whose
    input_schema *is* ChunkExtraction's JSON schema, so the model either
    produces a schema-conformant call or refuses — no free-text JSON parsing
    needed. The result is still validated with Pydantic afterward as the
    safety net; never trust "guaranteed" structured output blindly.
    """

    def __init__(self, api_key: str, model: str) -> None:
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def extract(self, chunk_text: str) -> ChunkExtraction:
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=2048,
                system=_SYSTEM_PROMPT,
                tools=[
                    {
                        "name": _TOOL_NAME,
                        "description": (
                            "Record the entities and relations found in this chunk."
                        ),
                        "input_schema": ChunkExtraction.model_json_schema(),
                    }
                ],
                tool_choice={"type": "tool", "name": _TOOL_NAME},
                messages=[{"role": "user", "content": chunk_text}],
            )
        except anthropic.RateLimitError as exc:
            raise ExtractionRateLimited(str(exc)) from exc

        tool_use = next(block for block in response.content if block.type == "tool_use")
        return ChunkExtraction.model_validate(tool_use.input)


def get_anthropic_client() -> ExtractionClient:
    settings = get_settings()
    return _AnthropicExtractionClient(
        api_key=settings.anthropic_api_key, model=settings.anthropic_extraction_model
    )


def extract_chunk_text(
    chunk_text: str, client: ExtractionClient | None = None
) -> ChunkExtraction:
    """Extracts entities/relations from one chunk's text.

    `client` defaults to the real Anthropic-backed adapter; pass a fake
    `ExtractionClient` in tests to exercise the retry logic without a
    network call.

    Retries on rate limits (exponential backoff, same shape as
    `embedding.py`) and on schema-validation failure — the model's tool call
    didn't conform to `ChunkExtraction` even with a forced schema (rare, but
    output is stochastic, so a retry can succeed on a fresh sample).
    """
    client = client or get_anthropic_client()

    for attempt in range(_MAX_RETRIES):
        try:
            return client.extract(chunk_text)
        except ExtractionRateLimited:
            if attempt == _MAX_RETRIES - 1:
                raise
            time.sleep(_RETRY_BASE_DELAY_SECONDS * (2**attempt))
        except ValidationError:
            if attempt == _MAX_RETRIES - 1:
                raise
    raise AssertionError("unreachable")  # loop always returns or raises above
