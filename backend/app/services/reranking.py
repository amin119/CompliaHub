from dataclasses import dataclass

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


def rerank(query: str, documents: list[str], top_n: int) -> list[RerankResult]:
    if not documents:
        return []

    settings = get_settings()
    client = cohere.ClientV2(api_key=settings.cohere_api_key)
    response = client.rerank(
        model=settings.cohere_rerank_model,
        query=query,
        documents=documents,
        top_n=min(top_n, len(documents)),
    )
    return [
        RerankResult(index=item.index, relevance_score=item.relevance_score)
        for item in response.results
    ]
