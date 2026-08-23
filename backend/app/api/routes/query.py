import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.checkpointer import checkpointer as agent_checkpointer
from app.core.checkpointer import delete_conversation as delete_conversation_checkpoint
from app.core.db import get_db
from app.schemas.query import ConversationResponse, ConversationTurn, QueryRequest, QueryResponse
from app.services import agent, answer_generation, graph_store, query_classifier, retrieval
from app.services.query_classifier import QueryCategory

router = APIRouter(tags=["query"])


@router.post("/query", response_model=QueryResponse)
def query(request: QueryRequest, db: Session = Depends(get_db)) -> QueryResponse:
    """Phase 5: a cheap classifier routes each question to the cheapest
    retrieval strategy that can actually answer it, instead of Phase 4's
    fixed "always do vector + local + global search" pipeline — see
    docs/phase-5-agentic-loop.md for the reasoning.
    """
    classification = query_classifier.classify_query(request.question)

    if classification.category == QueryCategory.AGENT:
        driver = graph_store.get_neo4j_driver()
        try:
            return agent.run_agent(
                request.question,
                db,
                driver,
                agent_checkpointer,
                conversation_id=request.conversation_id,
            )
        finally:
            driver.close()

    # vector/graph questions don't go through the agent, so they don't
    # build or read conversation memory (see docs/phase-5-agentic-loop.md)
    # — still echo/generate a conversation_id for a consistent API contract,
    # even though only an `agent`-classified turn ever does anything with it.
    conversation_id = request.conversation_id or str(uuid.uuid4())

    context_chunks, query_vector = retrieval.vector_search(db, request.question, request.top_k)
    if not context_chunks:
        return QueryResponse(
            answer="No relevant information found.", citations=[], conversation_id=conversation_id
        )

    if classification.category == QueryCategory.VECTOR:
        answer = answer_generation.generate_answer(request.question, context_chunks)
        _, _, citations = retrieval.render_evidence(db, context_chunks, [], [])
        return QueryResponse(answer=answer, citations=citations, conversation_id=conversation_id)

    # QueryCategory.GRAPH: vector search + Phase 4 Part 1 local search
    # (relational questions about specific named things) — global/thematic
    # search is reserved for the agent path, since deciding *whether* a
    # thematic summary is even relevant is exactly the judgment call this
    # baseline defers to Phase 5.
    driver = graph_store.get_neo4j_driver()
    try:
        graph_relations = retrieval.local_search_facts(driver, context_chunks)
    finally:
        driver.close()

    graph_facts, _, citations = retrieval.render_evidence(db, context_chunks, graph_relations, [])
    answer = answer_generation.generate_answer(
        request.question, context_chunks, graph_facts=graph_facts
    )
    return QueryResponse(answer=answer, citations=citations, conversation_id=conversation_id)


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
