from typing import Iterator, Protocol

from google import genai
from google.genai import types

from app.core.config import get_settings
from app.models.document import Chunk
from app.services import token_tracking

_SYSTEM_PROMPT = (
    "You are a compliance assistant answering questions about ISO/GDPR "
    "standards. Answer ONLY from the numbered excerpts provided — if they "
    "don't contain enough information, say so instead of guessing. Every "
    "claim must cite its source excerpt by the clause/article number shown "
    "in brackets, e.g. \"personal data must be processed lawfully [Article 6]\"."
)


class AnswerClient(Protocol):
    """Flattened to a plain string / string-iterator return — not the
    OpenAI SDK's nested `.choices[0].message.content` shape this used to
    mirror back when Grok was the answer model — so a test fake only needs
    two trivial methods, not to replicate any SDK's response object.
    """

    def create_completion(self, model: str, messages: list[dict], max_tokens: int) -> str: ...

    def stream_completion(
        self, model: str, messages: list[dict], max_tokens: int
    ) -> Iterator[str]: ...


def _split_messages(messages: list[dict]) -> tuple[str, str]:
    system_prompt = next(m["content"] for m in messages if m["role"] == "system")
    user_content = next(m["content"] for m in messages if m["role"] == "user")
    return system_prompt, user_content


class _GeminiAnswerClient:
    """Adapter around `google-genai`, narrowed to the two operations this
    module needs. Phase 6 Part 2 moved final answer generation here from
    Grok (xAI) specifically to unblock real token streaming — Gemini's SDK
    streams natively via `generate_content_stream`, and this project already
    depends on `google-genai` for extraction/classification, so this removes
    an external dependency (and its billing block) instead of adding one.
    """

    def __init__(self, api_key: str) -> None:
        self._client = genai.Client(api_key=api_key)

    def create_completion(self, model: str, messages: list[dict], max_tokens: int) -> str:
        system_prompt, content = _split_messages(messages)
        response = self._client.models.generate_content(
            model=model,
            contents=content,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt, max_output_tokens=max_tokens
            ),
        )
        token_tracking.record(response.usage_metadata)
        return response.text or ""

    def stream_completion(
        self, model: str, messages: list[dict], max_tokens: int
    ) -> Iterator[str]:
        system_prompt, content = _split_messages(messages)
        stream = self._client.models.generate_content_stream(
            model=model,
            contents=content,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt, max_output_tokens=max_tokens
            ),
        )
        # Gemini's streamed `usage_metadata` is cumulative per chunk, not
        # incremental — only the last chunk's value is recorded, otherwise
        # every earlier chunk's counts would be double(-triple-...)-counted.
        last_usage_metadata = None
        for chunk in stream:
            if chunk.usage_metadata is not None:
                last_usage_metadata = chunk.usage_metadata
            if chunk.text:
                yield chunk.text
        token_tracking.record(last_usage_metadata)


def get_answer_client() -> AnswerClient:
    settings = get_settings()
    return _GeminiAnswerClient(api_key=settings.gemini_api_key)


def _format_context(context_chunks: list[Chunk]) -> str:
    parts = []
    for i, chunk in enumerate(context_chunks, start=1):
        label = chunk.clause_number or chunk.title or f"chunk {i}"
        parts.append(f"[{i}] ({label}) {chunk.text}")
    return "\n\n".join(parts)


def _build_messages(
    question: str,
    context_chunks: list[Chunk],
    graph_facts: list[str] | None,
    community_context: list[str] | None,
) -> list[dict]:
    """Shared by `generate_answer` and `stream_answer` — same prompt either
    way, only how the response comes back differs.

    Both `graph_facts` and `community_context` are **separate,
    clearly-labeled sections** appended after the vector excerpts —
    sectioned rather than interleaved with them or each other, so it stays
    possible to tell which source (vector retrieval, graph traversal, or
    corpus-wide clustering) actually drove a given part of the answer. Each
    fact string is expected to already carry its own citation label (e.g. a
    clause number), same as the numbered excerpts above it — except a
    community's own summary line, which is a synthesized description, not
    a specific cited claim.
    """
    content = f"Excerpts:\n\n{_format_context(context_chunks)}"
    if graph_facts:
        content += "\n\nGraph-derived facts:\n\n" + "\n".join(graph_facts)
    if community_context:
        content += "\n\nRelated themes (from corpus-wide clustering):\n\n" + "\n".join(
            community_context
        )
    content += f"\n\nQuestion: {question}"
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": content},
    ]


def generate_answer(
    question: str,
    context_chunks: list[Chunk],
    client: AnswerClient | None = None,
    graph_facts: list[str] | None = None,
    community_context: list[str] | None = None,
) -> str:
    """Generates the final answer from the reranked top-N context chunks,
    plus (Phase 4) any graph-traversal facts local search found, plus
    (Phase 4 Part 2) thematically related community summaries global search
    found.

    Returns plain answer text; the caller (the `/query` route) builds the
    structured `Citation` list directly from `context_chunks` (and, for
    Phase 4, from whichever chunks the graph facts / community drill-down
    facts cite) rather than trying to parse which excerpts the model
    actually leaned on — precise per-claim citation attribution/
    faithfulness scoring is Phase 7 (evaluation harness) territory, not
    this baseline.

    `client` defaults to the real Gemini-backed adapter; pass a fake
    `AnswerClient` in tests to verify the prompt/citation formatting without
    a network call.
    """
    client = client or get_answer_client()
    settings = get_settings()
    messages = _build_messages(question, context_chunks, graph_facts, community_context)
    return client.create_completion(
        model=settings.gemini_answer_model, messages=messages, max_tokens=1024
    )


def stream_answer(
    question: str,
    context_chunks: list[Chunk],
    client: AnswerClient | None = None,
    graph_facts: list[str] | None = None,
    community_context: list[str] | None = None,
) -> Iterator[str]:
    """Phase 6 Part 2: same prompt as `generate_answer`, but yields the
    answer as it's generated instead of waiting for the full response —
    what `/query/stream` (direct vector/graph paths) and the agent's
    `answer_node` (both the streaming and non-streaming `/query` routes)
    use to surface real tokens as Gemini produces them.
    """
    client = client or get_answer_client()
    settings = get_settings()
    messages = _build_messages(question, context_chunks, graph_facts, community_context)
    yield from client.stream_completion(
        model=settings.gemini_answer_model, messages=messages, max_tokens=1024
    )
