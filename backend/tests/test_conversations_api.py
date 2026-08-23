import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.checkpointer import close_checkpointer, open_checkpointer
from app.core.db import engine
from app.main import app
from app.services import agent, answer_generation, query_classifier, retrieval
from app.services.query_classifier import QueryCategory, QueryClassification


def _infra_available() -> bool:
    """This module's whole point is exercising the *real* Postgres
    checkpointer end to end — retrieval itself is mocked (already covered
    by test_agent.py/test_query_api.py), Neo4j/Qdrant aren't needed here.

    Deliberately checks connectivity via SQLAlchemy's own `engine`, *not*
    by opening/closing the checkpointer's `ConnectionPool` — confirmed live
    that a `psycopg_pool.ConnectionPool`, once closed, can never be
    reopened (`PoolClosed: pool has already been opened/closed and cannot
    be reused`). The module-level `_checkpointer_lifecycle` fixture below
    is the *only* place that opens/closes it, exactly once.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _infra_available(), reason="requires docker compose up (postgres)"
)


@pytest.fixture(autouse=True, scope="module")
def _checkpointer_lifecycle():
    """`TestClient(app)` without a `with` block never triggers the app's
    own lifespan (confirmed live — see docs/phase-5-agentic-loop.md), so
    tests that exercise the real `/query/conversations/*` endpoints have to
    open/close the pool themselves, same as the real app's lifespan does.
    """
    open_checkpointer()
    yield
    close_checkpointer()


@pytest.fixture(autouse=True)
def _mock_agent_dependencies(monkeypatch):
    """Real checkpointer, real `agent.run_agent` control flow — only
    retrieval and the Gemini calls are faked, so this needs no live
    Neo4j/Qdrant/Gemini key.
    """
    monkeypatch.setattr(
        query_classifier,
        "classify_query",
        lambda question, client=None: QueryClassification(category=QueryCategory.AGENT),
    )
    monkeypatch.setattr(retrieval, "vector_search", lambda db, question, top_k: ([], [0.1]))
    monkeypatch.setattr(retrieval, "local_search_facts", lambda driver, context_chunks: [])
    monkeypatch.setattr(retrieval, "global_search_context", lambda driver, query_vector: [])
    monkeypatch.setattr(
        answer_generation,
        "generate_answer",
        lambda question, chunks, graph_facts=None, community_context=None: f"answer to {question}",
    )

    def _fake_gemini(api_key, model, system_prompt, contents, schema):
        if schema is agent.CritiqueResult:
            return agent.CritiqueResult(sufficient=True)
        if schema is agent.CondensedQuestion:
            return agent.CondensedQuestion(standalone_question=contents)
        raise AssertionError(f"unexpected schema {schema}")

    monkeypatch.setattr(agent, "_call_gemini_structured", _fake_gemini)


def test_conversation_persists_across_separate_query_requests_via_real_postgres():
    client = TestClient(app)

    first = client.post("/query", json={"question": "What does ISO 27001 say about access?"})
    assert first.status_code == 200
    conversation_id = first.json()["conversation_id"]
    assert conversation_id is not None

    second = client.post(
        "/query", json={"question": "What about GDPR?", "conversation_id": conversation_id}
    )
    assert second.status_code == 200
    assert second.json()["conversation_id"] == conversation_id

    inspect_response = client.get(f"/query/conversations/{conversation_id}")
    assert inspect_response.status_code == 200
    turns = inspect_response.json()["turns"]
    assert len(turns) == 2
    assert turns[0]["question"] == "What does ISO 27001 say about access?"
    assert turns[1]["question"] == "What about GDPR?"

    delete_response = client.delete(f"/query/conversations/{conversation_id}")
    assert delete_response.status_code == 204

    after_delete = client.get(f"/query/conversations/{conversation_id}")
    assert after_delete.status_code == 404


def test_get_unknown_conversation_returns_404():
    client = TestClient(app)
    response = client.get("/query/conversations/never-existed-at-all")
    assert response.status_code == 404
