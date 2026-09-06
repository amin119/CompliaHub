import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import select, text

from app.core.db import SessionLocal, engine
from app.models.document import Document, ProcessingJob
from app.services import token_tracking
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


def _job_for(document_id: uuid.UUID, task_name: str) -> ProcessingJob:
    db = SessionLocal()
    try:
        return db.scalar(
            select(ProcessingJob)
            .where(ProcessingJob.document_id == document_id, ProcessingJob.task_name == task_name)
            .order_by(ProcessingJob.started_at.desc())
        )
    finally:
        db.close()


def test_pipeline_stage_persists_token_usage_when_tracked():
    """Platform Phase 8: a stage that makes a real (or, here, simulated)
    Gemini call should have its token usage persisted onto the job row —
    extends Phase 7's `token_tracking` pattern from `/query` to ingestion.
    """
    document = _make_document()

    with pipeline_stage(str(document.id), "test_stage_tokens", "running_test") as (_db, _doc):
        token_tracking.record(SimpleNamespace(prompt_token_count=42, candidates_token_count=7))

    job = _job_for(document.id, "test_stage_tokens")
    assert job.prompt_tokens == 42
    assert job.completion_tokens == 7


def test_pipeline_stage_leaves_token_columns_null_when_nothing_tracked():
    """A stage that never calls a Gemini API (e.g. parse/chunk/embed) must
    not get a misleading `0` — null distinguishes "no tokens used" from
    "this stage doesn't track tokens at all" being conflated.
    """
    document = _make_document()

    with pipeline_stage(str(document.id), "test_stage_no_tokens", "running_test"):
        pass

    job = _job_for(document.id, "test_stage_no_tokens")
    assert job.prompt_tokens is None
    assert job.completion_tokens is None
