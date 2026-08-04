import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session


def search_chunks(db: Session, query: str, top_k: int) -> list[tuple[uuid.UUID, float]]:
    """Postgres full-text search over `chunks.text_search_vector` (a `tsvector`
    generated column, see migration 0002), ranked by `ts_rank_cd`.

    Queried via raw SQL rather than the ORM: `text_search_vector` is a
    `GENERATED ALWAYS AS (...) STORED` column, and Postgres rejects any
    explicit value for such a column on INSERT/UPDATE — mapping it onto the
    `Chunk` model would risk breaking the existing chunk-insert path in
    `app/tasks/ingestion.py` the moment SQLAlchemy tried to include it in an
    INSERT's column list. It only needs to be *read*, so raw SQL sidesteps
    the whole issue.

    Returns (chunk_id, rank) pairs, best match first.
    """
    rows = db.execute(
        text(
            """
            SELECT id, ts_rank_cd(text_search_vector, plainto_tsquery('english', :query)) AS rank
            FROM chunks
            WHERE text_search_vector @@ plainto_tsquery('english', :query)
            ORDER BY rank DESC
            LIMIT :top_k
            """
        ),
        {"query": query, "top_k": top_k},
    ).all()
    return [(row.id, row.rank) for row in rows]
