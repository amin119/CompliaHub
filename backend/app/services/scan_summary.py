"""Phase 8: Reports — pure aggregation of one scan's findings into the
counts a report needs. No DB access here: the route fetches findings (with
`reviews` eager-loaded) and hands them to `build_scan_summary`, mirroring
`finding_review.py`'s `apply_review` and `iso27001/mapping.py`'s
`decide_control_status` — plain, directly-unit-testable functions over
already-fetched data rather than composed SQL aggregates.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

# The same fixed vocabularies used throughout the scanner. Every bucket is
# zero-filled even when absent from this scan's findings — "0 VERIFIED" is
# more honest than an absent row, the same reasoning
# `FindingReviewRequest.decision` reusing the full 6-value vocabulary
# already established in Phase 7.
_SEVERITIES = ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATIONAL")
_STATUSES = (
    "VERIFIED",
    "PARTIALLY_VERIFIED",
    "NOT_VERIFIED",
    "POTENTIAL_NON_COMPLIANCE",
    "NOT_APPLICABLE",
    "REQUIRES_HUMAN_REVIEW",
)
_FRAMEWORKS = (None, "GDPR", "ISO42001", "ISO27001")


class _ReviewLike(Protocol):
    pass  # only its presence/count matters here, not its fields


class _FindingLike(Protocol):
    severity: str
    status: str
    framework: str | None
    human_review_required: bool
    reviews: Sequence[_ReviewLike]


@dataclass(frozen=True)
class ScanSummary:
    total_findings: int
    severity_counts: list[tuple[str, int]]
    status_counts: list[tuple[str, int]]
    framework_counts: list[tuple[str | None, int]]
    reviewed_findings: int
    unreviewed_findings: int
    requires_human_review_count: int
    requires_human_review_unreviewed_count: int
    total_reviews: int


def build_scan_summary(findings: Sequence[_FindingLike]) -> ScanSummary:
    """`requires_human_review_unreviewed_count` is the single most
    report-worthy number this phase surfaces: currently-flagged findings
    that have never been looked at by a human — distinct from
    `unreviewed_findings`, which also includes already-settled findings
    (e.g. `NOT_APPLICABLE`) nobody needed to review.
    """
    severity_counts = [(s, sum(1 for f in findings if f.severity == s)) for s in _SEVERITIES]
    status_counts = [(s, sum(1 for f in findings if f.status == s)) for s in _STATUSES]
    framework_counts = [(fw, sum(1 for f in findings if f.framework == fw)) for fw in _FRAMEWORKS]

    reviewed = [f for f in findings if len(f.reviews) > 0]
    requires_review = [f for f in findings if f.human_review_required]
    requires_review_unreviewed = [f for f in requires_review if len(f.reviews) == 0]

    return ScanSummary(
        total_findings=len(findings),
        severity_counts=severity_counts,
        status_counts=status_counts,
        framework_counts=framework_counts,
        reviewed_findings=len(reviewed),
        unreviewed_findings=len(findings) - len(reviewed),
        requires_human_review_count=len(requires_review),
        requires_human_review_unreviewed_count=len(requires_review_unreviewed),
        total_reviews=sum(len(f.reviews) for f in findings),
    )
