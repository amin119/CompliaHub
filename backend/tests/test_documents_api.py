import io

import pytest
from docx import Document as DocxDocument
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.db import engine
from app.main import app
from app.services import storage
from app.tasks.celery_app import celery_app


def _infra_available() -> bool:
    """Checks Postgres has the migration applied (not just that it's up) and
    that MinIO is reachable. If either fails, this test module is skipped
    rather than failing — it needs the real docker-compose stack, which CI
    doesn't run yet.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1 FROM documents LIMIT 1"))
        storage.get_minio_client().list_buckets()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _infra_available(),
    reason="requires docker compose up (postgres+redis+minio) with migrations applied",
)


@pytest.fixture(autouse=True, scope="module")
def _eager_celery():
    # Runs the parse->chunk chain synchronously in-process, so the test can
    # assert on the final state without a live worker or polling.
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    yield
    celery_app.conf.task_always_eager = False
    celery_app.conf.task_eager_propagates = False


def _sample_docx_bytes() -> bytes:
    buf = io.BytesIO()
    doc = DocxDocument()
    doc.add_heading("Sample Standard", level=1)
    doc.add_heading("A.1 Test Clause", level=2)
    doc.add_paragraph("This is a test clause body.")
    doc.save(buf)
    return buf.getvalue()


def test_upload_document_processes_end_to_end():
    client = TestClient(app)
    data = _sample_docx_bytes()
    docx_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    response = client.post("/documents", files={"file": ("sample.docx", data, docx_type)})
    assert response.status_code == 201
    document_id = response.json()["id"]
    # Enqueued but not yet processed at response time — that's correct even
    # in eager mode, since the chain runs inside apply_async(), which happens
    # after this response body was already built.
    assert response.json()["status"] == "pending"

    status_response = client.get(f"/documents/{document_id}")
    assert status_response.json()["status"] == "ready"

    chunks = client.get(f"/documents/{document_id}/chunks").json()
    assert len(chunks) == 1
    assert chunks[0]["clause_number"] == "A.1"


def test_upload_same_file_twice_is_idempotent():
    client = TestClient(app)
    data = _sample_docx_bytes()

    files = {"file": ("sample.docx", data, "application/octet-stream")}
    first = client.post("/documents", files=files)
    second = client.post("/documents", files=files)

    assert first.json()["id"] == second.json()["id"]
