import pytest
from pydantic import ValidationError

from app.services import extraction
from app.services.ontology import ChunkExtraction, EntityType, ExtractedEntity


class _FakeExtractionClient:
    """A fake `ExtractionClient` — exercises `extract_chunk_text`'s retry
    logic without any real Anthropic account or network call.
    """

    def __init__(self, fail_times: int = 0, result: ChunkExtraction | None = None):
        self.fail_times = fail_times
        self.result = result or ChunkExtraction()
        self.calls = 0

    def extract(self, chunk_text: str) -> ChunkExtraction:
        self.calls += 1
        if self.calls <= self.fail_times:
            raise extraction.ExtractionRateLimited("simulated rate limit")
        return self.result


class _AlwaysInvalidClient:
    """Stands in for a malformed tool-use response — every call raises
    Pydantic's ValidationError, same as the real adapter would if the model's
    output somehow didn't conform to `ChunkExtraction`.
    """

    def __init__(self) -> None:
        self.calls = 0

    def extract(self, chunk_text: str) -> ChunkExtraction:
        self.calls += 1
        return ChunkExtraction.model_validate({"entities": [{"name": "x"}]})


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch):
    monkeypatch.setattr(extraction.time, "sleep", lambda seconds: None)


def test_extract_chunk_text_retries_until_success():
    expected = ChunkExtraction(
        entities=[ExtractedEntity(name="X", entity_type=EntityType.CONTROL)]
    )
    client = _FakeExtractionClient(fail_times=2, result=expected)

    result = extraction.extract_chunk_text("some chunk text", client=client)

    assert result == expected
    assert client.calls == 3


def test_extract_chunk_text_raises_after_exhausting_retries():
    client = _FakeExtractionClient(fail_times=999)

    with pytest.raises(extraction.ExtractionRateLimited):
        extraction.extract_chunk_text("some chunk text", client=client)

    assert client.calls == extraction._MAX_RETRIES


def test_extract_chunk_text_retries_on_validation_error_too():
    """Not just rate limits — a response that fails Pydantic validation
    (missing required `entity_type`) should also be retried, since output is
    stochastic and a fresh sample can succeed.
    """
    client = _AlwaysInvalidClient()

    with pytest.raises(ValidationError):
        extraction.extract_chunk_text("some chunk text", client=client)

    assert client.calls == extraction._MAX_RETRIES
