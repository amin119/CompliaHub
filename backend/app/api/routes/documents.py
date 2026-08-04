import uuid

from celery import chain
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.document import Chunk, Document
from app.schemas.document import ChunkResponse, DocumentResponse
from app.services import storage
from app.services.hashing import sha256_bytes
from app.tasks.ingestion import chunk_document_task, embed_chunks_task, parse_document_task

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", response_model=DocumentResponse, status_code=201)
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
