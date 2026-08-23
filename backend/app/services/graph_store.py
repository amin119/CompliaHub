from typing import NamedTuple

from neo4j import Driver, GraphDatabase

from app.core.config import get_settings
from app.services.ontology import EntityType, RelationType


class RelationEdge(NamedTuple):
    """One relation, corpus-wide — the shape `fetch_all_relations` returns.
    A plain tuple would work but with five positional fields of overlapping
    types (str, EntityType, str, str, EntityType) it's too easy to transpose
    two by accident; a NamedTuple makes each field's meaning explicit at
    every call site that consumes it (community_detection, community_summary).
    """

    source_name: str
    source_type: EntityType
    relation_type: str
    target_name: str
    target_type: EntityType


class ProvenancedRelationEdge(NamedTuple):
    """Same shape as `RelationEdge`, plus the `chunk_id`/`document_id` every
    relation already carries — needed wherever the caller has to cite back
    to an exact clause (Phase 4's local search), unlike `RelationEdge`'s
    consumers (community detection/summarization), which only care about
    graph connectivity, never provenance.
    """

    source_name: str
    source_type: EntityType
    relation_type: str
    target_name: str
    target_type: EntityType
    chunk_id: str
    document_id: str


def get_neo4j_driver() -> Driver:
    settings = get_settings()
    return GraphDatabase.driver(
        settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
    )


def ensure_constraints(driver: Driver) -> None:
    """One uniqueness constraint per entity-type *label* on `canonical_name`
    — not a single composite `(entity_type, canonical_name)` constraint.
    Composite/node-key constraints need Neo4j Enterprise; we're on
    `neo4j:5-community`. Using `EntityType` as the node label instead of a
    property means each label's own single-property constraint achieves the
    same effect (two `Control` nodes can't share a name, but a `Control` and
    a `Risk` can) without needing the Enterprise-only feature.
    """
    with driver.session() as session:
        for entity_type in EntityType:
            session.run(
                f"CREATE CONSTRAINT IF NOT EXISTS FOR (e:{entity_type.value}) "
                "REQUIRE e.canonical_name IS UNIQUE"
            )


def upsert_entity(
    driver: Driver, entity_type: EntityType, canonical_name: str, embedding: list[float]
) -> str:
    """`MERGE` by `canonical_name` within the `entity_type` label — creates
    the node if it doesn't exist, or returns the existing one, so calling
    this twice with the same (type, name) never creates a duplicate.
    Returns the node's Neo4j element id, for use in `create_relation`.
    """
    query = (
        f"MERGE (e:{entity_type.value} {{canonical_name: $name}}) "
        "ON CREATE SET e.embedding = $embedding "
        "RETURN elementId(e) AS node_id"
    )
    with driver.session() as session:
        record = session.run(query, name=canonical_name, embedding=embedding).single()
        return record["node_id"]


def create_relation(
    driver: Driver,
    from_id: str,
    to_id: str,
    relation_type: RelationType,
    chunk_id: str,
    document_id: str,
) -> None:
    """One edge per extraction mention — if the same relation is
    independently mentioned in multiple chunks, this creates multiple
    parallel edges rather than merging into one edge with an array property,
    so "how many places support this claim" falls out for free later
    (useful for Phase 7's evaluation/confidence work).
    """
    query = (
        "MATCH (a), (b) WHERE elementId(a) = $from_id AND elementId(b) = $to_id "
        f"CREATE (a)-[r:{relation_type.value.upper()} "
        "{chunk_id: $chunk_id, document_id: $document_id}]->(b)"
    )
    with driver.session() as session:
        session.run(
            query, from_id=from_id, to_id=to_id, chunk_id=chunk_id, document_id=document_id
        )


def fetch_all_entities(driver: Driver) -> list[tuple[str, EntityType, list[float]]]:
    """Pulls every entity currently in the graph — feeds entity resolution's
    "compare new candidates against what already exists" step. Fine at this
    project's scale (hundreds-to-low-thousands of entities); revisit only if
    this becomes a real bottleneck at Phase 8 scale.
    """
    entity_labels = [entity_type.value for entity_type in EntityType]
    query = (
        "MATCH (e) WHERE any(label IN labels(e) WHERE label IN $entity_labels) "
        "RETURN labels(e) AS node_labels, e.canonical_name AS name, e.embedding AS embedding"
    )
    with driver.session() as session:
        records = session.run(query, entity_labels=entity_labels)
        return [
            (record["name"], EntityType(record["node_labels"][0]), record["embedding"])
            for record in records
        ]


def fetch_document_graph(driver: Driver, document_id: str) -> list[dict]:
    """Every relation extracted from this specific document, with its
    endpoint entities — the hands-on way to see extraction actually worked,
    same spirit as Phase 1's `/documents/{id}/chunks`.
    """
    query = (
        "MATCH (a)-[r]->(b) WHERE r.document_id = $document_id "
        "RETURN labels(a)[0] AS source_type, a.canonical_name AS source_name, "
        "type(r) AS relation_type, r.chunk_id AS chunk_id, "
        "labels(b)[0] AS target_type, b.canonical_name AS target_name"
    )
    with driver.session() as session:
        return [dict(record) for record in session.run(query, document_id=document_id)]


def fetch_all_relations(driver: Driver) -> list[RelationEdge]:
    """Every relation in the graph, corpus-wide — no `document_id` filter,
    unlike `fetch_document_graph`. Community detection needs the whole
    corpus's connectivity (a community spanning ISO 27001 *and* ISO 42001
    entities is exactly the interesting case for cross-standard gap
    analysis), not one document's slice of it.
    """
    entity_labels = [entity_type.value for entity_type in EntityType]
    query = (
        "MATCH (a)-[r]->(b) "
        "WHERE any(label IN labels(a) WHERE label IN $entity_labels) "
        "AND any(label IN labels(b) WHERE label IN $entity_labels) "
        "RETURN a.canonical_name AS source_name, labels(a)[0] AS source_type, "
        "type(r) AS relation_type, "
        "b.canonical_name AS target_name, labels(b)[0] AS target_type"
    )
    with driver.session() as session:
        records = session.run(query, entity_labels=entity_labels)
        return [
            RelationEdge(
                source_name=record["source_name"],
                source_type=EntityType(record["source_type"]),
                relation_type=record["relation_type"],
                target_name=record["target_name"],
                target_type=EntityType(record["target_type"]),
            )
            for record in records
        ]


def clear_communities(driver: Driver) -> None:
    """Deletes every `Community` node (and its `IN_COMMUNITY` edges, via
    `DETACH DELETE`). Communities are always fully recomputed from scratch,
    never updated incrementally, so every detection run starts from a clean
    slate — fine at this project's scale, and far simpler than reconciling
    an existing partition against a changed graph.
    """
    with driver.session() as session:
        session.run("MATCH (c:Community) DETACH DELETE c")


def create_community(
    driver: Driver,
    community_id: str,
    title: str,
    summary: str,
    members: list[tuple[EntityType, str]],
    summary_embedding: list[float],
) -> None:
    """Creates one `Community` node and links every member entity to it via
    `IN_COMMUNITY`. `community_id` is an application-level UUID (like
    `Document`/`Chunk` ids), not Neo4j's own `elementId` — stable to
    reference from the API layer.

    Members are identified by `(entity_type, canonical_name)`, the same pair
    `upsert_entity` uses, since `canonical_name` is only unique *within* an
    entity-type label, not globally.

    `summary_embedding` (Phase 4 Part 2) is what makes global search
    possible: comparing a question's embedding directly against entity-name
    embeddings is a weak match (see docs/phase-4-graph-retrieval.md), but a
    community summary is itself a full sentence, so question-vs-summary
    cosine similarity is the same well-behaved comparison Phase 2 already
    relies on for chunk retrieval.
    """
    with driver.session() as session:
        session.run(
            "CREATE (c:Community {id: $id, title: $title, summary: $summary, "
            "entity_count: $entity_count, summary_embedding: $summary_embedding})",
            id=community_id,
            title=title,
            summary=summary,
            entity_count=len(members),
            summary_embedding=summary_embedding,
        )
        for entity_type, name in members:
            session.run(
                f"MATCH (e:{entity_type.value} {{canonical_name: $name}}), "
                "(c:Community {id: $community_id}) "
                "CREATE (e)-[:IN_COMMUNITY]->(c)",
                name=name,
                community_id=community_id,
            )


def fetch_communities(driver: Driver) -> list[dict]:
    """Every community currently in the graph, largest first — the
    results-inspection endpoint, same spirit as `fetch_document_graph`.
    Deliberately excludes `summary_embedding` (see
    `fetch_community_embeddings` for that) — a 1024-float vector has no
    place in a human-facing inspection response.
    """
    query = (
        "MATCH (c:Community) RETURN c.id AS id, c.title AS title, "
        "c.summary AS summary, c.entity_count AS entity_count "
        "ORDER BY c.entity_count DESC"
    )
    with driver.session() as session:
        return [dict(record) for record in session.run(query)]


class CommunityWithEmbedding(NamedTuple):
    """A community plus its summary embedding — the shape global search's
    similarity ranking needs, distinct from `fetch_communities`'s
    embedding-free dicts (the API inspection response).
    """

    id: str
    title: str
    summary: str
    embedding: list[float]


def fetch_community_embeddings(driver: Driver) -> list[CommunityWithEmbedding]:
    """Every community with its summary embedding — feeds global search's
    brute-force cosine ranking (`global_search.find_similar_communities`),
    same "fine at this project's scale" reasoning as
    `entity_resolution.py`'s existing brute-force entity comparison.
    """
    query = (
        "MATCH (c:Community) RETURN c.id AS id, c.title AS title, "
        "c.summary AS summary, c.summary_embedding AS embedding"
    )
    with driver.session() as session:
        return [
            CommunityWithEmbedding(
                id=record["id"],
                title=record["title"],
                summary=record["summary"],
                embedding=record["embedding"],
            )
            for record in session.run(query)
        ]


def fetch_community_members(driver: Driver, community_id: str) -> list[tuple[EntityType, str]]:
    """Every entity belonging to one community — global search's "drill
    down" step: once a community's summary matches the question, pull its
    actual member entities so `fetch_relations_touching` can surface
    citable specifics, not just the synthesized summary text.
    """
    query = (
        "MATCH (e)-[:IN_COMMUNITY]->(c:Community {id: $community_id}) "
        "RETURN labels(e)[0] AS entity_type, e.canonical_name AS name"
    )
    with driver.session() as session:
        records = session.run(query, community_id=community_id)
        return [(EntityType(record["entity_type"]), record["name"]) for record in records]


def fetch_entities_for_chunks(driver: Driver, chunk_ids: list[str]) -> set[tuple[EntityType, str]]:
    """Every entity touched by any of the given chunks — the chunk-to-graph
    pivot point for local search: rather than a new, separately-tuned
    embedding-similarity path to find "relevant" entities for a question,
    local search reuses Phase 2's already-reranked chunks and asks "which
    entities did *these* mention," via the `chunk_id` provenance every
    relation already carries.
    """
    if not chunk_ids:
        return set()

    entity_labels = [entity_type.value for entity_type in EntityType]
    query = (
        "MATCH (a)-[r]->(b) WHERE r.chunk_id IN $chunk_ids "
        "AND any(label IN labels(a) WHERE label IN $entity_labels) "
        "AND any(label IN labels(b) WHERE label IN $entity_labels) "
        "RETURN a.canonical_name AS a_name, labels(a)[0] AS a_type, "
        "b.canonical_name AS b_name, labels(b)[0] AS b_type"
    )
    with driver.session() as session:
        records = session.run(query, chunk_ids=chunk_ids, entity_labels=entity_labels)
        keys: set[tuple[EntityType, str]] = set()
        for record in records:
            keys.add((EntityType(record["a_type"]), record["a_name"]))
            keys.add((EntityType(record["b_type"]), record["b_name"]))
        return keys


def fetch_relations_touching(
    driver: Driver, entity_keys: list[tuple[EntityType, str]]
) -> list[ProvenancedRelationEdge]:
    """One hop's worth of relations from a frontier of entities, in either
    direction — local search's BFS expansion primitive (see
    `app/services/local_search.py`). Matches each seed by `(label,
    canonical_name)` via `UNWIND`, one Cypher round-trip for the whole
    frontier rather than one per entity.

    Direction-agnostic on purpose: local search doesn't care whether a
    neighboring entity was reached via an outgoing or incoming edge, only
    that it's connected. `startNode`/`endNode` (not which side matched the
    seed) determine each returned edge's actual source/target, so directed
    provenance is preserved regardless of which side of `-[r]-` matched.
    """
    if not entity_keys:
        return []

    entity_labels = [entity_type.value for entity_type in EntityType]
    keys_param = [{"entity_type": key[0].value, "name": key[1]} for key in entity_keys]
    query = (
        "UNWIND $keys AS key "
        "MATCH (e) WHERE key.entity_type IN labels(e) AND e.canonical_name = key.name "
        "MATCH (e)-[r]-(other) "
        "WHERE any(label IN labels(other) WHERE label IN $entity_labels) "
        "WITH DISTINCT r "
        "RETURN labels(startNode(r))[0] AS source_type, "
        "startNode(r).canonical_name AS source_name, "
        "type(r) AS relation_type, "
        "labels(endNode(r))[0] AS target_type, endNode(r).canonical_name AS target_name, "
        "r.chunk_id AS chunk_id, r.document_id AS document_id"
    )
    with driver.session() as session:
        records = session.run(query, keys=keys_param, entity_labels=entity_labels)
        return [
            ProvenancedRelationEdge(
                source_name=record["source_name"],
                source_type=EntityType(record["source_type"]),
                relation_type=record["relation_type"],
                target_name=record["target_name"],
                target_type=EntityType(record["target_type"]),
                chunk_id=record["chunk_id"],
                document_id=record["document_id"],
            )
            for record in records
        ]


def fetch_relations_by_type(
    driver: Driver,
    relation_type: RelationType,
    entity_key: tuple[EntityType, str] | None = None,
) -> list[ProvenancedRelationEdge]:
    """All relations of one type, optionally touching one specific entity
    (either side) — a single, general query shape that covers two of the
    roadmap's three named Cypher templates: "what references X" is
    `relation_type=REFERENCES, entity_key=X`; "cross-standard mapping
    lookup" is `relation_type=MAPS_TO` with no entity filter for a
    corpus-wide view, or filtered to one standard.
    """
    query = (
        "MATCH (a)-[r]->(b) WHERE type(r) = $relation_type "
        "AND any(label IN labels(a) WHERE label IN $entity_labels) "
        "AND any(label IN labels(b) WHERE label IN $entity_labels) "
    )
    params: dict = {
        "relation_type": relation_type.value.upper(),
        "entity_labels": [entity_type.value for entity_type in EntityType],
    }
    if entity_key is not None:
        query += (
            "AND ((labels(a)[0] = $key_type AND a.canonical_name = $key_name) "
            "OR (labels(b)[0] = $key_type AND b.canonical_name = $key_name)) "
        )
        params["key_type"] = entity_key[0].value
        params["key_name"] = entity_key[1]
    query += (
        "RETURN a.canonical_name AS source_name, labels(a)[0] AS source_type, "
        "type(r) AS relation_type, "
        "b.canonical_name AS target_name, labels(b)[0] AS target_type, "
        "r.chunk_id AS chunk_id, r.document_id AS document_id"
    )
    with driver.session() as session:
        records = session.run(query, **params)
        return [
            ProvenancedRelationEdge(
                source_name=record["source_name"],
                source_type=EntityType(record["source_type"]),
                relation_type=record["relation_type"],
                target_name=record["target_name"],
                target_type=EntityType(record["target_type"]),
                chunk_id=record["chunk_id"],
                document_id=record["document_id"],
            )
            for record in records
        ]
