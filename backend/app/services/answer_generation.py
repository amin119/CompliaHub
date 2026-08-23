from typing import Protocol

import openai

from app.core.config import get_settings
from app.models.document import Chunk

_SYSTEM_PROMPT = (
    "You are a compliance assistant answering questions about ISO/GDPR "
    "standards. Answer ONLY from the numbered excerpts provided — if they "
    "don't contain enough information, say so instead of guessing. Every "
    "claim must cite its source excerpt by the clause/article number shown "
    "in brackets, e.g. \"personal data must be processed lawfully [Article 6]\"."
)


class AnswerClient(Protocol):
    """Flattened to a plain string return — not the OpenAI SDK's nested
    `.choices[0].message.content` shape — so a test fake only needs one
    trivial method, not to replicate that nested response object.
    """

    def create_completion(self, model: str, messages: list[dict], max_tokens: int) -> str: ...


class _OpenAIAnswerClient:
    """Adapter around the openai SDK's Chat Completions API, narrowed to the
    one operation this module needs. Grok (xAI) exposes an OpenAI-compatible
    API, so this uses the `openai` SDK pointed at xAI's base_url rather than
    a dedicated xAI SDK.
    """

    def __init__(self, api_key: str, base_url: str) -> None:
        self._client = openai.OpenAI(api_key=api_key, base_url=base_url)

    def create_completion(self, model: str, messages: list[dict], max_tokens: int) -> str:
        completion = self._client.chat.completions.create(
            model=model, messages=messages, max_tokens=max_tokens
        )
        return completion.choices[0].message.content or ""


def get_grok_client() -> AnswerClient:
    settings = get_settings()
    return _OpenAIAnswerClient(api_key=settings.grok_api_key, base_url=settings.grok_base_url)


def _format_context(context_chunks: list[Chunk]) -> str:
    parts = []
    for i, chunk in enumerate(context_chunks, start=1):
        label = chunk.clause_number or chunk.title or f"chunk {i}"
        parts.append(f"[{i}] ({label}) {chunk.text}")
    return "\n\n".join(parts)


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

    Both `graph_facts` and `community_context` are **separate,
    clearly-labeled sections** appended after the vector excerpts —
    sectioned rather than interleaved with them or each other, so it stays
    possible to tell which source (vector retrieval, graph traversal, or
    corpus-wide clustering) actually drove a given part of the answer. Each
    fact string is expected to already carry its own citation label (e.g. a
    clause number), same as the numbered excerpts above it — except a
    community's own summary line, which is a synthesized description, not
    a specific cited claim.

    Returns plain answer text; the caller (the `/query` route) builds the
    structured `Citation` list directly from `context_chunks` (and, for
    Phase 4, from whichever chunks the graph facts / community drill-down
    facts cite) rather than trying to parse which excerpts the model
    actually leaned on — precise per-claim citation attribution/
    faithfulness scoring is Phase 7 (evaluation harness) territory, not
    this baseline.

    `client` defaults to the real Grok-backed adapter; pass a fake
    `AnswerClient` in tests to verify the prompt/citation formatting without
    a network call.
    """
    client = client or get_grok_client()
    settings = get_settings()

    content = f"Excerpts:\n\n{_format_context(context_chunks)}"
    if graph_facts:
        content += "\n\nGraph-derived facts:\n\n" + "\n".join(graph_facts)
    if community_context:
        content += "\n\nRelated themes (from corpus-wide clustering):\n\n" + "\n".join(
            community_context
        )
    content += f"\n\nQuestion: {question}"

    return client.create_completion(
        model=settings.answer_model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
        max_tokens=1024,
    )
