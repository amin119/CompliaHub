import uuid

from celery import chain
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import require_api_key
from app.models.document import Chunk, Document
from app.schemas.document import ChunkResponse, DocumentResponse
from app.services import document_deletion, storage
from app.services.hashing import sha256_bytes
from app.tasks.embedding import embed_chunks_task
from app.tasks.ingestion import chunk_document_task, parse_document_task

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "", response_model=DocumentResponse, status_code=201, dependencies=[Depends(require_api_key)]
)
def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db)):
    data = file.file.read()
    file_hash = sha256_bytes(data)

    # Idempotency: the same bytes always hash the same way, so a re-upload
    # returns the existing record untouched instead of reprocessing.
    existing = db.scalar(select(Document).where(Document.sha256_hash == file_hash))
    if existing is not None:
        return existing

    object_key = f"{file_hash}/{file.filename}"
    client = storage.get_minio_client()
    storage.upload_document(
        client, object_key, data, file.content_type or "application/octet-stream"
    )

    document = Document(
        filename=file.filename,
        sha256_hash=file_hash,
        minio_object_key=object_key,
        status="pending",
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    chain(
        parse_document_task.s(str(document.id)),
        chunk_document_task.s(str(document.id)),
        embed_chunks_task.s(str(document.id)),
    ).apply_async()

    return document


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(document_id: uuid.UUID, db: Session = Depends(get_db)):
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="document not found")
    return document


@router.get("/{document_id}/chunks", response_model=list[ChunkResponse])
def get_document_chunks(document_id: uuid.UUID, db: Session = Depends(get_db)):
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="document not found")

    chunks = db.scalars(
        select(Chunk).where(Chunk.document_id == document_id).order_by(Chunk.path)
    ).all()
    return chunks


@router.delete("/{document_id}", status_code=204, dependencies=[Depends(require_api_key)])
def delete_document(document_id: uuid.UUID, db: Session = Depends(get_db)):
    """Platform Phase 8: removes a document and every one of its own
    Postgres/Qdrant/MinIO rows, then rebuilds the entire entity graph from
    every remaining document from scratch (the user's own resolved
    decision, via `AskUserQuestion`, over incremental provenance-tracked
    deletion — simpler and trivially correct at this project's real corpus
    size, though it does not scale; see docs/phase-8-scaling.md).
    Deliberately synchronous, no Celery — fast enough at today's real
    corpus; a documented, disclosed risk if that changes at real scale, not
    a reason to preemptively build async infra now.
    """
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="document not found")
    document_deletion.delete_document(db, document)
