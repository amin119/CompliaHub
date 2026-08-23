import pytest
from pydantic import ValidationError

from app.services import query_classifier
from app.services.query_classifier import QueryCategory, QueryClassification


class _FakeClassifierClient:
    def __init__(self, fail_times: int = 0, result: QueryClassification | None = None):
        self.fail_times = fail_times
        self.result = result or QueryClassification(category=QueryCategory.VECTOR)
        self.calls = 0

    def classify(self, question: str) -> QueryClassification:
        self.calls += 1
        if self.calls <= self.fail_times:
            raise query_classifier.ClassificationRateLimited("simulated rate limit")
        return self.result


class _AlwaysInvalidClient:
    def __init__(self) -> None:
        self.calls = 0

    def classify(self, question: str) -> QueryClassification:
        self.calls += 1
        return QueryClassification.model_validate({"category": "not_a_real_category"})


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch):
    monkeypatch.setattr(query_classifier.time, "sleep", lambda seconds: None)


def test_classify_query_retries_until_success():
    expected = QueryClassification(category=QueryCategory.AGENT)
    client = _FakeClassifierClient(fail_times=2, result=expected)

    result = query_classifier.classify_query("some question", client=client)

    assert result == expected
    assert client.calls == 3


def test_classify_query_raises_after_exhausting_retries():
    client = _FakeClassifierClient(fail_times=999)

    with pytest.raises(query_classifier.ClassificationRateLimited):
        query_classifier.classify_query("some question", client=client)

    assert client.calls == query_classifier._MAX_RETRIES


def test_classify_query_retries_on_validation_error_too():
    client = _AlwaysInvalidClient()

    with pytest.raises(ValidationError):
        query_classifier.classify_query("some question", client=client)

    assert client.calls == query_classifier._MAX_RETRIES


def test_all_three_categories_round_trip():
    for category in QueryCategory:
        client = _FakeClassifierClient(result=QueryClassification(category=category))
        assert query_classifier.classify_query("q", client=client).category == category
