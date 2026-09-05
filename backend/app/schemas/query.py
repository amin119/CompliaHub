import uuid

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str
    top_k: int = 5
    # Phase 5 Part 2: omit for a new conversation; pass back the id a prior
    # response returned to continue it (only meaningful for `agent`-
    # classified questions — see docs/phase-5-agentic-loop.md for why
    # vector/graph-classified turns don't build conversation memory).
    conversation_id: str | None = None


class Citation(BaseModel):
    chunk_id: uuid.UUID
    # Phase 6: without this, the frontend has no way to fetch a citation's
    # full clause text (GET /documents/{id}/chunks needs the document id,
    # not just its filename) — added specifically to make "clickable
    # citations" a real feature instead of a metadata-only stub.
    document_id: uuid.UUID
    document_filename: str
    clause_number: str | None
    path: str


class GraphNode(BaseModel):
    # Stable across a response's own nodes/edges (f"{entity_type}:{name}") —
    # not a Neo4j internal id, so it's meaningless outside this one response.
    id: str
    name: str
    entity_type: str


class GraphEdge(BaseModel):
    source: str
    target: str
    relation_type: str
    # None when a relation came from a community drill-down whose own
    # provenance chunk wasn't otherwise resolved — same "best effort"
    # provenance as render_evidence's graph_facts formatting.
    chunk_id: uuid.UUID | None = None


class GraphEvidence(BaseModel):
    """Phase 6 Part 2: the structural form of whatever local/global search
    found — previously `retrieval.render_evidence` only ever turned this
    into prompt strings and threw it away. Empty for vector-only answers,
    which never touch the graph at all.
    """

    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation]
    conversation_id: str | None = None
    graph_evidence: GraphEvidence = Field(default_factory=GraphEvidence)
    # Phase 7: `query_classifier.classify_query`'s routing decision, this
    # turn's wall-clock latency, and (agent-classified turns only) how many
    # retrieve/critique/rewrite rounds it took — all three were previously
    # computed internally and silently discarded before reaching this
    # response (see docs/phase-7-evaluation.md). Additive and optional so
    # existing frontend consumers built against the old shape don't break.
    category: str | None = None
    latency_ms: float | None = None
    iteration_count: int | None = None


class ConversationTurn(BaseModel):
    question: str
    answer: str


class ConversationResponse(BaseModel):
    conversation_id: str
    turns: list[ConversationTurn]
