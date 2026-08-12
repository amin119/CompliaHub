import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.document import Chunk
from app.schemas.query import Citation, QueryRequest, QueryResponse
from app.services import (
    answer_generation,
    embedding,
    fusion,
    graph_store,
    lexical_search,
    local_search,
    reranking,
    vector_store,
)

router = APIRouter(tags=["query"])

# How many candidates each retrieval path contributes before fusion — wider
# than the final rerank/answer top_k so RRF has enough signal to work with.
_DENSE_TOP_K = 20
_LEXICAL_TOP_K = 20

# Local search's BFS can legitimately surface hundreds of relations from a
# well-connected graph (confirmed live: a real 2-hop traversal from 5
# reranked chunks' entities returned 321) — far too many to hand the answer
# LLM without blowing up prompt size/cost. Capped here, not inside
# `expand_hops` itself, so that function stays a complete, uncapped
# traversal (useful on its own, e.g. for future debugging/inspection) and
# this is purely "how much of that evidence actually reaches the prompt" —
# same "gather broadly, narrow before the LLM" shape `_DENSE_TOP_K` vs.
# `request.top_k` already uses for vector search. Traversal order is
# BFS-by-hop, so earlier (closer) relations are kept over farther ones.
_MAX_GRAPH_FACTS = 30


@router.post("/query", response_model=QueryResponse)
def query(request: QueryRequest, db: Session = Depends(get_db)) -> QueryResponse:
    query_vector = embedding.embed_texts([request.question], input_type="query")[0]

    qdrant_client = vector_store.get_qdrant_client()
    dense_hits = vector_store.search(qdrant_client, query_vector, top_k=_DENSE_TOP_K)
    lexical_hits = lexical_search.search_chunks(db, request.question, top_k=_LEXICAL_TOP_K)

    fused_ids = fusion.reciprocal_rank_fusion(
        [[chunk_id for chunk_id, _ in dense_hits], [chunk_id for chunk_id, _ in lexical_hits]]
    )
    if not fused_ids:
        return QueryResponse(answer="No relevant information found.", citations=[])

    chunks_by_id = {
        chunk.id: chunk for chunk in db.scalars(select(Chunk).where(Chunk.id.in_(fused_ids)))
    }
    # Re-apply RRF's order — the DB query above doesn't preserve `IN (...)` order.
    fused_chunks = [chunks_by_id[chunk_id] for chunk_id in fused_ids if chunk_id in chunks_by_id]

    rerank_results = reranking.rerank(
        request.question, [chunk.text for chunk in fused_chunks], top_n=request.top_k
    )
    # Cohere already orders `results` by relevance_score descending, so this
    # list comprehension preserves that order.
    context_chunks = [fused_chunks[result.index] for result in rerank_results]

    # Phase 4 local search: pivot from these already-reranked chunks into the
    # graph (via the chunk_id provenance every relation carries) rather than
    # a second, separately-tuned embedding-similarity lookup against entity
    # names — see docs/phase-4-graph-retrieval.md for the reasoning.
    driver = graph_store.get_neo4j_driver()
    try:
        seed_keys = graph_store.fetch_entities_for_chunks(
            driver, [str(chunk.id) for chunk in context_chunks]
        )
        graph_relations = local_search.expand_hops(
            seed_keys, lambda keys: graph_store.fetch_relations_touching(driver, keys)
        )[:_MAX_GRAPH_FACTS]
    finally:
        driver.close()

    citations_by_chunk_id = {
        chunk.id: Citation(
            chunk_id=chunk.id,
            document_filename=chunk.document.filename,
            clause_number=chunk.clause_number,
            path=str(chunk.path),
        )
        for chunk in context_chunks
    }

    # Relations found by graph traversal often point at chunks outside the
    # original reranked set — fetch those too so they get a real citation
    # (filename/clause number) instead of just a bare chunk id.
    new_chunk_ids = {
        uuid.UUID(relation.chunk_id)
        for relation in graph_relations
        if uuid.UUID(relation.chunk_id) not in citations_by_chunk_id
    }
    if new_chunk_ids:
        for chunk in db.scalars(select(Chunk).where(Chunk.id.in_(new_chunk_ids))):
            citations_by_chunk_id[chunk.id] = Citation(
                chunk_id=chunk.id,
                document_filename=chunk.document.filename,
                clause_number=chunk.clause_number,
                path=str(chunk.path),
            )

    graph_facts = []
    for relation in graph_relations:
        citation = citations_by_chunk_id.get(uuid.UUID(relation.chunk_id))
        if citation is None:
            continue
        label = citation.clause_number or relation.chunk_id
        graph_facts.append(
            f"[{label}] {relation.source_type.value}:{relation.source_name!r} "
            f"--{relation.relation_type}--> {relation.target_type.value}:{relation.target_name!r}"
        )

    answer = answer_generation.generate_answer(
        request.question, context_chunks, graph_facts=graph_facts
    )

    # Citation order: reranked chunks first (as before), then any additional
    # chunks the graph traversal surfaced.
    citations = [citations_by_chunk_id[chunk.id] for chunk in context_chunks] + [
        citations_by_chunk_id[chunk_id] for chunk_id in new_chunk_ids
    ]
    return QueryResponse(answer=answer, citations=citations)
