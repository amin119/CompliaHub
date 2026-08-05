import uuid
from datetime import datetime, timezone

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import DateTime

from app.core.db import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ChunkExtractionCache(Base):
    """Caches one chunk-text's extraction result by content hash — not by
    chunk id, so identical text shared across chunks/documents (e.g. the same
    boilerplate definition repeated verbatim in multiple standards) only ever
    gets sent to the LLM once, regardless of how many chunks contain it.

    Only successful extractions are stored here — a failed attempt (rate
    limit exhausted, persistent validation failure) simply isn't cached, so
    the next run tries again rather than being permanently skipped.
    """

    __tablename__ = "chunk_extractions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    extraction_result: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
