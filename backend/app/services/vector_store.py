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


def search(
    client: QdrantClient, query_vector: list[float], top_k: int
) -> list[tuple[uuid.UUID, float]]:
    """Returns (chunk_id, score) pairs, best match first."""
    response = client.query_points(
        COLLECTION_NAME, query=query_vector, limit=top_k, with_payload=False
    )
    return [(uuid.UUID(str(point.id)), point.score) for point in response.points]
