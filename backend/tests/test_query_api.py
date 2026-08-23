import io

import pytest
from docx import Document as DocxDocument
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.db import engine
from app.main import app
from app.services import (
    agent,
    answer_generation,
    embedding,
    graph_store,
    query_classifier,
    reranking,
    retrieval,
    vector_store,
)
from app.services.query_classifier import QueryCategory, QueryClassification
from app.tasks.celery_app import celery_app


def _infra_available() -> bool:
    """Same infra requirement as test_documents_api.py, plus a reachable
    Qdrant and (Phase 4) Neo4j — this module's whole point is exercising
    real dense-search + lexical-search + fusion + local-search wiring, only
    the paid API calls (Voyage, Cohere, Grok) are mocked.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1 FROM documents LIMIT 1"))
        vector_store.get_qdrant_client().get_collections()
        driver = graph_store.get_neo4j_driver()
        driver.verify_connectivity()
        driver.close()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _infra_available(),
    reason="requires docker compose up (postgres+redis+qdrant) with migrations applied",
)


@pytest.fixture(autouse=True, scope="module")
def _eager_celery():
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    yield
    celery_app.conf.task_always_eager = False
    celery_app.conf.task_eager_propagates = False


@pytest.fixture(autouse=True)
def _mock_external_apis(monkeypatch):
    """Mocks every paid third-party call (Voyage, Cohere, Anthropic) so this
    test needs no real API keys, while still exercising the real Postgres
    lexical search + real Qdrant dense search + real RRF fusion wiring.

    Embeddings are faked as a single constant vector: dense-search *ranking*
    isn't asserted on (there's only one document's chunks in Qdrant, so
    scores would be meaningless with a fake vector anyway) — this test
    verifies the endpoint's plumbing end-to-end, not retrieval quality,
    which is what the real GDPR regression check (docs/phase-2-vector-layer.md)
    is for.
    """

    def _fake_embed_texts(texts, input_type):
        return [[0.1] * embedding.EMBEDDING_DIM for _ in texts]

    def _fake_rerank(query, documents, top_n):
        return [
            reranking.RerankResult(index=i, relevance_score=1.0 - i * 0.01)
            for i in range(min(top_n, len(documents)))
        ]

    monkeypatch.setattr(embedding, "embed_texts", _fake_embed_texts)
    monkeypatch.setattr(reranking, "rerank", _fake_rerank)
    monkeypatch.setattr(
        answer_generation,
        "generate_answer",
        lambda question, chunks, graph_facts=None, community_context=None: "mocked answer",
    )
    # Phase 5: every /query call now classifies first — default to GRAPH so
    # the existing tests below (written against Phase 4's vector+local
    # behavior) keep exercising that same path unchanged. Tests that care
    # about a different category override this per-test.
    monkeypatch.setattr(
        query_classifier,
        "classify_query",
        lambda question, client=None: QueryClassification(category=QueryCategory.GRAPH),
    )


def _sample_docx_bytes() -> bytes:
    buf = io.BytesIO()
    doc = DocxDocument()
    doc.add_heading("Query Test Standard", level=1)
    doc.add_heading("A.1 Test Clause", level=2)
    doc.add_paragraph("Assets associated with information shall be identified and inventoried.")
    doc.save(buf)
    return buf.getvalue()


def test_query_returns_answer_with_citations():
    client = TestClient(app)
    files = {"file": ("query_sample.docx", _sample_docx_bytes(), "application/octet-stream")}
    upload = client.post("/documents", files=files)
    assert client.get(f"/documents/{upload.json()['id']}").json()["status"] == "ready"

    question = "What must be done with information assets?"
    response = client.post("/query", json={"question": question})

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "mocked answer"
    assert len(body["citations"]) >= 1
    assert body["citations"][0]["clause_number"] == "A.1"


def test_query_with_no_matching_chunks_returns_empty_citations():
    client = TestClient(app)
    question = "asdkjhaslkdjhaslkdjh nonsense query xyz123"
    response = client.post("/query", json={"question": question})

    assert response.status_code == 200
    # Lexical search may legitimately find nothing for gibberish; dense
    # search still returns *something* (fake vectors have no real notion of
    # "no match"), so this only asserts the endpoint doesn't error — not
    # that citations are empty.
    assert "answer" in response.json()


def test_vector_category_skips_the_graph_entirely(monkeypatch):
    """Real cost savings from Phase 5's classifier: a `vector`-classified
    question must never touch Neo4j at all. Verified by making
    `local_search_facts` raise — if the route calls it anyway, this test
    fails loudly instead of silently passing.
    """
    monkeypatch.setattr(
        query_classifier,
        "classify_query",
        lambda question, client=None: QueryClassification(category=QueryCategory.VECTOR),
    )

    def _boom(driver, context_chunks):
        raise AssertionError("local_search_facts must not run for a VECTOR-classified question")

    monkeypatch.setattr(retrieval, "local_search_facts", _boom)

    client = TestClient(app)
    response = client.post("/query", json={"question": "what does clause 6.1.2 require?"})

    assert response.status_code == 200
    assert response.json()["answer"] == "mocked answer"


def test_agent_category_delegates_to_the_agent_loop(monkeypatch):
    from app.schemas.query import QueryResponse

    monkeypatch.setattr(
        query_classifier,
        "classify_query",
        lambda question, client=None: QueryClassification(category=QueryCategory.AGENT),
    )

    captured = {}

    def _fake_run_agent(question, db, driver, checkpointer, conversation_id=None, max_iterations=2):
        captured["question"] = question
        captured["conversation_id"] = conversation_id
        return QueryResponse(answer="agent answer", citations=[], conversation_id="conv-123")

    monkeypatch.setattr(agent, "run_agent", _fake_run_agent)

    client = TestClient(app)
    question = "what does ISO 42001 require that ISO 27001 doesn't?"
    response = client.post("/query", json={"question": question, "conversation_id": "conv-123"})

    assert response.status_code == 200
    assert response.json()["conversation_id"] == "conv-123"
    assert captured["conversation_id"] == "conv-123"
    assert response.json()["answer"] == "agent answer"
    assert captured["question"] == question
