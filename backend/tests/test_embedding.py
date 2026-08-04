import pytest

from app.services import embedding


class _FakeEmbeddingClient:
    """A fake `EmbeddingClient` — this is the whole point of the DIP fix:
    `embed_texts`'s batching/retry logic can now be exercised without any
    real Voyage account or network call.
    """

    def __init__(self, fail_times: int = 0, tokens_per_text: int = 100):
        self.fail_times = fail_times
        self.tokens_per_text = tokens_per_text
        self.calls = 0

    def embed(self, texts, model, input_type):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise embedding.RateLimitExceeded("simulated rate limit")
        return [[0.1, 0.2, 0.3] for _ in texts]

    def count_tokens(self, texts, model):
        return sum(self.tokens_per_text for _ in texts)


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch):
    """Every test here simulates retries/spacing that would otherwise take
    tens of seconds of real wall-clock time — this makes them instant.
    """
    monkeypatch.setattr(embedding.time, "sleep", lambda seconds: None)


def test_embed_texts_retries_until_success():
    client = _FakeEmbeddingClient(fail_times=2)
    vectors = embedding.embed_texts(["hello"], input_type="document", client=client)
    assert len(vectors) == 1
    assert client.calls == 3


def test_embed_texts_raises_after_exhausting_retries():
    client = _FakeEmbeddingClient(fail_times=999)
    with pytest.raises(embedding.RateLimitExceeded):
        embedding.embed_texts(["hello"], input_type="document", client=client)
    assert client.calls == embedding._MAX_RETRIES


def test_token_aware_batches_respects_token_budget():
    client = _FakeEmbeddingClient(tokens_per_text=1000)
    texts = ["text"] * 10  # 10,000 tokens total; 4,000-token cap -> batches of 4/4/2
    batches = embedding._token_aware_batches(client, texts, model="voyage-law-2")
    assert [len(b) for b in batches] == [4, 4, 2]


def test_token_aware_batches_respects_text_count_cap():
    client = _FakeEmbeddingClient(tokens_per_text=1)  # tokens are negligible; count cap binds
    texts = ["t"] * 200
    batches = embedding._token_aware_batches(client, texts, model="voyage-law-2")
    assert [len(b) for b in batches] == [128, 72]


def test_embed_texts_spaces_out_requests_between_batches(monkeypatch):
    sleep_calls = []
    monkeypatch.setattr(embedding.time, "sleep", lambda seconds: sleep_calls.append(seconds))
    client = _FakeEmbeddingClient(tokens_per_text=1000)
    texts = ["text"] * 5  # 5,000 tokens -> 2 batches (4,000 cap): [4, 1]

    embedding.embed_texts(texts, input_type="document", client=client)

    assert len(sleep_calls) == 1  # one gap between the two batches
    assert sleep_calls[0] > 15  # close to _MIN_SECONDS_BETWEEN_REQUESTS (21s)
