import uuid

import pytest

from app.services import graph_store
from app.services.ontology import EntityType, RelationType


def _infra_available() -> bool:
    try:
        driver = graph_store.get_neo4j_driver()
        driver.verify_connectivity()
        driver.close()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _infra_available(), reason="requires docker compose up (neo4j)"
)


@pytest.fixture
def driver():
    d = graph_store.get_neo4j_driver()
    graph_store.ensure_constraints(d)
    yield d
    d.close()


def _unique_name(prefix: str) -> str:
    """Every test uses a fresh random name — this project doesn't clean up
    test data between runs (same convention as test_documents_api.py etc.),
    so uniqueness avoids collisions with entities from earlier test runs.
    """
    return f"{prefix} {uuid.uuid4().hex[:8]}"


def test_upsert_entity_is_idempotent(driver):
    name = _unique_name("Test Entity")

    first_id = graph_store.upsert_entity(driver, EntityType.CONTROL, name, [1.0, 0.0])
    second_id = graph_store.upsert_entity(driver, EntityType.CONTROL, name, [9.0, 9.0])

    assert first_id == second_id


def test_upsert_entity_keeps_first_embedding_on_repeat_upsert(driver):
    name = _unique_name("Test Entity")
    graph_store.upsert_entity(driver, EntityType.CONTROL, name, [1.0, 0.0])
    graph_store.upsert_entity(driver, EntityType.CONTROL, name, [9.0, 9.0])

    matching = [e for e in graph_store.fetch_all_entities(driver) if e[0] == name]

    assert len(matching) == 1
    assert matching[0][2] == [1.0, 0.0]


def test_same_name_different_type_creates_separate_nodes(driver):
    name = _unique_name("Ambiguous Name")

    control_id = graph_store.upsert_entity(driver, EntityType.CONTROL, name, [1.0])
    risk_id = graph_store.upsert_entity(driver, EntityType.RISK, name, [1.0])

    assert control_id != risk_id


def test_create_relation_and_fetch_document_graph(driver):
    document_id = str(uuid.uuid4())
    chunk_id = str(uuid.uuid4())
    source_name = _unique_name("Source Entity")
    target_name = _unique_name("Target Entity")

    source_id = graph_store.upsert_entity(driver, EntityType.CONTROL, source_name, [1.0])
    target_id = graph_store.upsert_entity(driver, EntityType.RISK, target_name, [1.0])
    graph_store.create_relation(
        driver,
        source_id,
        target_id,
        RelationType.APPLIES_TO,
        chunk_id=chunk_id,
        document_id=document_id,
    )

    rows = graph_store.fetch_document_graph(driver, document_id)

    assert len(rows) == 1
    assert rows[0]["source_name"] == source_name
    assert rows[0]["target_name"] == target_name
    assert rows[0]["relation_type"] == "APPLIES_TO"
    assert rows[0]["chunk_id"] == chunk_id
