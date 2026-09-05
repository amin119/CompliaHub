"""Pure unit tests for Phase 7's contextvar-based token accumulator — no
DB/LLM involved.
"""

from types import SimpleNamespace

from app.services import token_tracking


def test_record_is_a_noop_when_nothing_is_tracking():
    # No start_tracking() call in this test — record() must not raise, and
    # current() must reflect "nothing active", not a stray leftover value
    # from another test.
    token_tracking._current.set(None)
    token_tracking.record(SimpleNamespace(prompt_token_count=10, candidates_token_count=5))
    assert token_tracking.current() is None


def test_record_accumulates_onto_the_started_tracker():
    usage = token_tracking.start_tracking()
    token_tracking.record(SimpleNamespace(prompt_token_count=10, candidates_token_count=5))
    token_tracking.record(SimpleNamespace(prompt_token_count=3, candidates_token_count=2))

    assert usage.prompt_tokens == 13
    assert usage.completion_tokens == 7
    # The same object instance is what current() returns — callers holding
    # the value returned by start_tracking() see every subsequent record().
    assert token_tracking.current() is usage


def test_record_handles_none_usage_metadata():
    token_tracking.start_tracking()
    token_tracking.record(None)  # some responses may not carry usage_metadata
    assert token_tracking.current().prompt_tokens == 0
    assert token_tracking.current().completion_tokens == 0


def test_record_handles_missing_fields_on_usage_metadata():
    token_tracking.start_tracking()
    # A usage_metadata-shaped object missing one of the two expected
    # attributes entirely (not just None) must not raise.
    token_tracking.record(SimpleNamespace())
    assert token_tracking.current().prompt_tokens == 0
    assert token_tracking.current().completion_tokens == 0


def test_start_tracking_resets_across_two_sequential_fake_requests():
    first = token_tracking.start_tracking()
    token_tracking.record(SimpleNamespace(prompt_token_count=100, candidates_token_count=50))
    assert first.prompt_tokens == 100

    second = token_tracking.start_tracking()
    assert second.prompt_tokens == 0
    assert second.completion_tokens == 0
    assert second is not first
