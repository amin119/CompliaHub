"""Phase 7: per-request Gemini token-usage accumulation, so the evaluation
harness can estimate real cost per query. Opt-in via `contextvars` rather
than a global counter — `record()` is safe to call unconditionally from
every Gemini call site (it no-ops when nothing is tracking), so this can be
threaded through `query_classifier.py`/`answer_generation.py`/`agent.py`
without those modules needing to know whether a caller cares.

Nothing outside `app.services.query_orchestration.run_query` calls
`start_tracking()` today — ingestion/extraction/the scanner's own LLM calls
(`finding_validation.py`, `finding_remediation.py`, etc.) never start a
tracker, so `record()` is a guaranteed no-op for them. This phase only
prices the `/query` path.
"""

from contextvars import ContextVar
from dataclasses import dataclass


@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0


_current: ContextVar["TokenUsage | None"] = ContextVar("_current_token_usage", default=None)


def start_tracking() -> TokenUsage:
    """Begins tracking for the current request/task, returning the mutable
    accumulator every subsequent `record()` call (from any Gemini adapter
    invoked during this same context) will add onto in place.
    """
    usage = TokenUsage()
    _current.set(usage)
    return usage


def record(usage_metadata) -> None:
    """Adds one Gemini call's token counts onto the active tracker, if any.
    `usage_metadata` is a `google.genai.types.GenerateContentResponse
    .usage_metadata` (or `None`, which this treats as "nothing to add" rather
    than raising — some responses may not carry it).
    """
    usage = _current.get()
    if usage is None or usage_metadata is None:
        return
    usage.prompt_tokens += getattr(usage_metadata, "prompt_token_count", None) or 0
    usage.completion_tokens += getattr(usage_metadata, "candidates_token_count", None) or 0


def current() -> TokenUsage | None:
    return _current.get()
