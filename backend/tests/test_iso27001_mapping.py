from dataclasses import dataclass

import pytest

from app.services.iso27001.catalog import CATALOG_BY_ID
from app.services.iso27001.mapping import (
    CATEGORY_TO_CONTROLS,
    DELIBERATELY_UNMAPPED_CATEGORIES,
    decide_control_status,
    validate_mapping_integrity,
)


@dataclass
class _FakeFinding:
    status: str
    severity: str


# --- referential integrity --------------------------------------------------


def test_every_mapped_control_id_exists_in_catalog():
    validate_mapping_integrity()  # raises on any bad control_id


def test_no_overlap_between_mapped_and_deliberately_unmapped():
    assert set(CATEGORY_TO_CONTROLS) & set(DELIBERATELY_UNMAPPED_CATEGORIES) == set()


# --- explicit "deliberately not mapped" assertions --------------------------


@pytest.mark.parametrize(
    "key",
    [
        ("GDPR", "consent_mechanisms"),
        ("GDPR", "data_minimisation"),
        ("GDPR", "special_category_data"),
        ("GDPR", "lawful_basis"),
        ("GDPR", "dpia"),
        ("GDPR", "dpo_appointment"),
        ("GDPR", "records_of_processing_activities"),
        ("GDPR", "data_subject_rights"),
        ("ISO42001", "rag_detection"),
        ("ISO42001", "prompt_detection"),
        ("ISO42001", "agentic_pattern_detection"),
        ("ISO42001", "inference_call_detection"),
        ("ISO42001", "ai_system_documentation"),
        ("ISO42001", "intended_purpose"),
        ("ISO42001", "risk_management"),
        ("ISO42001", "human_oversight"),
        ("ISO42001", "model_evaluation"),
    ],
)
def test_category_is_deliberately_unmapped(key):
    assert key not in CATEGORY_TO_CONTROLS
    assert key in DELIBERATELY_UNMAPPED_CATEGORIES


@pytest.mark.parametrize(
    "key",
    [
        (None, "cryptography"),
        (None, "secrets"),
        (None, "authentication"),
        (None, "logging"),
        (None, "dependencies"),
        (None, "insecure_configuration"),
        ("GDPR", "security_of_processing"),
        ("GDPR", "third_party_processors"),
        ("GDPR", "third_party_contracts"),
        ("ISO42001", "ai_system_detection"),
        ("ISO42001", "ai_system_inventory"),
        ("ISO42001", "monitoring_logging"),
        ("ISO42001", "incident_handling"),
        ("ISO42001", "lifecycle_management"),
        ("ISO42001", "third_party_ai_providers"),
    ],
)
def test_category_is_mapped(key):
    assert key in CATEGORY_TO_CONTROLS
    assert len(CATEGORY_TO_CONTROLS[key]) > 0


def test_supplier_related_categories_all_map_to_the_same_supplier_controls():
    supplier_controls = {"A.5.19", "A.5.20", "A.5.21", "A.5.22", "A.5.23"}
    assert set(CATEGORY_TO_CONTROLS[("GDPR", "third_party_processors")]) == supplier_controls
    assert set(CATEGORY_TO_CONTROLS[("GDPR", "third_party_contracts")]) == supplier_controls
    assert set(CATEGORY_TO_CONTROLS[("ISO42001", "third_party_ai_providers")]) == supplier_controls


def test_catalog_by_id_has_every_supplier_control():
    for control_id in ("A.5.19", "A.5.20", "A.5.21", "A.5.22", "A.5.23"):
        assert control_id in CATALOG_BY_ID


# --- decide_control_status ---------------------------------------------------


def test_not_automatable_always_requires_human_review_even_with_non_compliance():
    assessment = decide_control_status(
        automatable=False,
        mapped_findings=[_FakeFinding(status="POTENTIAL_NON_COMPLIANCE", severity="CRITICAL")],
    )
    assert assessment.status == "REQUIRES_HUMAN_REVIEW"


def test_automatable_with_non_compliance_finding_propagates_max_severity():
    assessment = decide_control_status(
        automatable=True,
        mapped_findings=[
            _FakeFinding(status="POTENTIAL_NON_COMPLIANCE", severity="MEDIUM"),
            _FakeFinding(status="POTENTIAL_NON_COMPLIANCE", severity="CRITICAL"),
            _FakeFinding(status="REQUIRES_HUMAN_REVIEW", severity="LOW"),
        ],
    )
    assert assessment.status == "POTENTIAL_NON_COMPLIANCE"
    assert assessment.severity == "CRITICAL"


def test_automatable_with_only_human_review_findings():
    assessment = decide_control_status(
        automatable=True,
        mapped_findings=[
            _FakeFinding(status="REQUIRES_HUMAN_REVIEW", severity="MEDIUM"),
        ],
    )
    assert assessment.status == "REQUIRES_HUMAN_REVIEW"


def test_automatable_with_zero_mapped_findings_is_not_verified():
    assessment = decide_control_status(automatable=True, mapped_findings=[])
    assert assessment.status == "NOT_VERIFIED"


@pytest.mark.parametrize("automatable", [True, False])
def test_never_returns_verified_or_partially_verified(automatable):
    """Direct regression test for the deliberate constraint: this phase
    must never claim positive evidence of compliance."""
    scenarios = [
        [],
        [_FakeFinding(status="POTENTIAL_NON_COMPLIANCE", severity="LOW")],
        [_FakeFinding(status="REQUIRES_HUMAN_REVIEW", severity="MEDIUM")],
        [
            _FakeFinding(status="POTENTIAL_NON_COMPLIANCE", severity="HIGH"),
            _FakeFinding(status="REQUIRES_HUMAN_REVIEW", severity="LOW"),
        ],
    ]
    for mapped_findings in scenarios:
        assessment = decide_control_status(automatable, mapped_findings)
        assert assessment.status not in ("VERIFIED", "PARTIALLY_VERIFIED")
