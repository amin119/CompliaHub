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
    findings_status: str
    findings_error_message: str | None
    privacy_status: str
    privacy_error_message: str | None
    ai_status: str
    ai_error_message: str | None
    iso27001_status: str
    iso27001_error_message: str | None
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


class EvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_type: str | None
    rule_id: str | None
    file_path: str | None
    line_start: int | None
    line_end: int | None
    snippet: str | None
    description: str
    confidence: str | None
    evidence_metadata: dict | None


class FindingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    framework: str | None
    category: str
    rule_id: str
    title: str
    status: str
    severity: str
    confidence: str
    summary: str
    recommendation: str | None
    automated: bool
    human_review_required: bool
    created_at: datetime


class FindingDetailResponse(FindingResponse):
    reasoning: str
    evidence: list[EvidenceResponse]


class BulkValidationRequest(BaseModel):
    finding_ids: list[uuid.UUID]


class BulkValidationResult(BaseModel):
    finding_id: uuid.UUID
    ok: bool
    evidence: EvidenceResponse | None
    error: str | None
