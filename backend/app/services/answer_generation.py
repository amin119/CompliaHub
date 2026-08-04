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


def _format_context(context_chunks: list[Chunk]) -> str:
    parts = []
    for i, chunk in enumerate(context_chunks, start=1):
        label = chunk.clause_number or chunk.title or f"chunk {i}"
        parts.append(f"[{i}] ({label}) {chunk.text}")
    return "\n\n".join(parts)


def generate_answer(question: str, context_chunks: list[Chunk]) -> str:
    """Generates the final answer from the reranked top-N context chunks.

    Returns plain answer text; the caller (the `/query` route) builds the
    structured `Citation` list directly from `context_chunks` rather than
    trying to parse which excerpts the model actually leaned on — precise
    per-claim citation attribution/faithfulness scoring is Phase 7
    (evaluation harness) territory, not this baseline.
    """
    settings = get_settings()
    client = openai.OpenAI(api_key=settings.grok_api_key, base_url=settings.grok_base_url)

    completion = client.chat.completions.create(
        model=settings.answer_model,
        max_tokens=1024,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Excerpts:\n\n{_format_context(context_chunks)}\n\nQuestion: {question}"
                ),
            },
        ],
    )
    return completion.choices[0].message.content or ""
