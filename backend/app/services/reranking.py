from dataclasses import dataclass
from typing import Protocol

import cohere

from app.core.config import get_settings


@dataclass
class RerankResult:
    """`index` is the position of this document in the *input* list passed
    to `rerank()` — the caller uses it to map back to its own chunk objects,
    since Cohere returns documents reordered by relevance, not by index.
    """

    index: int
    relevance_score: float


class RerankClient(Protocol):
    def rerank(self, query: str, documents: list[str], top_n: int) -> list[RerankResult]: ...


class _CohereRerankClient:
    """Adapter around cohere.ClientV2: unwraps its response object to a plain
    list of RerankResult — this is the one place that knows Cohere's SDK shape.
    """

    def __init__(self, api_key: str, model: str) -> None:
        self._client = cohere.ClientV2(api_key=api_key)
        self._model = model

    def rerank(self, query: str, documents: list[str], top_n: int) -> list[RerankResult]:
        response = self._client.rerank(
            model=self._model, query=query, documents=documents, top_n=top_n
        )
        return [
            RerankResult(index=item.index, relevance_score=item.relevance_score)
            for item in response.results
        ]


def get_cohere_client() -> RerankClient:
    settings = get_settings()
    return _CohereRerankClient(api_key=settings.cohere_api_key, model=settings.cohere_rerank_model)


def rerank(
    query: str, documents: list[str], top_n: int, client: RerankClient | None = None
) -> list[RerankResult]:
    """`client` defaults to the real Cohere-backed adapter; pass a fake
    `RerankClient` in tests to exercise the empty-input/top_n-clamping logic
    without a network call.
    """
    if not documents:
        return []

    client = client or get_cohere_client()
    return client.rerank(query, documents, min(top_n, len(documents)))
