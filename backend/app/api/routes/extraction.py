import uuid

from celery import chain
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.document import Document
from app.schemas.graph import DocumentGraphResponse, GraphEntity, GraphRelation
from app.services import graph_store
from app.tasks.extraction import extract_document_task, resolve_and_load_document_task

router = APIRouter(prefix="/documents", tags=["extraction"])


@router.post("/{document_id}/extract", status_code=202)
def extract_document(document_id: uuid.UUID, db: Session = Depends(get_db)):
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="document not found")
    if document.status != "ready":
        raise HTTPException(
            status_code=409,
            detail=f"document ingestion not finished yet (status: {document.status})",
        )

    chain(
        extract_document_task.s(str(document.id)),
        resolve_and_load_document_task.s(str(document.id)),
    ).apply_async()

    return {"document_id": str(document.id), "graph_status": "extracting"}


@router.get("/{document_id}/graph", response_model=DocumentGraphResponse)
def get_document_graph(document_id: uuid.UUID, db: Session = Depends(get_db)):
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="document not found")

    driver = graph_store.get_neo4j_driver()
    try:
        rows = graph_store.fetch_document_graph(driver, str(document_id))
    finally:
        driver.close()

    relations = [
        GraphRelation(
            source=GraphEntity(name=row["source_name"], entity_type=row["source_type"]),
            relation_type=row["relation_type"],
            target=GraphEntity(name=row["target_name"], entity_type=row["target_type"]),
            chunk_id=row["chunk_id"],
        )
        for row in rows
    ]
    return DocumentGraphResponse(relations=relations)
