import time
from typing import Protocol

from google import genai
from google.genai import errors, types
from pydantic import ValidationError

from app.core.config import get_settings
from app.services.ontology import ChunkExtraction

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


class _GeminiExtractionClient:
    """Adapter around google.genai.Client: passes `ChunkExtraction` directly
    as `response_schema` (the SDK generates the JSON schema from the Pydantic
    model itself), so the model either produces a schema-conformant response
    or refuses — no free-text JSON parsing needed.

    Re-validates via `ChunkExtraction.model_validate_json(response.text)`
    ourselves rather than trusting the SDK's own `response.parsed` — that
    convenience field may be built through a path that skips our custom
    `model_validator` (the dangling-relation check), so this is the one place
    that guarantees it always runs. Never trust "guaranteed" structured
    output blindly, regardless of provider.
    """

    def __init__(self, api_key: str, model: str) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def extract(self, chunk_text: str) -> ChunkExtraction:
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=chunk_text,
                config=types.GenerateContentConfig(
                    system_instruction=_SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_schema=ChunkExtraction,
                ),
            )
        except errors.ClientError as exc:
            if exc.code == 429:
                raise ExtractionRateLimited(str(exc)) from exc
            raise

        return ChunkExtraction.model_validate_json(response.text)


def get_gemini_client() -> ExtractionClient:
    settings = get_settings()
    return _GeminiExtractionClient(
        api_key=settings.gemini_api_key, model=settings.gemini_extraction_model
    )


def extract_chunk_text(
    chunk_text: str, client: ExtractionClient | None = None
) -> ChunkExtraction:
    """Extracts entities/relations from one chunk's text.

    `client` defaults to the real Gemini-backed adapter; pass a fake
    `ExtractionClient` in tests to exercise the retry logic without a
    network call.

    Retries on rate limits (exponential backoff, same shape as
    `embedding.py`) and on schema-validation failure — the model's response
    didn't conform to `ChunkExtraction` even with a forced schema (rare, but
    output is stochastic, so a retry can succeed on a fresh sample).

    Gemini's free tier has both per-minute *and* per-day quotas — a 429 from
    a per-day quota being exhausted won't be fixed by retrying a few seconds
    later, and this correctly exhausts its retry budget and fails rather than
    retrying forever; that failure is the correct signal to wait or upgrade.
    """
    client = client or get_gemini_client()

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
