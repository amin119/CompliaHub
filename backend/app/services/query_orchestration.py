"""Phase 7: the real `/query` pipeline, extracted from
`app.api.routes.query`'s `query()` route body so the HTTP route and the
Phase 7 evaluation harness call the exact same logic — never a second,
subtly-different pipeline built just for scoring (same reasoning Phase 5
used extracting `retrieval.py`'s primitives out of Phase 4's inline route
code).

Deliberately does NOT touch `/query/stream`'s `_stream_query_events` — see
that function's own docstring for why it mirrors rather than shares code
with the plain route: forcing the streaming path through a single-return-
value function here would mean buffering every token before yielding,
defeating streaming's purpose, and the eval harness never needs token-by-
token output.
"""

import time
import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.checkpointer import checkpointer as agent_checkpointer
from app.core.checkpointer import ensure_open as ensure_checkpointer_open
from app.models.document import Chunk
from app.schemas.query import QueryResponse
from app.services import (
    agent,
    answer_generation,
    graph_store,
    query_classifier,
    retrieval,
    token_tracking,
)
from app.services.query_classifier import QueryCategory
from app.services.token_tracking import TokenUsage

_OFF_TOPIC_FALLBACK = (
    "I'm a compliance assistant for ISO 27001, ISO 42001, and GDPR — I can't "
    "help with that, but ask me anything about those standards."
)


@dataclass
class OrchestrationResult:
    """`response` is the exact object the HTTP route returns as-is.
    `context_texts`/`token_usage` are eval-only internals, deliberately never
    added to the public `QueryResponse` schema — real retrieved chunk text
    (for RAGAS-style faithfulness/context metrics) and this turn's real
    Gemini token counts.
    """

    response: QueryResponse
    context_texts: list[str] = field(default_factory=list)
    token_usage: TokenUsage = field(default_factory=TokenUsage)


def _context_texts_for_citations(db: Session, citations: list) -> list[str]:
    """Reconstructs retrieved-context text from a response's own citations —
    works uniformly across vector/graph/agent categories without needing
    `agent.run_agent` to expose its internal chunk cache (which lives inside
    `build_agent`'s closure, not `AgentState`, and isn't meant to escape it).

    A disclosed scope simplification (see docs/phase-7-evaluation.md): this
    treats vector-retrieved chunk text as *the* context every metric scores
    against, not also the separate `graph_facts`/`community_context` strings
    — those are supplementary evidence, not the primary text basis, and
    scoring them textually too added complexity with no proportionate payoff
    for a first version of this harness.
    """
    if not citations:
        return []
    chunk_ids = [c.chunk_id for c in citations]
    chunks_by_id = {c.id: c for c in db.scalars(select(Chunk).where(Chunk.id.in_(chunk_ids)))}
    return [chunks_by_id[cid].text for cid in chunk_ids if cid in chunks_by_id]


def run_query(
    question: str,
    db: Session,
    conversation_id: str | None = None,
    top_k: int = 5,
) -> OrchestrationResult:
    """The exact pipeline `POST /query` runs (classify -> off_topic/agent/
    vector/graph), wrapped with latency timing and token-usage tracking —
    both discarded by the plain HTTP route (which only ever returns
    `.response`) and consumed by the Phase 7 evaluation harness (which also
    wants `.context_texts`/`.token_usage`).
    """
    start = time.perf_counter()
    usage = token_tracking.start_tracking()

    classification = query_classifier.classify_query(question)

    if classification.category == QueryCategory.OFF_TOPIC:
        response = QueryResponse(
            answer=classification.reply or _OFF_TOPIC_FALLBACK,
            citations=[],
            conversation_id=conversation_id or str(uuid.uuid4()),
            category=classification.category.value,
            latency_ms=(time.perf_counter() - start) * 1000,
        )
        return OrchestrationResult(response=response, context_texts=[], token_usage=usage)

    if classification.category == QueryCategory.AGENT:
        # Lazily ensures the checkpointer is open, exactly once per process
        # — needed when this runs inside the Phase 7 eval harness's Celery
        # worker, which has no FastAPI lifespan of its own to open it
        # ahead of time (a no-op in the host FastAPI process, where
        # `app.main`'s lifespan already opened it at startup). Called only
        # here, not unconditionally for every question, since only the
        # agent path ever touches the checkpointer.
        ensure_checkpointer_open()
        driver = graph_store.get_neo4j_driver()
        try:
            response = agent.run_agent(
                question, db, driver, agent_checkpointer, conversation_id=conversation_id
            )
        finally:
            driver.close()
        response.category = classification.category.value
        response.latency_ms = (time.perf_counter() - start) * 1000
        context_texts = _context_texts_for_citations(db, response.citations)
        return OrchestrationResult(
            response=response, context_texts=context_texts, token_usage=usage
        )

    # vector/graph questions don't go through the agent (see `query.py`'s own
    # route for the same comment) — still generate a conversation_id for a
    # consistent API contract.
    conversation_id = conversation_id or str(uuid.uuid4())

    context_chunks, query_vector = retrieval.vector_search(db, question, top_k)
    if not context_chunks:
        response = QueryResponse(
            answer="No relevant information found.",
            citations=[],
            conversation_id=conversation_id,
            category=classification.category.value,
            latency_ms=(time.perf_counter() - start) * 1000,
        )
        return OrchestrationResult(response=response, context_texts=[], token_usage=usage)

    if classification.category == QueryCategory.VECTOR:
        answer = answer_generation.generate_answer(question, context_chunks)
        _, _, citations = retrieval.render_evidence(db, context_chunks, [], [])
        response = QueryResponse(
            answer=answer,
            citations=citations,
            conversation_id=conversation_id,
            category=classification.category.value,
            latency_ms=(time.perf_counter() - start) * 1000,
        )
        return OrchestrationResult(
            response=response,
            context_texts=[chunk.text for chunk in context_chunks],
            token_usage=usage,
        )

    # QueryCategory.GRAPH: vector search + Phase 4 Part 1 local search.
    driver = graph_store.get_neo4j_driver()
    try:
        graph_relations = retrieval.local_search_facts(driver, context_chunks)
    finally:
        driver.close()

    graph_facts, _, citations = retrieval.render_evidence(db, context_chunks, graph_relations, [])
    graph_evidence = retrieval.build_graph_evidence(graph_relations)
    answer = answer_generation.generate_answer(question, context_chunks, graph_facts=graph_facts)
    response = QueryResponse(
        answer=answer,
        citations=citations,
        conversation_id=conversation_id,
        graph_evidence=graph_evidence,
        category=classification.category.value,
        latency_ms=(time.perf_counter() - start) * 1000,
    )
    return OrchestrationResult(
        response=response,
        context_texts=[chunk.text for chunk in context_chunks],
        token_usage=usage,
    )
