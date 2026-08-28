"""Shared event-shape vocabulary for `/query/stream`'s Server-Sent Events.

One small set of dict-builders so the agent loop's LangGraph nodes (pushing
through `get_stream_writer()`) and the direct vector/graph paths in the
`/query` route emit the exact same `{"type": ...}` shapes — the frontend
handles both with one switch statement regardless of which retrieval
strategy actually answered the question. Deliberately plain dicts, not
pydantic models: these are serialized straight to SSE `data:` lines, and
`GraphEvidence`/`Citation` already have their own `model_dump` for the one
place (`done_event`) that embeds them.
"""

from app.schemas.query import Citation, GraphEvidence


def status_event(stage: str) -> dict:
    return {"type": "status", "stage": stage}


def token_event(text: str) -> dict:
    return {"type": "token", "text": text}


def done_event(
    conversation_id: str, citations: list[Citation], graph_evidence: GraphEvidence
) -> dict:
    return {
        "type": "done",
        "conversation_id": conversation_id,
        "citations": [citation.model_dump(mode="json") for citation in citations],
        "graph_evidence": graph_evidence.model_dump(mode="json"),
    }


def error_event(message: str) -> dict:
    return {"type": "error", "message": message}
