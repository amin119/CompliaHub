from neo4j import Driver, GraphDatabase

from app.core.config import get_settings
from app.services.ontology import EntityType, RelationType


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
