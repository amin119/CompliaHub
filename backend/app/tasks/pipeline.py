import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

from app.core.db import SessionLocal
from app.models.document import Document, ProcessingJob


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _fail(
    db,
    document: Document,
    job: ProcessingJob,
    error: Exception,
    status_field: str = "status",
    error_field: str = "error_message",
) -> None:
    """Failure boundary for a pipeline stage: record it on both the job (this
    stage's own history) and the document (so the API/UI can show *why* a
    document is stuck), instead of letting the worker crash silently.

    `status_field`/`error_field` let Phase 3's extraction stages write to
    `graph_status`/`graph_error_message` instead of the ingestion `status` —
    extraction must never clobber the ingestion status that vector/lexical
    search (Phase 2) depends on being `"ready"`.

    `db.rollback()` first is required, not optional: if `error` came from a
    failed flush (e.g. a bad insert), the session's transaction is already
    dead — any further use (including setting these attributes and
    committing) raises `PendingRollbackError` without this.
    """
    db.rollback()
    job.status = "failed"
    job.error_message = str(error)
    job.finished_at = _now()
    setattr(document, status_field, "failed")
    setattr(document, error_field, str(error))
    db.commit()


@contextmanager
def pipeline_stage(
    document_id: str,
    task_name: str,
    in_progress_status: str,
    status_field: str = "status",
    error_field: str = "error_message",
):
    """Owns everything shared by every pipeline stage (ingestion *and*
    extraction): open a session, load the `Document`, create+track a
    `ProcessingJob`, and on exit either mark both successful or route the
    failure through `_fail` — so each task body below only contains the one
    thing that's actually unique to that stage.

    `status_field`/`error_field` default to the ingestion pipeline's own
    `status`/`error_message` columns, unchanged from Phase 1/2's original
    behavior. Phase 3's extraction tasks pass `status_field="graph_status"`,
    `error_field="graph_error_message"` instead — a separate, independent
    status track, since a document can be ready for querying (Phase 2) long
    before graph extraction has run at all.

    Yields `(db, document)`. A failure raised inside the `with` block is
    caught, handed to `_fail`, and re-raised (so Celery still sees the task
    as failed) — everything before the first commit (loading the document,
    creating the job) is deliberately outside that try/except, matching the
    original behavior: a failure that early has no job/document state worth
    rolling back yet, so it just propagates straight to Celery.

    Deliberately dependency-free (no Docling, no embedding/vector/extraction
    services) — every task worker, regardless of which slim Docker image it
    runs in, imports this module, so pulling in a provider-specific import
    here would silently defeat the whole point of per-worker slim images.
    """
    db = SessionLocal()
    try:
        document = db.get(Document, uuid.UUID(document_id))
        if document is None:
            raise ValueError(f"document {document_id} not found")

        job = ProcessingJob(
            document_id=document.id, task_name=task_name, status="running", started_at=_now()
        )
        db.add(job)
        setattr(document, status_field, in_progress_status)
        db.commit()

        try:
            yield db, document
        except Exception as exc:
            _fail(db, document, job, exc, status_field=status_field, error_field=error_field)
            raise

        job.status = "success"
        job.finished_at = _now()
        db.commit()
    finally:
        db.close()
