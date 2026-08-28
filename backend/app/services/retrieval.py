import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Chunk
from app.schemas.query import Citation, GraphEdge, GraphEvidence, GraphNode
from app.services import (
    embedding,
    fusion,
    global_search,
    graph_store,
    lexical_search,
    local_search,
    reranking,
    vector_store,
)
from app.services.graph_store import CommunityWithEmbedding, ProvenancedRelationEdge

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
# this is purely "how much of that evidence actually reaches the prompt".
MAX_GRAPH_FACTS = 30

# Same "gather broadly, cap what reaches the prompt" reasoning as
# MAX_GRAPH_FACTS, scoped per matched community rather than globally.
MAX_DRILLDOWN_FACTS_PER_COMMUNITY = 10


def vector_search(db: Session, question: str, top_k: int) -> tuple[list[Chunk], list[float]]:
    """Dense + lexical + RRF fusion + rerank, Phase 2's retrieval pipeline —
    shared by every retrieval strategy (direct vector/graph paths and the
    Phase 5 agent loop), so it's written once here instead of duplicated at
    each call site. Returns both the reranked chunks *and* the question's
    embedding, since local/global search reuse that same vector rather than
    re-embedding.
    """
    query_vector = embedding.embed_texts([question], input_type="query")[0]

    qdrant_client = vector_store.get_qdrant_client()
    dense_hits = vector_store.search(qdrant_client, query_vector, top_k=_DENSE_TOP_K)
    lexical_hits = lexical_search.search_chunks(db, question, top_k=_LEXICAL_TOP_K)

    fused_ids = fusion.reciprocal_rank_fusion(
        [[chunk_id for chunk_id, _ in dense_hits], [chunk_id for chunk_id, _ in lexical_hits]]
    )
    if not fused_ids:
        return [], query_vector

    chunks_by_id = {
        chunk.id: chunk for chunk in db.scalars(select(Chunk).where(Chunk.id.in_(fused_ids)))
    }
    # Re-apply RRF's order — the DB query above doesn't preserve `IN (...)` order.
    fused_chunks = [chunks_by_id[chunk_id] for chunk_id in fused_ids if chunk_id in chunks_by_id]
    if not fused_chunks:
        return [], query_vector

    rerank_results = reranking.rerank(question, [chunk.text for chunk in fused_chunks], top_n=top_k)
    # Cohere already orders `results` by relevance_score descending, so this
    # list comprehension preserves that order.
    context_chunks = [fused_chunks[result.index] for result in rerank_results]
    return context_chunks, query_vector


def local_search_facts(driver, context_chunks: list[Chunk]) -> list[ProvenancedRelationEdge]:
    """Phase 4 Part 1: pivot from already-reranked chunks into the graph via
    each relation's `chunk_id` provenance, then BFS outward — see
    docs/phase-4-graph-retrieval.md for why this reuses chunk retrieval
    instead of a separate entity-embedding-similarity path.
    """
    seed_keys = graph_store.fetch_entities_for_chunks(
        driver, [str(chunk.id) for chunk in context_chunks]
    )
    return local_search.expand_hops(
        seed_keys, lambda keys: graph_store.fetch_relations_touching(driver, keys)
    )[:MAX_GRAPH_FACTS]


def global_search_context(
    driver, query_vector: list[float]
) -> list[tuple[CommunityWithEmbedding, list[ProvenancedRelationEdge]]]:
    """Phase 4 Part 2: rank community summaries by similarity to the
    question, then drill into each match's member entities for citable
    specifics.
    """
    all_communities = graph_store.fetch_community_embeddings(driver)
    matched_communities = global_search.find_similar_communities(query_vector, all_communities)
    return [
        (
            community,
            graph_store.fetch_relations_touching(
                driver, graph_store.fetch_community_members(driver, community.id)
            )[:MAX_DRILLDOWN_FACTS_PER_COMMUNITY],
        )
        for community in matched_communities
    ]


def build_graph_evidence(
    graph_relations: list[ProvenancedRelationEdge],
    community_drilldowns: list[tuple[CommunityWithEmbedding, list[ProvenancedRelationEdge]]]
    | None = None,
) -> GraphEvidence:
    """Phase 6 Part 2: the structural counterpart to `render_evidence`'s
    prompt-string formatting — turns the same relations into deduped nodes/
    edges for the frontend's graph visualization, instead of throwing that
    structure away once it's been flattened into text for the LLM.

    Deliberately a separate function from `render_evidence` rather than
    folded into it: `render_evidence` needs a `db` session (to resolve
    citation metadata for chunks outside `context_chunks`) and is called
    from every retrieval path including plain `vector`-classified questions
    that never have graph relations at all; this only needs the relations
    themselves and is skipped entirely when there aren't any.
    """
    all_relations = list(graph_relations)
    if community_drilldowns:
        all_relations += [
            relation for _, relations in community_drilldowns for relation in relations
        ]

    nodes_by_id: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []
    seen_edges: set[tuple[str, str, str]] = set()
    for relation in all_relations:
        source_id = f"{relation.source_type.value}:{relation.source_name}"
        target_id = f"{relation.target_type.value}:{relation.target_name}"
        nodes_by_id.setdefault(
            source_id,
            GraphNode(
                id=source_id, name=relation.source_name, entity_type=relation.source_type.value
            ),
        )
        nodes_by_id.setdefault(
            target_id,
            GraphNode(
                id=target_id, name=relation.target_name, entity_type=relation.target_type.value
            ),
        )

        edge_key = (source_id, relation.relation_type, target_id)
        if edge_key in seen_edges:
            continue
        seen_edges.add(edge_key)
        edges.append(
            GraphEdge(
                source=source_id,
                target=target_id,
                relation_type=relation.relation_type,
                chunk_id=uuid.UUID(relation.chunk_id),
            )
        )

    return GraphEvidence(nodes=list(nodes_by_id.values()), edges=edges)


def render_evidence(
    db: Session,
    context_chunks: list[Chunk],
    graph_relations: list[ProvenancedRelationEdge],
    community_drilldowns: list[tuple[CommunityWithEmbedding, list[ProvenancedRelationEdge]]],
) -> tuple[list[str], list[str], list[Citation]]:
    """Turns accumulated retrieval results into the three things
    `answer_generation.generate_answer` and `QueryResponse` need:
    `graph_facts`, `community_context`, and the final `citations` list.
    Fetches citation metadata for any chunk a graph/community relation
    points at that wasn't already in `context_chunks`.
    """
    citations_by_chunk_id = {
        chunk.id: Citation(
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            document_filename=chunk.document.filename,
            clause_number=chunk.clause_number,
            path=str(chunk.path),
        )
        for chunk in context_chunks
    }

    all_found_relations = graph_relations + [
        relation for _, relations in community_drilldowns for relation in relations
    ]
    new_chunk_ids = {
        uuid.UUID(relation.chunk_id)
        for relation in all_found_relations
        if uuid.UUID(relation.chunk_id) not in citations_by_chunk_id
    }
    if new_chunk_ids:
        for chunk in db.scalars(select(Chunk).where(Chunk.id.in_(new_chunk_ids))):
            citations_by_chunk_id[chunk.id] = Citation(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                document_filename=chunk.document.filename,
                clause_number=chunk.clause_number,
                path=str(chunk.path),
            )

    def _format_relation(relation: ProvenancedRelationEdge) -> str | None:
        citation = citations_by_chunk_id.get(uuid.UUID(relation.chunk_id))
        if citation is None:
            return None
        label = citation.clause_number or relation.chunk_id
        return (
            f"[{label}] {relation.source_type.value}:{relation.source_name!r} "
            f"--{relation.relation_type}--> {relation.target_type.value}:{relation.target_name!r}"
        )

    graph_facts = [
        fact for relation in graph_relations if (fact := _format_relation(relation)) is not None
    ]

    community_context = []
    for community, relations in community_drilldowns:
        community_context.append(f"Theme: {community.title} — {community.summary}")
        community_context.extend(
            fact for relation in relations if (fact := _format_relation(relation)) is not None
        )

    citations = [citations_by_chunk_id[chunk.id] for chunk in context_chunks] + [
        citations_by_chunk_id[chunk_id] for chunk_id in new_chunk_ids
    ]
    return graph_facts, community_context, citations
