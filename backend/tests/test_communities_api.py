import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import community_summary, graph_store
from app.services.ontology import EntityType, RelationType
from app.tasks.celery_app import celery_app


def _infra_available() -> bool:
    try:
        driver = graph_store.get_neo4j_driver()
        driver.verify_connectivity()
        driver.close()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _infra_available(), reason="requires docker compose up (neo4j)")


@pytest.fixture(autouse=True, scope="module")
def _eager_celery():
    """`task_store_eager_result` (unlike test_extraction_api.py's fixture) is
    needed here specifically: this test polls `GET /.../status/{task_id}`
    via `AsyncResult`, which only finds anything in eager mode if results are
    explicitly stored — test_extraction_api.py never needed this because it
    checks task outcome via the Document row the task itself updated.
    """
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    celery_app.conf.task_store_eager_result = True
    yield
    celery_app.conf.task_always_eager = False
    celery_app.conf.task_eager_propagates = False
    celery_app.conf.task_store_eager_result = False


@pytest.fixture(autouse=True)
def _mock_summarizer(monkeypatch):
    """Real Neo4j, real Leiden partitioning — only the LLM summary call is
    faked, so this test needs no real Gemini key.
    """

    def _fake_summarize(members, relations, client=None):
        names = ", ".join(name for _, name in members)
        return community_summary.CommunitySummary(title="Fake Title", summary=f"About {names}")

    monkeypatch.setattr(community_summary, "summarize_community", _fake_summarize)


def _unique_name(prefix: str) -> str:
    return f"{prefix} {uuid.uuid4().hex[:8]}"


def test_detect_communities_end_to_end():
    name_a = _unique_name("API Test A")
    name_b = _unique_name("API Test B")
    driver = graph_store.get_neo4j_driver()
    try:
        a_id = graph_store.upsert_entity(driver, EntityType.CONTROL, name_a, [1.0])
        b_id = graph_store.upsert_entity(driver, EntityType.RISK, name_b, [1.0])
        graph_store.create_relation(
            driver,
            a_id,
            b_id,
            RelationType.APPLIES_TO,
            chunk_id=str(uuid.uuid4()),
            document_id=str(uuid.uuid4()),
        )
    finally:
        driver.close()

    client = TestClient(app)

    detect_response = client.post("/graph/communities/detect")
    assert detect_response.status_code == 202
    task_id = detect_response.json()["task_id"]

    status = client.get(f"/graph/communities/status/{task_id}").json()
    assert status["state"] == "SUCCESS"
    assert status["result"]["communities_created"] >= 1

    communities = client.get("/graph/communities").json()["communities"]
    matching = [c for c in communities if name_a in c["summary"]]
    assert len(matching) == 1
    assert name_b in matching[0]["summary"]


def test_status_for_unknown_task_id_is_pending():
    response = TestClient(app).get(f"/graph/communities/status/{uuid.uuid4()}")
    assert response.json()["state"] == "PENDING"
