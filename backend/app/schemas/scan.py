import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ScanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    repository_name: str | None
    source_type: str
    original_filename: str
    status: str
    error_message: str | None
    file_count: int | None
    total_size_bytes: int | None
    detected_languages: list[str]
    detected_frameworks: list[str]
    created_at: datetime
    updated_at: datetime


class RepositoryFileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    relative_path: str
    language: str | None
    component_type: str
    size_bytes: int
    content_stored: bool
