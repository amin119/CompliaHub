"""Repo-level checks — plain functions, not `FunctionRule`s.

These are aggregate facts across the *whole file set* (does a deletion
route exist anywhere? does a privacy-policy doc exist anywhere?), not
per-file — forcing them into the per-file `detect(context)` protocol would
break its one-file contract. They are called directly by the Celery task,
not registered in `PRIVACY_RULES`.

The spec's "cannot be verified technically" organizational findings live
here: lawful basis, DPIA, DPO appointment, records of processing
activities, third-party contracts, retention policy. All are always emitted
once per scan, always `REQUIRES_HUMAN_REVIEW` — a deterministic scanner
cannot verify an organizational fact, only surface it as something a human
must confirm.

This phase never parses a privacy policy's *prose* — that's Phase 6+
territory. Presence of a privacy-shaped doc only nudges confidence
`low → medium` and adds a note that the doc exists; it never claims the
doc's content was checked.
"""

from __future__ import annotations

import ast

from app.services.privacy_analysis.base import RuleContext, RuleHit

# Decorator attribute names that shape a "delete this resource" route across
# the common Python web frameworks (`@router.delete(...)`, `@app.delete(...)`).
_DELETE_DECORATOR_ATTRS = {"delete"}

# Filenames (already lower-cased) that repo_discovery classifies as
# component_type == "documentation" and whose name is privacy-shaped.
_PRIVACY_DOC_FILENAMES = {
    "privacy.md",
    "privacy-policy.md",
    "privacy_policy.md",
    "data-protection.md",
}


def weak_positive_deletion_signal(context: RuleContext) -> bool:
    """Per-file AST check for a `@router.delete(...)` / `@app.delete(...)`-
    shaped decorator — a weak positive signal that a data-subject deletion
    (erasure) capability *might* exist. Accumulated by the task across its
    file loop; a single True anywhere is enough.
    """
    if context.tree is None:
        return False

    for node in ast.walk(context.tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            target = dec.func if isinstance(dec, ast.Call) else dec
            if isinstance(target, ast.Attribute) and target.attr in _DELETE_DECORATOR_ATTRS:
                return True
    return False


def privacy_policy_doc_present(repository_files) -> bool:
    """`repository_files` is an iterable of objects with `.component_type`
    and `.relative_path` (the `RepositoryFile` rows). True if any is a
    documentation file with a privacy-shaped filename.

    Depends on `repo_discovery._FILENAME_COMPONENT_TYPES` mapping these
    filenames to `"documentation"` (added in Phase 3) — without that a
    repo's own `PRIVACY.md` classifies as `"unknown"` and this carve-out
    could never trigger for the single most common real case.
    """
    for repository_file in repository_files:
        if repository_file.component_type != "documentation":
            continue
        filename = repository_file.relative_path.replace("\\", "/").rsplit("/", 1)[-1].lower()
        if filename in _PRIVACY_DOC_FILENAMES:
            return True
    return False


# The six fixed organizational findings, as (category, title, gap-description)
# triples. Each is always emitted once per scan.
_FIXED_FINDINGS: list[tuple[str, str, str]] = [
    (
        "lawful_basis",
        "Lawful basis for processing not technically verifiable",
        "Whether a valid Art. 6 lawful basis (and Art. 9 condition for any special-category "
        "data) has been identified and documented for each processing activity cannot be "
        "determined from source code alone.",
    ),
    (
        "dpia",
        "Data Protection Impact Assessment status unknown",
        "Whether a DPIA has been carried out where processing is likely to result in a high "
        "risk to individuals (Art. 35) cannot be determined from source code alone.",
    ),
    (
        "dpo_appointment",
        "Data Protection Officer appointment not verifiable",
        "Whether a DPO has been appointed where required (Art. 37) cannot be determined from "
        "source code alone.",
    ),
    (
        "records_of_processing_activities",
        "Records of Processing Activities not verifiable",
        "Whether Records of Processing Activities are maintained (Art. 30) cannot be "
        "determined from source code alone. This also covers data-export/portability "
        "obligations (Art. 20), which have no clean code-shape heuristic to detect directly.",
    ),
    (
        "third_party_contracts",
        "Data processing agreements with third parties not verifiable",
        "Whether data processing agreements are in place with the third-party processors this "
        "code integrates with (Art. 28) cannot be determined from source code alone.",
    ),
    (
        "retention_policy",
        "Data retention policy not technically verifiable",
        "Whether personal data is subject to a defined retention period and deletion schedule "
        "(Art. 5(1)(e)) cannot be determined from source code alone.",
    ),
]


def build_repo_level_findings(
    found_deletion_route: bool, privacy_doc_present: bool
) -> list[tuple[str, RuleHit]]:
    """The six fixed organizational findings, plus one absence-only
    `data_subject_rights` finding when no deletion route was found anywhere.

    Returns `(category, RuleHit)` pairs rather than bare `RuleHit`s: these
    hits don't go through a `FunctionRule` (which is where a per-file rule's
    `category` normally lives), so the category has to travel with the hit
    explicitly — matching it back out of the hit's title text later would be
    a silent-breakage risk the moment a title's wording changes.

    When a privacy doc is present, the six fixed findings' confidence moves
    `low → medium` and their reasoning notes the doc's existence — without
    claiming to have verified its content (this phase never parses the
    doc's prose).

    Presence of a deletion route is never *reported* — only its absence is,
    to keep the list focused on gaps rather than praise.
    """
    confidence = "medium" if privacy_doc_present else "low"
    doc_note = (
        " A privacy-shaped policy document was found in the repository; its existence is "
        "noted but its content has not been verified by this scan."
        if privacy_doc_present
        else ""
    )

    hits: list[tuple[str, RuleHit]] = []
    for category, title, gap in _FIXED_FINDINGS:
        hits.append((
            category,
            RuleHit(
                title=title,
                status="REQUIRES_HUMAN_REVIEW",
                severity="MEDIUM",
                confidence=confidence,
                summary=title + ".",
                reasoning=gap + doc_note,
                recommendation="Confirm this organizational control exists and is documented; "
                "a code scan can surface the obligation but cannot verify it.",
            ),
        ))

    if not found_deletion_route:
        hits.append((
            "data_subject_rights",
            RuleHit(
                title="No data-subject deletion (erasure) route found",
                status="REQUIRES_HUMAN_REVIEW",
                severity="MEDIUM",
                confidence="low",
                summary="No DELETE-shaped route was found anywhere in the scanned code.",
                reasoning=(
                    "No `@router.delete(...)` / `@app.delete(...)`-shaped route was found in "
                    "any scanned file. The right to erasure (Art. 17) requires a way for a "
                    "data subject's personal data to be deleted on request. Absence of a "
                    "DELETE route is a weak signal — the capability may exist by another "
                    "shape — so this is flagged for human review, not asserted."
                ),
                recommendation="Confirm there is a mechanism to delete a data subject's "
                "personal data on request.",
            ),
        ))

    return hits
