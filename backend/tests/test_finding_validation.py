import uuid

import pytest
from pydantic import ValidationError

from app.models.scan import Evidence, Finding
from app.schemas.query import Citation
from app.services import finding_validation
from app.services.compliance_retrieval import ComplianceContext
from app.services.finding_validation import (
    ContextRelationship,
    FindingAssessment,
    FindingValidationVerdict,
)


def _make_finding(**overrides) -> Finding:
    defaults = dict(
        scan_id=uuid.uuid4(),
        framework=None,
        category="secrets",
        rule_id="SEC-SECRET-AWS-KEY",
        title="Hardcoded AWS access key",
        status="POTENTIAL_NON_COMPLIANCE",
        severity="CRITICAL",
        confidence="high",
        summary="A hardcoded AWS access key was found.",
        reasoning="A hardcoded AWS access key was found in app/auth.py.",
    )
    defaults.update(overrides)
    finding = Finding(**defaults)
    finding.evidence = [
        Evidence(
            scan_id=finding.scan_id,
            source_type="static_pattern",
            rule_id=finding.rule_id,
            file_path="app/auth.py",
            line_start=3,
            snippet='AWS_KEY = "..."',
            description="Hardcoded AWS key literal.",
            confidence="high",
        )
    ]
    return finding


def _make_verdict(**overrides) -> FindingValidationVerdict:
    defaults = dict(
        context_relationship=ContextRelationship.SUPPORTS_CONCERN,
        finding_assessment=FindingAssessment.LIKELY_TRUE_POSITIVE,
        confidence="high",
        rationale="The retrieved excerpt on key management supports this concern.",
    )
    defaults.update(overrides)
    return FindingValidationVerdict(**defaults)


class _FakeValidationClient:
    def __init__(self, fail_times: int = 0, result: FindingValidationVerdict | None = None):
        self.fail_times = fail_times
        self.result = result or _make_verdict()
        self.calls = 0
        self.last_prompt: str | None = None

    def validate(self, prompt: str) -> FindingValidationVerdict:
        self.calls += 1
        self.last_prompt = prompt
        if self.calls <= self.fail_times:
            raise finding_validation.ValidationRateLimited("simulated rate limit")
        return self.result


class _AlwaysInvalidClient:
    def __init__(self) -> None:
        self.calls = 0

    def validate(self, prompt: str) -> FindingValidationVerdict:
        self.calls += 1
        return FindingValidationVerdict.model_validate({"context_relationship": "not_a_real_value"})


class _FakeDBSession:
    """Minimal stand-in for a SQLAlchemy Session — just enough surface for
    `persist_verdict`'s add/commit/refresh calls, no real database. Keeping
    this a unit test (not live-infra) since nothing here needs a real FK
    constraint check — `test_finding_validation_api.py` covers the
    live-infra path.
    """

    def __init__(self):
        self.added: list = []

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        pass

    def refresh(self, obj):
        if obj.id is None:
            obj.id = uuid.uuid4()


def _make_context() -> ComplianceContext:
    return ComplianceContext(
        chunks=[],
        citations=[
            Citation(
                chunk_id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                document_filename="iso27001.docx",
                clause_number="A.8.24",
                path="standard.section",
            )
        ],
    )


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch):
    monkeypatch.setattr(finding_validation.time, "sleep", lambda seconds: None)


# --- validate_finding retry behavior (structural copy of query_classifier's) -


def test_validate_finding_retries_until_success():
    expected = _make_verdict(finding_assessment=FindingAssessment.LIKELY_FALSE_POSITIVE)
    client = _FakeValidationClient(fail_times=2, result=expected)
    finding = _make_finding()

    result = finding_validation.validate_finding(finding, context_chunks=[], client=client)

    assert result == expected
    assert client.calls == 3


def test_validate_finding_raises_after_exhausting_retries():
    client = _FakeValidationClient(fail_times=999)
    finding = _make_finding()

    with pytest.raises(finding_validation.ValidationRateLimited):
        finding_validation.validate_finding(finding, context_chunks=[], client=client)

    assert client.calls == finding_validation._MAX_RETRIES


def test_validate_finding_retries_on_validation_error_too():
    client = _AlwaysInvalidClient()
    finding = _make_finding()

    with pytest.raises(ValidationError):
        finding_validation.validate_finding(finding, context_chunks=[], client=client)

    assert client.calls == finding_validation._MAX_RETRIES


# --- verdict vocabulary round-trips ------------------------------------------


def test_all_finding_assessments_round_trip():
    finding = _make_finding()
    for assessment in FindingAssessment:
        client = _FakeValidationClient(result=_make_verdict(finding_assessment=assessment))
        result = finding_validation.validate_finding(finding, context_chunks=[], client=client)
        assert result.finding_assessment == assessment


def test_all_context_relationships_round_trip():
    finding = _make_finding()
    for relationship in ContextRelationship:
        client = _FakeValidationClient(result=_make_verdict(context_relationship=relationship))
        result = finding_validation.validate_finding(finding, context_chunks=[], client=client)
        assert result.context_relationship == relationship


def test_verdict_vocabulary_never_includes_compliance_status_words():
    """Direct regression test for the one non-negotiable constraint: this
    agent must be structurally incapable of claiming VERIFIED/
    PARTIALLY_VERIFIED/NOT_APPLICABLE."""
    for assessment in FindingAssessment:
        assert assessment.value not in ("verified", "partially_verified", "not_applicable")
    for relationship in ContextRelationship:
        assert relationship.value not in ("verified", "partially_verified", "not_applicable")


# --- prompt construction ------------------------------------------------------


def test_validate_finding_prompt_includes_finding_and_evidence():
    finding = _make_finding()
    client = _FakeValidationClient()

    finding_validation.validate_finding(finding, context_chunks=[], client=client)

    assert finding.title in client.last_prompt
    assert "app/auth.py:3" in client.last_prompt


# --- persist_verdict ----------------------------------------------------------


def test_persist_verdict_writes_llm_reasoning_evidence_with_expected_metadata():
    finding = _make_finding()
    verdict = _make_verdict()
    context = _make_context()
    db = _FakeDBSession()

    evidence = finding_validation.persist_verdict(
        db, finding, verdict, context, model="gemini-3.1-flash-lite", top_k=5
    )

    assert evidence in db.added
    assert evidence.finding_id == finding.id
    assert evidence.source_type == "llm_reasoning"
    assert evidence.rule_id == "llm_finding_validation"
    assert evidence.file_path is None
    assert evidence.snippet is None
    assert evidence.description == verdict.rationale
    assert evidence.confidence == verdict.confidence
    assert evidence.evidence_metadata["context_relationship"] == verdict.context_relationship.value
    assert evidence.evidence_metadata["finding_assessment"] == verdict.finding_assessment.value
    assert evidence.evidence_metadata["model"] == "gemini-3.1-flash-lite"
    assert evidence.evidence_metadata["top_k"] == 5
    assert evidence.evidence_metadata["retrieved_citations"][0]["clause_number"] == "A.8.24"


def test_persist_verdict_never_touches_finding_status():
    finding = _make_finding(status="REQUIRES_HUMAN_REVIEW")
    original_status = finding.status
    db = _FakeDBSession()

    finding_validation.persist_verdict(
        db, finding, _make_verdict(), _make_context(), model="m", top_k=5
    )

    assert finding.status == original_status
