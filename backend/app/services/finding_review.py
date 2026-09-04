"""Phase 7: Human Review — the status-transition logic behind a human's
review decision on a Finding.

Deliberately a tiny pure function, not a class or a service with its own
I/O: unlike Phase 6's `finding_validation.py` (an LLM call plus retrieval),
a review is a plain data-entry action with nothing to retry or mock beyond
ordinary SQLAlchemy object mutation.
"""

from __future__ import annotations

from app.models.scan import Finding


def apply_review(finding: Finding, decision: str) -> str | None:
    """Mutates `finding.status`/`finding.human_review_required` in place to
    reflect a human's review decision, returning the finding's status
    immediately beforehand (for the review row's own `previous_status`
    snapshot).

    `human_review_required` is set to whether the *new* decision is itself
    `"REQUIRES_HUMAN_REVIEW"` — not unconditionally cleared — so a reviewer
    who concludes a finding still needs escalation (e.g. to a second,
    more senior reviewer) isn't silently swallowed by the act of reviewing
    it once.
    """
    previous_status = finding.status
    finding.status = decision
    finding.human_review_required = decision == "REQUIRES_HUMAN_REVIEW"
    return previous_status
