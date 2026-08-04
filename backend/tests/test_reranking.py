from app.services import reranking


class _FakeRerankClient:
    def __init__(self):
        self.calls: list[tuple[str, list[str], int]] = []

    def rerank(self, query, documents, top_n):
        self.calls.append((query, documents, top_n))
        return [
            reranking.RerankResult(index=i, relevance_score=1.0 - i * 0.1) for i in range(top_n)
        ]


def test_rerank_short_circuits_on_empty_documents():
    client = _FakeRerankClient()
    result = reranking.rerank("query", [], top_n=5, client=client)
    assert result == []
    assert client.calls == []  # never even reaches the client


def test_rerank_clamps_top_n_to_document_count():
    client = _FakeRerankClient()
    reranking.rerank("query", ["a", "b"], top_n=10, client=client)
    assert client.calls[0][2] == 2  # clamped from 10 down to len(documents)


def test_rerank_passes_through_client_results():
    client = _FakeRerankClient()
    results = reranking.rerank("query", ["a", "b", "c"], top_n=2, client=client)
    assert len(results) == 2
    assert results[0].index == 0
    assert results[1].index == 1
