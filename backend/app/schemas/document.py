import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    status: str
    error_message: str | None
    graph_status: str
    graph_error_message: str | None
    created_at: datetime
    updated_at: datetime


class ChunkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    clause_number: str | None
    title: str | None
    text: str
    path: str
    order_in_parent: int

    @field_validator("path", mode="before")
    @classmethod
    def _stringify_ltree(cls, value: object) -> str:
        # The ORM gives back a sqlalchemy_utils.Ltree, not a plain str (it
        # isn't a str subclass) — coerce it here so response validation
        # doesn't reject it.
        return str(value)
