import uuid

import pytest
from sqlalchemy import text

from app.core.db import SessionLocal, engine
from app.models.document import Document
from app.tasks.pipeline import pipeline_stage


def _infra_available() -> bool:
    """`pipeline_stage` talks to a real Postgres session — this needs the
    same live docker stack as the other integration tests.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1 FROM documents LIMIT 1"))
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _infra_available(),
    reason="requires docker compose up (postgres) with migrations applied",
)


def _make_document() -> Document:
    db = SessionLocal()
    try:
        document = Document(
            filename="pipeline_stage_test.docx",
            sha256_hash=uuid.uuid4().hex,  # unique per test run, avoids collisions
            minio_object_key="test/pipeline_stage_key",
            status="pending",
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        return document
    finally:
        db.close()


def _reload(document_id: uuid.UUID) -> Document:
    db = SessionLocal()
    try:
        return db.get(Document, document_id)
    finally:
        db.close()


def test_pipeline_stage_marks_document_status_and_commits_on_success():
    document = _make_document()

    with pipeline_stage(str(document.id), "test_stage", "running_test") as (_db, stage_document):
        assert stage_document.status == "running_test"

    refreshed = _reload(document.id)
    assert refreshed.status == "running_test"


def test_pipeline_stage_marks_document_failed_on_exception():
    document = _make_document()

    with pytest.raises(ValueError, match="simulated failure"):
        with pipeline_stage(str(document.id), "test_stage", "running_test") as (_db, _doc):
            raise ValueError("simulated failure")

    refreshed = _reload(document.id)
    assert refreshed.status == "failed"
    assert refreshed.error_message == "simulated failure"


def test_pipeline_stage_raises_for_missing_document():
    with pytest.raises(ValueError, match="not found"):
        with pipeline_stage(str(uuid.uuid4()), "test_stage", "running_test"):
            pass
