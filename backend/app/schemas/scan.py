import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# The compliance-scanner spec's 6-value status vocabulary — reused verbatim
# by FindingReviewRequest.decision, since a review is the one mechanism
# allowed to assert any of these on a Finding (see FindingReview's model
# docstring). Spelled out once here rather than re-derived elsewhere.
_FINDING_STATUSES = (
    "VERIFIED",
    "PARTIALLY_VERIFIED",
    "NOT_VERIFIED",
    "POTENTIAL_NON_COMPLIANCE",
    "NOT_APPLICABLE",
    "REQUIRES_HUMAN_REVIEW",
)


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


class FindingReviewRequest(BaseModel):
    reviewer_name: str | None = None
    decision: Literal[_FINDING_STATUSES]
    notes: str = Field(min_length=10)

    @field_validator("notes")
    @classmethod
    def _notes_not_blank(cls, v: str) -> str:
        stripped = v.strip()
        if len(stripped) < 10:
            raise ValueError("notes must be a substantive justification, not blank/whitespace")
        return stripped

    @field_validator("reviewer_name")
    @classmethod
    def _blank_name_to_none(cls, v: str | None) -> str | None:
        if v is None:
            return None
        stripped = v.strip()
        return stripped or None


class FindingReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    finding_id: uuid.UUID
    reviewer_name: str | None
    decision: str
    notes: str
    previous_status: str | None
    created_at: datetime


class FindingDetailResponse(FindingResponse):
    reasoning: str
    evidence: list[EvidenceResponse]
    reviews: list[FindingReviewResponse]


class BulkValidationRequest(BaseModel):
    finding_ids: list[uuid.UUID]


class BulkValidationResult(BaseModel):
    finding_id: uuid.UUID
    ok: bool
    evidence: EvidenceResponse | None
    error: str | None
