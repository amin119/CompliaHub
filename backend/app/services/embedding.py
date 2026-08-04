import time
from typing import Literal, Protocol

import voyageai
from voyageai.error import RateLimitError

from app.core.config import get_settings

# voyage-law-2's output dimensionality — fixed for the model, not something
# the API returns per-call. Used by vector_store.py to size the Qdrant
# collection. If voyage_model in Settings ever changes, this must change too.
EMBEDDING_DIM = 1024

# Voyage caps each embed() call at 128 texts, independent of token count.
_MAX_TEXTS_PER_BATCH = 128

# Voyage's docs quote free-tier limits of 3 requests/minute and 10K
# tokens/minute, but empirically (tested directly against this account) a
# single request over ~6-7K tokens already gets a 429 regardless of recent
# request history — the real enforced per-request cap is stricter than the
# advertised per-minute one. 4000 leaves real margin under the observed
# ~6234-tokens-ok / ~8791-tokens-fails boundary.
_MAX_TOKENS_PER_BATCH = 4000
_MIN_SECONDS_BETWEEN_REQUESTS = 21.0
_MAX_RETRIES = 5
_RETRY_BASE_DELAY_SECONDS = 5.0


class RateLimitExceeded(Exception):
    """Our own abstraction of "the embedding provider rate-limited us" — the
    retry logic below catches this, not a Voyage-specific exception type, so
    it doesn't depend on which provider is behind `EmbeddingClient`.
    """


class EmbeddingClient(Protocol):
    """The narrow interface this module actually needs, expressed in plain
    Python return shapes rather than a specific SDK's response objects. This
    is the seam that makes `embed_texts` testable with a fake client instead
    of only ever being exercisable via a real network call.
    """

    def embed(
        self, texts: list[str], model: str, input_type: str
    ) -> list[list[float]]: ...

    def count_tokens(self, texts: list[str], model: str) -> int: ...


class _VoyageEmbeddingClient:
    """Adapter around voyageai.Client: unwraps its response object to a plain
    list of vectors, and translates its RateLimitError into our own
    RateLimitExceeded — this is the one place that knows Voyage's SDK shape.
    """

    def __init__(self, api_key: str) -> None:
        self._client = voyageai.Client(api_key=api_key)

    def embed(self, texts: list[str], model: str, input_type: str) -> list[list[float]]:
        try:
            result = self._client.embed(texts, model=model, input_type=input_type)
        except RateLimitError as exc:
            raise RateLimitExceeded(str(exc)) from exc
        return result.embeddings

    def count_tokens(self, texts: list[str], model: str) -> int:
        return self._client.count_tokens(texts, model=model)


def get_voyage_client() -> EmbeddingClient:
    return _VoyageEmbeddingClient(api_key=get_settings().voyage_api_key)


def _token_aware_batches(client: EmbeddingClient, texts: list[str], model: str) -> list[list[str]]:
    """Groups texts so each batch stays under both the per-call text-count cap
    and an approximate per-minute token budget. `count_tokens` runs Voyage's
    tokenizer locally — it does not itself count against the API rate limit,
    so measuring before sending is free.
    """
    batches: list[list[str]] = []
    current_batch: list[str] = []
    current_tokens = 0

    for text in texts:
        text_tokens = client.count_tokens([text], model=model)
        batch_full = len(current_batch) >= _MAX_TEXTS_PER_BATCH
        over_token_budget = current_tokens + text_tokens > _MAX_TOKENS_PER_BATCH
        if current_batch and (batch_full or over_token_budget):
            batches.append(current_batch)
            current_batch = []
            current_tokens = 0
        current_batch.append(text)
        current_tokens += text_tokens

    if current_batch:
        batches.append(current_batch)
    return batches


def _embed_with_retry(
    client: EmbeddingClient, batch: list[str], model: str, input_type: str
) -> list[list[float]]:
    for attempt in range(_MAX_RETRIES):
        try:
            return client.embed(batch, model=model, input_type=input_type)
        except RateLimitExceeded:
            if attempt == _MAX_RETRIES - 1:
                raise
            # No Retry-After header is reliably present on Voyage's 429s, so
            # this backs off exponentially (5s, 10s, 20s, 40s) rather than
            # assuming a fixed cooldown.
            time.sleep(_RETRY_BASE_DELAY_SECONDS * (2**attempt))
    raise AssertionError("unreachable")  # loop always returns or raises above


def embed_texts(
    texts: list[str],
    input_type: Literal["document", "query"],
    client: EmbeddingClient | None = None,
) -> list[list[float]]:
    """Embed a list of texts with Voyage. `input_type` matters: Voyage's
    embed models are trained with distinct prompts for indexed documents vs.
    search queries, so passing the wrong one measurably hurts retrieval
    quality even though both return same-shaped vectors.

    Batches are token-aware and spaced out to respect the account's rate
    limits (see `_MAX_TOKENS_PER_BATCH` for the empirically-found per-request
    cap) — without this, embedding a real document's worth of chunks in one
    burst reliably trips a 429 on a non-billing account.

    `client` defaults to the real Voyage-backed adapter; pass a fake
    `EmbeddingClient` in tests to exercise the batching/retry logic without
    a network call.
    """
    if not texts:
        return []

    client = client or get_voyage_client()
    settings = get_settings()

    batches = _token_aware_batches(client, texts, settings.voyage_model)

    vectors: list[list[float]] = []
    last_request_at: float | None = None
    for batch in batches:
        if last_request_at is not None:
            elapsed = time.monotonic() - last_request_at
            remaining = _MIN_SECONDS_BETWEEN_REQUESTS - elapsed
            if remaining > 0:
                time.sleep(remaining)

        vectors.extend(_embed_with_retry(client, batch, settings.voyage_model, input_type))
        last_request_at = time.monotonic()

    return vectors
