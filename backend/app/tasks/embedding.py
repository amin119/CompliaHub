from app.models.document import Chunk
from app.services import embedding, vector_store
from app.tasks.celery_app import celery_app
from app.tasks.pipeline import pipeline_stage


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
