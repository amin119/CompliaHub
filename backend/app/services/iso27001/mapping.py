"""Deterministic mapping from existing Finding categories to ISO 27001
Annex A control IDs, plus the conservative status-decision function that
turns a control's mapped findings into one ISO27001 Finding's status.

**Caveat distinct from the catalog's own**: `catalog.py`'s `source_note`
is about control ID/title accuracy against the (unlicensed) standard.
This mapping's caveat is different — the *connection* between a category
this scanner already detects and a control ID is this project's own
judgment call about topical relevance, not a licensed cross-reference
published anywhere. Treat every entry here as "plausibly relevant",
never as an authoritative gap analysis.

Categories are deliberately **not** force-fit to a control when there is
no real Annex A analog. `DELIBERATELY_UNMAPPED_CATEGORIES` records those
omissions explicitly (asserted by a unit test) so the absence reads as a
decision, not an oversight that could silently regress.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.services.iso27001.catalog import CATALOG_BY_ID

# (framework, category) -> control IDs. `framework` is `None` for Phase 2's
# security categories, matching `Finding.framework`'s own `None` convention.
CATEGORY_TO_CONTROLS: dict[tuple[str | None, str], list[str]] = {
    # --- Phase 2 (security, framework=None) --------------------------------
    (None, "cryptography"): ["A.8.24"],
    (None, "secrets"): ["A.8.24", "A.8.5"],
    (None, "authentication"): ["A.8.5"],
    (None, "logging"): ["A.8.15"],
    (None, "dependencies"): ["A.8.8"],
    (None, "insecure_configuration"): ["A.8.9"],
    # --- Phase 3 (GDPR) ------------------------------------------------------
    ("GDPR", "security_of_processing"): ["A.8.15"],
    ("GDPR", "third_party_processors"): ["A.5.19", "A.5.20", "A.5.21", "A.5.22", "A.5.23"],
    ("GDPR", "third_party_contracts"): ["A.5.19", "A.5.20", "A.5.21", "A.5.22", "A.5.23"],
    ("GDPR", "retention_policy"): ["A.8.10"],
    # --- Phase 4 (ISO 42001 / AI) --------------------------------------------
    ("ISO42001", "ai_system_detection"): ["A.5.9"],
    ("ISO42001", "ai_system_inventory"): ["A.5.9"],
    ("ISO42001", "monitoring_logging"): ["A.8.16"],
    ("ISO42001", "incident_handling"): ["A.5.24", "A.5.25", "A.5.26", "A.5.27"],
    ("ISO42001", "lifecycle_management"): ["A.8.32"],
    ("ISO42001", "third_party_ai_providers"): ["A.5.19", "A.5.20", "A.5.21", "A.5.22", "A.5.23"],
}

# Categories that exist in the codebase today but are deliberately left out
# of CATEGORY_TO_CONTROLS above — recorded so the absence is a decision,
# not silently-lost coverage. Each has a one-line reason.
DELIBERATELY_UNMAPPED_CATEGORIES: dict[tuple[str | None, str], str] = {
    ("GDPR", "consent_mechanisms"): "GDPR-specific legal construct with no Annex A analog.",
    ("GDPR", "data_minimisation"): "GDPR-specific legal construct with no Annex A analog.",
    ("GDPR", "special_category_data"): "GDPR-specific legal construct with no Annex A analog.",
    ("GDPR", "lawful_basis"): "GDPR-specific legal construct with no Annex A analog.",
    ("GDPR", "dpia"): "GDPR-specific legal construct with no Annex A analog.",
    ("GDPR", "dpo_appointment"): "GDPR-specific legal construct with no Annex A analog.",
    ("GDPR", "records_of_processing_activities"): (
        "GDPR-specific legal construct with no Annex A analog."
    ),
    ("GDPR", "data_subject_rights"): "GDPR-specific legal construct with no Annex A analog.",
    ("ISO42001", "rag_detection"): "Architecture-pattern signal, not itself a compliance gap.",
    ("ISO42001", "prompt_detection"): "Architecture-pattern signal, not itself a compliance gap.",
    ("ISO42001", "agentic_pattern_detection"): (
        "Architecture-pattern signal, not itself a compliance gap."
    ),
    ("ISO42001", "inference_call_detection"): (
        "Architecture-pattern signal, not itself a compliance gap."
    ),
    ("ISO42001", "ai_system_documentation"): (
        "AI-specific governance concept; ISO 27001 has no AI-documentation control."
    ),
    ("ISO42001", "intended_purpose"): (
        "AI-specific governance concept; ISO 27001 has no AI-purpose control."
    ),
    ("ISO42001", "risk_management"): (
        "AI-specific risk process; too AI-specific to map to a generic Annex A control."
    ),
    ("ISO42001", "human_oversight"): "AI-specific governance concept with no Annex A analog.",
    ("ISO42001", "model_evaluation"): "AI-specific governance concept with no Annex A analog.",
}


class _StatusSeverityLike(Protocol):
    status: str
    severity: str


_SEVERITY_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


@dataclass(frozen=True)
class ControlAssessment:
    status: str
    severity: str
    reasoning: str


def decide_control_status(
    automatable: bool, mapped_findings: list[_StatusSeverityLike]
) -> ControlAssessment:
    """Decide one ISO27001 control's status from its mapped findings.

    Deliberately produces only 3 of the spec's 6 statuses —
    `REQUIRES_HUMAN_REVIEW`, `POTENTIAL_NON_COMPLIANCE`, `NOT_VERIFIED` —
    and **never** `VERIFIED`/`PARTIALLY_VERIFIED`: nothing in Phases 2-4's
    rule set produces positive evidence a control is satisfied, only gap
    detection, so synthesizing "verified" from "no negative finding fired"
    would claim more than the evidence supports.
    """
    if not automatable:
        return ControlAssessment(
            status="REQUIRES_HUMAN_REVIEW",
            severity="MEDIUM",
            reasoning="This control is organizational/physical in nature and cannot be "
            "assessed from a source-code repository scan, regardless of any related "
            "findings below.",
        )

    non_compliance = [f for f in mapped_findings if f.status == "POTENTIAL_NON_COMPLIANCE"]
    if non_compliance:
        max_severity = max(
            non_compliance, key=lambda f: _SEVERITY_ORDER.get(f.severity, 0)
        ).severity
        return ControlAssessment(
            status="POTENTIAL_NON_COMPLIANCE",
            severity=max_severity,
            reasoning=f"{len(non_compliance)} mapped finding(s) indicate potential "
            "non-compliance with this control.",
        )

    if mapped_findings:
        return ControlAssessment(
            status="REQUIRES_HUMAN_REVIEW",
            severity="MEDIUM",
            reasoning=f"{len(mapped_findings)} mapped finding(s) exist for this control, all "
            "requiring human review rather than indicating a clear gap.",
        )

    return ControlAssessment(
        status="NOT_VERIFIED",
        severity="LOW",
        reasoning="No mapped findings were produced for this control. This is an absence of "
        "detected gaps, not positive evidence the control is satisfied — a deterministic "
        "code scan cannot confirm compliance, only surface gaps it can detect.",
    )


def control_ids_for(framework: str | None, category: str) -> list[str]:
    return CATEGORY_TO_CONTROLS.get((framework, category), [])


def _build_control_to_categories() -> dict[str, list[tuple[str | None, str]]]:
    reverse: dict[str, list[tuple[str | None, str]]] = {}
    for (framework, category), control_ids in CATEGORY_TO_CONTROLS.items():
        for control_id in control_ids:
            reverse.setdefault(control_id, []).append((framework, category))
    return reverse


# control_id -> the (framework, category) pairs that map onto it. Built once
# at import time from CATEGORY_TO_CONTROLS — the single source of truth —
# rather than hand-duplicated, so the two can never drift apart.
CONTROL_TO_CATEGORIES: dict[str, list[tuple[str | None, str]]] = _build_control_to_categories()


def validate_mapping_integrity() -> None:
    """Every mapped control ID must exist in the catalog. Called by a unit
    test, not at import time, so a bad edit fails CI loudly instead of
    silently no-oping in production.
    """
    for key, control_ids in CATEGORY_TO_CONTROLS.items():
        for control_id in control_ids:
            if control_id not in CATALOG_BY_ID:
                raise ValueError(f"{key} maps to unknown control_id {control_id!r}")
