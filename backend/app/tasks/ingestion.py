import uuid
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone

from sqlalchemy_utils import Ltree

from app.core.db import SessionLocal
from app.models.document import Chunk, Document, ProcessingJob
from app.services import chunking, embedding, storage, vector_store
from app.services.parsing import ParsedSection, parse_document
from app.tasks.celery_app import celery_app


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _dict_to_section(data: dict) -> ParsedSection:
    return ParsedSection(
        title=data["title"],
        level=data["level"],
        clause_number=data["clause_number"],
        text=data["text"],
        children=[_dict_to_section(child) for child in data["children"]],
    )


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


@celery_app.task(name="ingestion.parse_document")
def parse_document_task(document_id: str) -> dict:
    """Stage 1: fetch the raw file from MinIO, run it through Docling, return
    the heading tree (as a plain dict) for the next stage in the chain.
    """
    with pipeline_stage(document_id, "parse", "parsing") as (_db, document):
        client = storage.get_minio_client()
        response = client.get_object(storage.DOCUMENTS_BUCKET, document.minio_object_key)
        try:
            data = response.read()
        finally:
            response.close()
            response.release_conn()

        parsed = parse_document(data, document.filename)

    return asdict(parsed)


@celery_app.task(name="ingestion.chunk_document")
def chunk_document_task(parsed_tree: dict, document_id: str) -> None:
    """Stage 2: walk the heading tree from stage 1, write chunk rows with
    their ltree hierarchy paths, and mark the document ready for embedding.
    """
    with pipeline_stage(document_id, "chunk", "chunking") as (db, document):
        root = _dict_to_section(parsed_tree)
        document_slug = document.filename.rsplit(".", 1)[0]
        records = chunking.build_chunks(root, document_slug)

        # Sibling chunks can reference an already-inserted parent by path;
        # flush (not commit) assigns each row's id without ending the
        # transaction, so later chunks in the same batch can look it up.
        path_to_id: dict[str, uuid.UUID] = {}
        for record in records:
            chunk = Chunk(
                document_id=document.id,
                clause_number=record.clause_number,
                title=record.title,
                text=record.text,
                path=Ltree(record.path),
                order_in_parent=record.order_in_parent,
                parent_chunk_id=(
                    path_to_id.get(record.parent_path) if record.parent_path else None
                ),
            )
            db.add(chunk)
            db.flush()
            path_to_id[record.path] = chunk.id

        # Chunking is no longer the last stage — embedding follows in the
        # chain, so "ready" is set there instead.
        document.status = "embedding"


@celery_app.task(name="ingestion.embed_chunks")
def embed_chunks_task(_chunk_result: None, document_id: str) -> None:
    """Stage 3: embed every chunk of this document with Voyage and upsert the
    vectors into Qdrant, keyed by chunk id. Last stage — marks the document
    `ready` on success.

    `_chunk_result` is unused — Celery's `chain()` always feeds the previous
    task's return value as the leading positional arg (`chunk_document_task`
    returns `None`), same pattern `chunk_document_task` itself uses for
    `parsed_tree` from stage 1.
    """
    with pipeline_stage(document_id, "embed", "embedding") as (db, document):
        chunks: list[Chunk] = (
            db.query(Chunk).filter(Chunk.document_id == document.id).order_by(Chunk.path).all()
        )
        vectors = embedding.embed_texts([chunk.text for chunk in chunks], input_type="document")
        client = vector_store.get_qdrant_client()
        vector_store.upsert_chunks(client, chunks, vectors)

        document.status = "ready"
