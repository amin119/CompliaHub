"""Platform Phase 8: deletes one document and every one of its own
Postgres/Qdrant/MinIO rows, then triggers a full entity-graph rebuild from
every remaining document (see `document_rebuild.py` for why "full rebuild"
was chosen over incremental provenance-tracked cleanup).
"""

import logging
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.services import document_rebuild, graph_store, storage, vector_store

logger = logging.getLogger(__name__)


@dataclass
class DeletionResult:
    remaining_document_count: int


def delete_document(db: Session, document: Document) -> DeletionResult:
    """Order matters: external stores (Qdrant, MinIO) are cleaned up before
    the Postgres row is deleted, so a mid-failure leaves the Postgres row as
    evidence of a partial delete rather than an orphaned external remnant
    with nothing left pointing at it.
    """
    logger.info("deleting document %s", document.id)

    vector_store.delete_by_document(vector_store.get_qdrant_client(), document.id)
    storage.delete_document(storage.get_minio_client(), document.minio_object_key)

    db.delete(document)  # cascades chunks + processing_jobs at the DB level, already free
    db.commit()

    driver = graph_store.get_neo4j_driver()
    try:
        document_rebuild.rebuild_graph_from_remaining_documents(db, driver)
    finally:
        driver.close()

    remaining = db.scalar(select(func.count()).select_from(Document))
    logger.info("document deletion complete, %d document(s) remain", remaining)
    return DeletionResult(remaining_document_count=remaining)
