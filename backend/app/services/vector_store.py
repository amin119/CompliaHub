import uuid

from qdrant_client import QdrantClient, models

from app.core.config import get_settings
from app.models.document import Chunk
from app.services.embedding import EMBEDDING_DIM

COLLECTION_NAME = "chunks"


def get_qdrant_client() -> QdrantClient:
    return QdrantClient(url=get_settings().qdrant_url)


def ensure_collection(client: QdrantClient) -> None:
    if not client.collection_exists(COLLECTION_NAME):
        client.create_collection(
            COLLECTION_NAME,
            vectors_config=models.VectorParams(size=EMBEDDING_DIM, distance=models.Distance.COSINE),
        )


def upsert_chunks(client: QdrantClient, chunks: list[Chunk], vectors: list[list[float]]) -> None:
    """One Qdrant point per chunk, keyed by `chunk.id` directly — Qdrant
    accepts a UUID as a point ID natively, so there's no need for a separate
    id-mapping table between Postgres and the vector store.
    """
    ensure_collection(client)
    points = [
        models.PointStruct(
            id=str(chunk.id),
            vector=vector,
            payload={
                "document_id": str(chunk.document_id),
                "clause_number": chunk.clause_number,
                "title": chunk.title,
                "path": str(chunk.path),
                "text": chunk.text,
            },
        )
        for chunk, vector in zip(chunks, vectors, strict=True)
    ]
    client.upsert(COLLECTION_NAME, points=points)


def delete_by_document(client: QdrantClient, document_id: uuid.UUID) -> None:
    """Platform Phase 8: removes every point belonging to one document. Safe
    as a plain filter-delete with no cross-document risk — chunks (and
    their Qdrant points) are never shared across documents, unlike Neo4j's
    entity nodes.
    """
    client.delete(
        COLLECTION_NAME,
        points_selector=models.FilterSelector(
            filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="document_id", match=models.MatchValue(value=str(document_id))
                    )
                ]
            )
        ),
    )


def count_by_document(client: QdrantClient, document_id: uuid.UUID) -> int:
    """Platform Phase 8: used by live-infra tests to confirm a document's
    points are actually gone after `delete_by_document`."""
    result = client.count(
        COLLECTION_NAME,
        count_filter=models.Filter(
            must=[
                models.FieldCondition(
                    key="document_id", match=models.MatchValue(value=str(document_id))
                )
            ]
        ),
    )
    return result.count


def search(
    client: QdrantClient, query_vector: list[float], top_k: int
) -> list[tuple[uuid.UUID, float]]:
    """Returns (chunk_id, score) pairs, best match first."""
    response = client.query_points(
        COLLECTION_NAME, query=query_vector, limit=top_k, with_payload=False
    )
    return [(uuid.UUID(str(point.id)), point.score) for point in response.points]
