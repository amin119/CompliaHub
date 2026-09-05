import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.checkpointer import checkpointer as agent_checkpointer
from app.core.checkpointer import delete_conversation as delete_conversation_checkpoint
from app.core.db import get_db
from app.schemas.query import (
    ConversationResponse,
    ConversationTurn,
    GraphEvidence,
    QueryRequest,
    QueryResponse,
)
from app.services import (
    agent,
    answer_generation,
    graph_store,
    query_classifier,
    query_orchestration,
    retrieval,
)
from app.services import streaming_events as events
from app.services.query_classifier import QueryCategory

router = APIRouter(tags=["query"])

# Bug fix (post-Phase 6): before `off_topic` existed, a greeting or any
# other non-compliance question had no category that actually fit it, so
# the classifier's own "when unsure, prefer agent" tie-breaker sent it
# through the full retrieve→critique→rewrite loop — confirmed live to take
# ~19s and return two dozen irrelevant citations for "hi, how are you?".
# Fast-pathing this skips retrieval and any answer-generation LLM call
# entirely, so an off-topic question costs exactly one cheap classification
# call, nothing else. See docs/phase-5-agentic-loop.md.
#
# `classification.reply` (generated in that same classification call, see
# query_classifier.py) is the actual answer used — a real, varied response
# to what the user said, not one fixed sentence every time. This fallback
# only covers the rare case the model leaves `reply` empty despite
# instructions to fill it.
_OFF_TOPIC_FALLBACK = (
    "I'm a compliance assistant for ISO 27001, ISO 42001, and GDPR — I can't "
    "help with that, but ask me anything about those standards."
)


@router.post("/query", response_model=QueryResponse)
def query(request: QueryRequest, db: Session = Depends(get_db)) -> QueryResponse:
    """Phase 5: a cheap classifier routes each question to the cheapest
    retrieval strategy that can actually answer it, instead of Phase 4's
    fixed "always do vector + local + global search" pipeline — see
    docs/phase-5-agentic-loop.md for the reasoning.

    Phase 7: the actual classify-then-route logic now lives in
    `query_orchestration.run_query`, so this route and the evaluation
    harness run the exact same pipeline — this just discards the
    eval-only `context_texts`/`token_usage` the harness needs.
    """
    result = query_orchestration.run_query(
        request.question, db, conversation_id=request.conversation_id, top_k=request.top_k
    )
    return result.response


def _sse_encode(payloads):
    """Wraps `_stream_query_events`'s plain event dicts into the actual SSE
    wire format only at the very end — kept separate so the event-producing
    generator itself stays trivially testable (yields dicts, not strings).
    """
    for payload in payloads:
        yield f"data: {json.dumps(payload)}\n\n"


def _stream_query_events(request: QueryRequest, db: Session):
    """Generator body for `/query/stream` — see docs/phase-6-frontend.md for
    why this mirrors the plain `/query` route's classify-then-route
    structure instead of sharing code with it directly: every step here
    also has to decide what to push to `events` before doing the work, and
    the agent path delegates its own event pushing entirely to
    `agent.stream_agent`.
    """
    try:
        yield events.status_event("classifying")
        classification = query_classifier.classify_query(request.question)

        if classification.category == QueryCategory.OFF_TOPIC:
            conversation_id = request.conversation_id or str(uuid.uuid4())
            yield events.token_event(classification.reply or _OFF_TOPIC_FALLBACK)
            yield events.done_event(conversation_id, [], GraphEvidence())
            return

        if classification.category == QueryCategory.AGENT:
            driver = graph_store.get_neo4j_driver()
            try:
                for event in agent.stream_agent(
                    request.question,
                    db,
                    driver,
                    agent_checkpointer,
                    conversation_id=request.conversation_id,
                ):
                    yield event
            finally:
                driver.close()
            return

        conversation_id = request.conversation_id or str(uuid.uuid4())
        yield events.status_event("retrieving")
        context_chunks, _ = retrieval.vector_search(db, request.question, request.top_k)
        if not context_chunks:
            yield events.done_event(conversation_id, [], GraphEvidence())
            return

        if classification.category == QueryCategory.VECTOR:
            _, _, citations = retrieval.render_evidence(db, context_chunks, [], [])
            yield events.status_event("generating_answer")
            for token in answer_generation.stream_answer(request.question, context_chunks):
                yield events.token_event(token)
            yield events.done_event(conversation_id, citations, GraphEvidence())
            return

        # QueryCategory.GRAPH
        driver = graph_store.get_neo4j_driver()
        try:
            graph_relations = retrieval.local_search_facts(driver, context_chunks)
        finally:
            driver.close()
        graph_facts, _, citations = retrieval.render_evidence(
            db, context_chunks, graph_relations, []
        )
        graph_evidence = retrieval.build_graph_evidence(graph_relations)
        yield events.status_event("generating_answer")
        for token in answer_generation.stream_answer(
            request.question, context_chunks, graph_facts=graph_facts
        ):
            yield events.token_event(token)
        yield events.done_event(conversation_id, citations, graph_evidence)
    except Exception as exc:
        # A mid-stream failure (e.g. Gemini errors after already sending
        # tokens) must still end the SSE stream cleanly with an `error`
        # event — an uncaught exception here would just cut the HTTP
        # response off with no way for the frontend to distinguish that
        # from the network dropping.
        yield events.error_event(str(exc))


@router.post("/query/stream")
def query_stream(request: QueryRequest, db: Session = Depends(get_db)) -> StreamingResponse:
    """Phase 6 Part 2: the streaming counterpart to `POST /query` — same
    classify-then-route logic, but emits Server-Sent Events (`status`/
    `token`/`done`/`error`, see `app.services.streaming_events`) as the
    answer is generated instead of blocking for the full response.

    A plain `fetch()` + `ReadableStream` on the frontend, not the browser's
    `EventSource` — `EventSource` can't send a POST body, and the question
    has to go in the body, not a query string.
    """
    return StreamingResponse(
        _sse_encode(_stream_query_events(request, db)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/query/conversations/{conversation_id}", response_model=ConversationResponse)
def get_conversation(conversation_id: str) -> ConversationResponse:
    """Inspect a conversation's accumulated turn history — the concrete,
    user-facing fulfillment of the roadmap's "resumable/inspectable" agent
    session requirement (Part 1 only made this inspectable via internal
    debugging scripts; this makes it inspectable through the API itself).

    Reads directly from the checkpointer (`get_tuple`), not by building a
    full agent graph just to call `.get_state()` — cheaper, and doesn't
    need `db`/`driver` for a pure read.

    Only conversations that actually went through the agent loop at least
    once have anything to return here — a `conversation_id` from a
    `vector`/`graph`-classified turn is a real UUID but was never used as a
    checkpoint thread id, so this 404s for it, same as for a
    conversation_id that never existed at all. See
    docs/phase-5-agentic-loop.md.
    """
    config = {"configurable": {"thread_id": conversation_id}}
    checkpoint_tuple = agent_checkpointer.get_tuple(config)
    if checkpoint_tuple is None:
        raise HTTPException(status_code=404, detail="conversation not found")

    history = checkpoint_tuple.checkpoint["channel_values"].get("conversation_history", [])
    return ConversationResponse(
        conversation_id=conversation_id,
        turns=[ConversationTurn(**turn) for turn in history],
    )


@router.delete("/query/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: str) -> None:
    """Explicit "forget this conversation" — see
    `app.core.checkpointer.delete_conversation`'s docstring for why this is
    deliberately manual, not an automatic TTL/retention policy."""
    delete_conversation_checkpoint(conversation_id)
