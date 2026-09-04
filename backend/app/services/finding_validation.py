"""FindingValidationAgent — Phase 6: an LLM's interpretive review of one
Finding, grounded in retrieved standard text (see `compliance_retrieval.py`).

Deliberately narrow: this agent never touches `Finding.status`, and its
verdict vocabulary is structurally incapable of claiming
VERIFIED/PARTIALLY_VERIFIED/NOT_APPLICABLE — nothing in this pipeline
synthesizes positive compliance evidence, and this agent's read of a
handful of retrieved chunks is even weaker grounds for such a claim than
the deterministic rule engine's own restraint (see
docs/scanner-phase-5-iso27001-mapping.md's "explicitly out of scope"). It
only ever adds a new `Evidence` row.
"""

from __future__ import annotations

import time
from enum import Enum
from functools import lru_cache
from typing import Protocol

from google import genai
from google.genai import errors, types
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.document import Chunk
from app.models.scan import Evidence, Finding
from app.services.compliance_retrieval import ComplianceContext

_SYSTEM_PROMPT = (
    "You are reviewing one automated compliance finding produced by a "
    "deterministic code-pattern scanner, using standard-text excerpts "
    "retrieved as grounding. You have NO authority to certify compliance "
    "— never use the words 'compliant', 'non-compliant', 'verified', or "
    "'certified'. Only a qualified human assessor working against a full "
    "licensed copy of the standard can make that call.\n\n"
    "Your job is narrower: judge whether the finding itself looks like a "
    "real issue or a false alarm from the rule that produced it, and "
    "describe how the retrieved excerpts relate to the concern.\n\n"
    "context_relationship: 'supports_concern' if the retrieved text "
    "describes a requirement this finding's evidence plausibly violates; "
    "'contradicts_concern' if the retrieved text suggests this is a "
    "misfire (the requirement doesn't apply here, or the snippet already "
    "satisfies it); 'not_addressed' if the excerpts aren't relevant "
    "enough to judge either way — this is a legitimate, common answer, "
    "not a failure.\n\n"
    "finding_assessment: 'likely_true_positive' only when the evidence "
    "snippet itself looks like a genuine instance of the issue; "
    "'likely_false_positive' when it looks like a rule misfire (wrong "
    "context, test/example code, already mitigated); "
    "'insufficient_evidence' whenever unsure — the correct default, not "
    "a last resort.\n\n"
    "rationale: 2-4 plain sentences, citing which retrieved excerpt(s) "
    "informed your judgment where relevant."
)

_MAX_RETRIES = 3
_RETRY_BASE_DELAY_SECONDS = 2.0
_MAX_EVIDENCE_ROWS_IN_PROMPT = 5


class ContextRelationship(str, Enum):
    SUPPORTS_CONCERN = "supports_concern"
    CONTRADICTS_CONCERN = "contradicts_concern"
    NOT_ADDRESSED = "not_addressed"


class FindingAssessment(str, Enum):
    LIKELY_TRUE_POSITIVE = "likely_true_positive"
    LIKELY_FALSE_POSITIVE = "likely_false_positive"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class FindingValidationVerdict(BaseModel):
    """An LLM's interpretive review of one Finding — NOT a compliance-
    status determination. `Finding.status` is never written from this;
    it only ever backs a new `Evidence` row.
    """

    context_relationship: ContextRelationship
    finding_assessment: FindingAssessment
    confidence: str  # "high" | "medium" | "low" — same vocabulary Evidence.confidence already uses
    rationale: str


class ValidationRateLimited(Exception):
    """Mirrors query_classifier.ClassificationRateLimited — covers both
    actual rate limiting and transient server-side unavailability, since
    both call for the same response: back off and retry.
    """


class ValidationClient(Protocol):
    def validate(self, prompt: str) -> FindingValidationVerdict: ...


@lru_cache
def _sdk_client(api_key: str) -> genai.Client:
    return genai.Client(api_key=api_key)


class _GeminiValidationClient:
    """Same adapter shape as query_classifier.py's — forced schema,
    re-validated via `model_validate_json` rather than trusting
    `.parsed`. Deliberately not sharing code with it: different prompt/
    schema, no shared call site.
    """

    def __init__(self, api_key: str, model: str) -> None:
        self._client = _sdk_client(api_key)
        self._model = model

    def validate(self, prompt: str) -> FindingValidationVerdict:
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=_SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_schema=FindingValidationVerdict,
                    # Unlike query_classifier's thinking_budget=0: this task
                    # needs real reasoning over retrieved text against a
                    # finding's evidence, not a four-way routing decision.
                ),
            )
        except errors.ClientError as exc:
            if exc.code == 429:
                raise ValidationRateLimited(str(exc)) from exc
            raise
        except errors.ServerError as exc:
            raise ValidationRateLimited(str(exc)) from exc

        return FindingValidationVerdict.model_validate_json(response.text)


def get_gemini_validation_client() -> ValidationClient:
    settings = get_settings()
    return _GeminiValidationClient(
        api_key=settings.gemini_api_key, model=settings.gemini_validation_model
    )


def _format_evidence(finding: Finding) -> str:
    parts = []
    for i, evidence in enumerate(finding.evidence[:_MAX_EVIDENCE_ROWS_IN_PROMPT], start=1):
        location = (
            f"{evidence.file_path}:{evidence.line_start}" if evidence.file_path else "no file"
        )
        content = evidence.snippet or evidence.description
        parts.append(f"[{i}] ({location}) {content}")
    return "\n\n".join(parts)


def _format_context_chunks(context_chunks: list[Chunk]) -> str:
    parts = []
    for i, chunk in enumerate(context_chunks, start=1):
        label = chunk.clause_number or chunk.title or f"chunk {i}"
        parts.append(f"[{i}] ({label}) {chunk.text}")
    return "\n\n".join(parts)


def _build_prompt(finding: Finding, context_chunks: list[Chunk]) -> str:
    return (
        f"Finding: {finding.title}\n"
        f"Framework: {finding.framework or 'security (general)'}\n"
        f"Category: {finding.category}\n"
        f"Rule: {finding.rule_id}\n"
        f"Severity: {finding.severity}\n"
        f"Summary: {finding.summary}\n"
        f"Reasoning: {finding.reasoning}\n\n"
        f"Evidence:\n\n{_format_evidence(finding)}\n\n"
        f"Retrieved standard-text excerpts:\n\n{_format_context_chunks(context_chunks)}"
    )


def validate_finding(
    finding: Finding, context_chunks: list[Chunk], client: ValidationClient | None = None
) -> FindingValidationVerdict:
    """Reviews `finding` against `context_chunks` (from
    `compliance_retrieval.retrieve_context_for_finding`), returning a
    structured verdict. `client` defaults to the real Gemini-backed
    adapter; pass a fake `ValidationClient` in tests.

    Retries on rate limits/transient server errors and on schema-
    validation failure, same shape as `query_classifier.classify_query`.
    """
    client = client or get_gemini_validation_client()
    prompt = _build_prompt(finding, context_chunks)

    for attempt in range(_MAX_RETRIES):
        try:
            return client.validate(prompt)
        except ValidationRateLimited:
            if attempt == _MAX_RETRIES - 1:
                raise
            time.sleep(_RETRY_BASE_DELAY_SECONDS * (2**attempt))
        except ValidationError:
            if attempt == _MAX_RETRIES - 1:
                raise
    raise AssertionError("unreachable")  # loop always returns or raises above


def persist_verdict(
    db: Session,
    finding: Finding,
    verdict: FindingValidationVerdict,
    context: ComplianceContext,
    model: str,
    top_k: int,
) -> Evidence:
    """Writes the verdict as a new `Evidence` row using the already-
    reserved `source_type="llm_reasoning"` value — no schema change.
    Every re-validate writes a **new** row (matching the codebase-wide
    clear-and-rebuild-with-new-UUIDs convention); `finding.status` is
    never touched here.
    """
    evidence = Evidence(
        scan_id=finding.scan_id,
        repository_file_id=None,
        finding_id=finding.id,
        source_type="llm_reasoning",
        rule_id="llm_finding_validation",
        file_path=None,
        line_start=None,
        line_end=None,
        snippet=None,
        description=verdict.rationale,
        confidence=verdict.confidence,
        evidence_metadata={
            "context_relationship": verdict.context_relationship.value,
            "finding_assessment": verdict.finding_assessment.value,
            "model": model,
            "top_k": top_k,
            "retrieved_citations": [
                {
                    "chunk_id": str(citation.chunk_id),
                    "document_id": str(citation.document_id),
                    "document_filename": citation.document_filename,
                    "clause_number": citation.clause_number,
                }
                for citation in context.citations
            ],
        },
    )
    db.add(evidence)
    db.commit()
    db.refresh(evidence)
    return evidence
