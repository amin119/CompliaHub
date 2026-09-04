import uuid

import pytest
from pydantic import ValidationError

from app.models.scan import Finding
from app.schemas.scan import _FINDING_STATUSES, FindingReviewRequest
from app.services import finding_review


def _make_finding(status: str = "REQUIRES_HUMAN_REVIEW") -> Finding:
    return Finding(
        scan_id=uuid.uuid4(),
        framework=None,
        category="secrets",
        rule_id="SEC-SECRET-AWS-KEY",
        title="Hardcoded AWS access key",
        status=status,
        severity="CRITICAL",
        confidence="high",
        summary="A hardcoded AWS access key was found.",
        reasoning="A hardcoded AWS access key was found.",
        human_review_required=(status == "REQUIRES_HUMAN_REVIEW"),
    )


# --- FindingReviewRequest schema ---------------------------------------------


def test_request_accepts_every_valid_decision():
    for decision in _FINDING_STATUSES:
        request = FindingReviewRequest(
            decision=decision, notes="Manually confirmed this is accurate."
        )
        assert request.decision == decision


def test_request_rejects_invalid_decision():
    with pytest.raises(ValidationError):
        FindingReviewRequest(decision="MAYBE", notes="Manually confirmed this is accurate.")


def test_request_rejects_blank_notes():
    with pytest.raises(ValidationError):
        FindingReviewRequest(decision="VERIFIED", notes="   ")


def test_request_rejects_too_short_notes():
    with pytest.raises(ValidationError):
        FindingReviewRequest(decision="VERIFIED", notes="ok")


def test_request_strips_and_keeps_substantive_notes():
    request = FindingReviewRequest(
        decision="VERIFIED", notes="  Manually confirmed this is accurate.  "
    )
    assert request.notes == "Manually confirmed this is accurate."


def test_request_blank_reviewer_name_becomes_none():
    request = FindingReviewRequest(
        reviewer_name="   ", decision="VERIFIED", notes="Manually confirmed this is accurate."
    )
    assert request.reviewer_name is None


def test_request_reviewer_name_none_stays_none():
    request = FindingReviewRequest(
        reviewer_name=None, decision="VERIFIED", notes="Manually confirmed this is accurate."
    )
    assert request.reviewer_name is None


def test_request_real_reviewer_name_is_kept_trimmed():
    request = FindingReviewRequest(
        reviewer_name="  Jane Doe  ",
        decision="VERIFIED",
        notes="Manually confirmed this is accurate.",
    )
    assert request.reviewer_name == "Jane Doe"


# --- apply_review -------------------------------------------------------------


@pytest.mark.parametrize("decision", _FINDING_STATUSES)
@pytest.mark.parametrize("starting_status", _FINDING_STATUSES)
def test_apply_review_sets_status_and_snapshots_previous(starting_status, decision):
    finding = _make_finding(status=starting_status)

    previous_status = finding_review.apply_review(finding, decision)

    assert previous_status == starting_status
    assert finding.status == decision


@pytest.mark.parametrize("decision", _FINDING_STATUSES)
def test_apply_review_sets_human_review_required_correctly(decision):
    finding = _make_finding(status="POTENTIAL_NON_COMPLIANCE")

    finding_review.apply_review(finding, decision)

    assert finding.human_review_required == (decision == "REQUIRES_HUMAN_REVIEW")


def test_apply_review_re_escalation_sets_flag_again():
    finding = _make_finding(status="REQUIRES_HUMAN_REVIEW")
    finding_review.apply_review(finding, "VERIFIED")
    assert finding.human_review_required is False

    finding_review.apply_review(finding, "REQUIRES_HUMAN_REVIEW")
    assert finding.human_review_required is True
