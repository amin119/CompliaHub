from dataclasses import dataclass

from app.services.privacy_analysis.repo_level_checks import (
    build_repo_level_findings,
    privacy_policy_doc_present,
    weak_positive_deletion_signal,
)
from app.services.security_analysis.ast_utils import safe_parse
from app.services.security_analysis.base import RuleContext


def _python_context(source: str) -> RuleContext:
    return RuleContext(
        relative_path="app/api/users.py",
        language="python",
        component_type="application_code",
        text=source,
        tree=safe_parse(source),
    )


@dataclass
class _FakeFile:
    relative_path: str
    component_type: str


# --- weak_positive_deletion_signal -----------------------------------------


def test_detects_router_delete_decorator():
    source = "@router.delete('/users/{id}')\nasync def delete_user(id):\n    ...\n"
    assert weak_positive_deletion_signal(_python_context(source)) is True


def test_detects_app_delete_decorator():
    source = "@app.delete('/x')\ndef d():\n    ...\n"
    assert weak_positive_deletion_signal(_python_context(source)) is True


def test_no_delete_route_returns_false():
    source = "@router.get('/users')\ndef list_users():\n    ...\n"
    assert weak_positive_deletion_signal(_python_context(source)) is False


# --- privacy_policy_doc_present --------------------------------------------


def test_privacy_doc_detected():
    files = [_FakeFile("docs/PRIVACY.md", "documentation")]
    assert privacy_policy_doc_present(files) is True


def test_privacy_doc_requires_documentation_component_type():
    # Right name but wrong component_type -> not counted.
    files = [_FakeFile("privacy.md", "unknown")]
    assert privacy_policy_doc_present(files) is False


def test_no_privacy_doc_returns_false():
    files = [_FakeFile("README.md", "documentation")]
    assert privacy_policy_doc_present(files) is False


# --- build_repo_level_findings: all four boolean combinations --------------

_EXPECTED_FIXED_CATEGORIES = {
    "lawful_basis",
    "dpia",
    "dpo_appointment",
    "records_of_processing_activities",
    "third_party_contracts",
    "retention_policy",
}


def test_six_fixed_findings_always_present():
    pairs = build_repo_level_findings(found_deletion_route=True, privacy_doc_present=False)
    # Six fixed findings; deletion route found -> no absence finding.
    assert len(pairs) == 6
    assert {category for category, _hit in pairs} == _EXPECTED_FIXED_CATEGORIES
    assert all(hit.status == "REQUIRES_HUMAN_REVIEW" for _category, hit in pairs)


def test_absence_finding_added_when_no_deletion_route():
    pairs = build_repo_level_findings(found_deletion_route=False, privacy_doc_present=False)
    assert len(pairs) == 7
    assert any(category == "data_subject_rights" for category, _hit in pairs)
    absence_hit = next(hit for category, hit in pairs if category == "data_subject_rights")
    assert "deletion (erasure) route" in absence_hit.title


def test_privacy_doc_raises_confidence_to_medium():
    without = build_repo_level_findings(found_deletion_route=True, privacy_doc_present=False)
    with_doc = build_repo_level_findings(found_deletion_route=True, privacy_doc_present=True)
    assert all(hit.confidence == "low" for _category, hit in without)
    assert all(hit.confidence == "medium" for _category, hit in with_doc)
    # Notes the doc's existence without claiming to verify its content.
    assert any("not been verified" in hit.reasoning for _category, hit in with_doc)


def test_presence_of_deletion_route_is_never_reported():
    # Only absence is ever surfaced — presence produces no praise finding.
    pairs = build_repo_level_findings(found_deletion_route=True, privacy_doc_present=True)
    assert not any(category == "data_subject_rights" for category, _hit in pairs)
