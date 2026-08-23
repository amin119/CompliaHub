import uuid
from dataclasses import asdict

from sqlalchemy_utils import Ltree

from app.models.document import Chunk
from app.services import chunking, storage
from app.services.parsing import ParsedSection, parse_document
from app.tasks.celery_app import celery_app
from app.tasks.pipeline import pipeline_stage


def _dict_to_section(data: dict) -> ParsedSection:
    return ParsedSection(
        title=data["title"],
        level=data["level"],
        clause_number=data["clause_number"],
        text=data["text"],
        children=[_dict_to_section(child) for child in data["children"]],
    )


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
        # Idempotency: re-running this stage (e.g. retrying after a
        # downstream embed failure) must not pile up duplicate chunk rows
        # alongside the ones a prior run already wrote — clear first, same
        # "full recompute, not incremental" pattern used elsewhere in this
        # project (e.g. community detection's clear-then-rebuild).
        db.query(Chunk).filter(Chunk.document_id == document.id).delete(
            synchronize_session=False
        )

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
