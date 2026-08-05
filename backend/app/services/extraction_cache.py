from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.extraction import ChunkExtractionCache
from app.services.ontology import ChunkExtraction


def get_cached(db: Session, content_hash: str) -> ChunkExtraction | None:
    """Returns a previously-cached extraction result for this content hash,
    or None on a cache miss.
    """
    row = db.query(ChunkExtractionCache).filter_by(content_hash=content_hash).first()
    if row is None:
        return None
    return ChunkExtraction.model_validate(row.extraction_result)


def store_result(db: Session, content_hash: str, result: ChunkExtraction) -> None:
    """Caches a successful extraction result.

    Uses a SAVEPOINT (`begin_nested`), not a plain insert: if two documents
    with identical chunk text get extracted concurrently (the worker runs
    several Celery tasks in parallel), both can race to cache the same
    content hash. That's harmless — whoever loses just hits the unique
    constraint — but a plain `db.rollback()` on that error would also discard
    any *other* chunks already cached earlier in this same task's session.
    The savepoint scopes the rollback to only this one insert.
    """
    try:
        with db.begin_nested():
            db.add(
                ChunkExtractionCache(
                    content_hash=content_hash,
                    extraction_result=result.model_dump(mode="json"),
                )
            )
    except IntegrityError:
        pass
