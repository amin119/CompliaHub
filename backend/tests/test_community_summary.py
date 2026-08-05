import pytest
from pydantic import ValidationError

from app.services import community_summary
from app.services.graph_store import RelationEdge
from app.services.ontology import EntityType


class _FakeSummaryClient:
    """A fake `SummaryClient` — exercises `summarize_community`'s retry
    logic without any real Gemini account or network call.
    """

    def __init__(
        self, fail_times: int = 0, result: community_summary.CommunitySummary | None = None
    ):
        self.fail_times = fail_times
        self.result = result or community_summary.CommunitySummary(title="T", summary="S")
        self.calls = 0

    def summarize(self, community_text: str) -> community_summary.CommunitySummary:
        self.calls += 1
        if self.calls <= self.fail_times:
            raise community_summary.SummaryRateLimited("simulated rate limit")
        return self.result


class _AlwaysInvalidClient:
    def __init__(self) -> None:
        self.calls = 0

    def summarize(self, community_text: str) -> community_summary.CommunitySummary:
        self.calls += 1
        return community_summary.CommunitySummary.model_validate({"title": "T"})


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch):
    monkeypatch.setattr(community_summary.time, "sleep", lambda seconds: None)


def _members() -> list[tuple[EntityType, str]]:
    return [(EntityType.CONTROL, "A"), (EntityType.RISK, "B")]


def test_format_community_text_includes_members_and_intra_relations():
    members = _members()
    relations = [
        RelationEdge("A", EntityType.CONTROL, "applies_to", "B", EntityType.RISK),
        RelationEdge("A", EntityType.CONTROL, "applies_to", "Outside", EntityType.RISK),
    ]

    text = community_summary.format_community_text(members, relations)

    assert "A (Control)" in text
    assert "B (Risk)" in text
    assert "A applies_to B" in text
    assert "Outside" not in text  # not a member of this community


def test_summarize_community_retries_until_success():
    expected = community_summary.CommunitySummary(title="Access Control", summary="...")
    client = _FakeSummaryClient(fail_times=2, result=expected)

    result = community_summary.summarize_community(_members(), [], client=client)

    assert result == expected
    assert client.calls == 3


def test_summarize_community_raises_after_exhausting_retries():
    client = _FakeSummaryClient(fail_times=999)

    with pytest.raises(community_summary.SummaryRateLimited):
        community_summary.summarize_community(_members(), [], client=client)

    assert client.calls == community_summary._MAX_RETRIES


def test_summarize_community_retries_on_validation_error_too():
    client = _AlwaysInvalidClient()

    with pytest.raises(ValidationError):
        community_summary.summarize_community(_members(), [], client=client)

    assert client.calls == community_summary._MAX_RETRIES
