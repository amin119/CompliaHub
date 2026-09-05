import uuid

import pytest

from app.models.scan import Finding, FindingReview
from app.services import scan_summary
from app.services.scan_summary import _FRAMEWORKS, _SEVERITIES, _STATUSES


def _make_finding(
    severity: str = "HIGH",
    status: str = "POTENTIAL_NON_COMPLIANCE",
    framework: str | None = None,
    human_review_required: bool = False,
    reviews: list | None = None,
) -> Finding:
    finding = Finding(
        scan_id=uuid.uuid4(),
        framework=framework,
        category="secrets",
        rule_id="SEC-SECRET-AWS-KEY",
        title="Hardcoded AWS access key",
        status=status,
        severity=severity,
        confidence="high",
        summary="A hardcoded AWS access key was found.",
        reasoning="A hardcoded AWS access key was found.",
        human_review_required=human_review_required,
    )
    finding.reviews = reviews or []
    return finding


def _make_review() -> FindingReview:
    return FindingReview(
        scan_id=uuid.uuid4(),
        finding_id=uuid.uuid4(),
        reviewer_name="Jane Doe",
        decision="VERIFIED",
        notes="Manually confirmed this is accurate.",
        previous_status="POTENTIAL_NON_COMPLIANCE",
    )


# --- empty findings -----------------------------------------------------------


def test_empty_findings_zero_fills_everything():
    summary = scan_summary.build_scan_summary([])

    assert summary.total_findings == 0
    assert summary.severity_counts == [(s, 0) for s in _SEVERITIES]
    assert summary.status_counts == [(s, 0) for s in _STATUSES]
    assert summary.framework_counts == [(fw, 0) for fw in _FRAMEWORKS]
    assert summary.reviewed_findings == 0
    assert summary.unreviewed_findings == 0
    assert summary.requires_human_review_count == 0
    assert summary.requires_human_review_unreviewed_count == 0
    assert summary.total_reviews == 0


# --- severity/status/framework zero-filling and counting ----------------------


def test_severity_counts_zero_fill_and_count_correctly():
    findings = [_make_finding(severity="HIGH"), _make_finding(severity="HIGH"),
                _make_finding(severity="LOW")]
    summary = scan_summary.build_scan_summary(findings)

    counts = dict(summary.severity_counts)
    assert counts["HIGH"] == 2
    assert counts["LOW"] == 1
    assert counts["CRITICAL"] == 0
    assert counts["MEDIUM"] == 0
    assert counts["INFORMATIONAL"] == 0
    assert set(counts) == set(_SEVERITIES)


def test_status_counts_zero_fill_and_count_correctly():
    findings = [
        _make_finding(status="VERIFIED"),
        _make_finding(status="VERIFIED"),
        _make_finding(status="REQUIRES_HUMAN_REVIEW"),
    ]
    summary = scan_summary.build_scan_summary(findings)

    counts = dict(summary.status_counts)
    assert counts["VERIFIED"] == 2
    assert counts["REQUIRES_HUMAN_REVIEW"] == 1
    assert counts["NOT_VERIFIED"] == 0
    assert set(counts) == set(_STATUSES)


def test_framework_none_groups_as_its_own_bucket():
    findings = [
        _make_finding(framework=None),
        _make_finding(framework=None),
        _make_finding(framework="GDPR"),
        _make_finding(framework="ISO27001"),
    ]
    summary = scan_summary.build_scan_summary(findings)

    counts = dict(summary.framework_counts)
    assert counts[None] == 2
    assert counts["GDPR"] == 1
    assert counts["ISO27001"] == 1
    assert counts["ISO42001"] == 0
    assert set(counts) == set(_FRAMEWORKS)


# --- review coverage ------------------------------------------------------------


def test_finding_with_zero_reviews_counts_as_unreviewed():
    findings = [_make_finding(reviews=[])]
    summary = scan_summary.build_scan_summary(findings)

    assert summary.reviewed_findings == 0
    assert summary.unreviewed_findings == 1
    assert summary.total_reviews == 0


def test_finding_with_multiple_reviews_counts_as_reviewed_exactly_once():
    findings = [_make_finding(reviews=[_make_review(), _make_review(), _make_review()])]
    summary = scan_summary.build_scan_summary(findings)

    assert summary.reviewed_findings == 1
    assert summary.unreviewed_findings == 0
    assert summary.total_reviews == 3


def test_requires_human_review_unreviewed_count_increments_only_when_unreviewed():
    flagged_and_reviewed = _make_finding(human_review_required=True, reviews=[_make_review()])
    flagged_and_unreviewed = _make_finding(human_review_required=True, reviews=[])
    not_flagged = _make_finding(human_review_required=False, reviews=[])

    summary = scan_summary.build_scan_summary(
        [flagged_and_reviewed, flagged_and_unreviewed, not_flagged]
    )

    assert summary.requires_human_review_count == 2
    assert summary.requires_human_review_unreviewed_count == 1


# --- counters never drift out of sync -------------------------------------------


@pytest.mark.parametrize("status", _STATUSES)
@pytest.mark.parametrize("has_review", [True, False])
def test_counters_stay_consistent_with_total_findings(status, has_review):
    finding = _make_finding(
        status=status,
        human_review_required=(status == "REQUIRES_HUMAN_REVIEW"),
        reviews=[_make_review()] if has_review else [],
    )
    summary = scan_summary.build_scan_summary([finding])

    assert summary.total_findings == 1
    assert summary.reviewed_findings + summary.unreviewed_findings == summary.total_findings
    if has_review:
        assert summary.reviewed_findings == 1
        assert summary.requires_human_review_unreviewed_count == 0
    else:
        assert summary.unreviewed_findings == 1
        expected_unreviewed_flagged = 1 if status == "REQUIRES_HUMAN_REVIEW" else 0
        assert summary.requires_human_review_unreviewed_count == expected_unreviewed_flagged
