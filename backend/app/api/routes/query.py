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
    lexical_search,
    reranking,
    vector_store,
)

router = APIRouter(tags=["query"])

# How many candidates each retrieval path contributes before fusion — wider
# than the final rerank/answer top_k so RRF has enough signal to work with.
_DENSE_TOP_K = 20
_LEXICAL_TOP_K = 20


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

    answer = answer_generation.generate_answer(request.question, context_chunks)

    citations = [
        Citation(
            chunk_id=chunk.id,
            document_filename=chunk.document.filename,
            clause_number=chunk.clause_number,
            path=str(chunk.path),
        )
        for chunk in context_chunks
    ]
    return QueryResponse(answer=answer, citations=citations)
