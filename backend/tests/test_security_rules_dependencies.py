from app.services.security_analysis.base import RuleContext
from app.services.security_analysis.dependencies import _detect_unpinned


def _manifest_context(path: str, text: str) -> RuleContext:
    return RuleContext(
        relative_path=path,
        language=None,
        component_type="dependency_manifest",
        text=text,
        tree=None,
    )


def test_flags_unpinned_requirements_line():
    hits = _detect_unpinned(_manifest_context("requirements.txt", "requests\n"))
    assert len(hits) == 1
    assert hits[0].status == "REQUIRES_HUMAN_REVIEW"
    assert hits[0].severity == "LOW"


def test_does_not_flag_pinned_requirements_line():
    hits = _detect_unpinned(_manifest_context("requirements.txt", "requests==2.31.0\n"))
    assert hits == []


def test_ignores_comments_and_options():
    text = "# a comment\n-r other.txt\nrequests==2.31.0\n"
    assert _detect_unpinned(_manifest_context("requirements.txt", text)) == []


def test_flags_wildcard_package_json_dependency():
    text = '{"dependencies": {"left-pad": "*"}}'
    hits = _detect_unpinned(_manifest_context("package.json", text))
    assert len(hits) == 1


def test_flags_latest_package_json_dependency():
    text = '{"dependencies": {"left-pad": "latest"}}'
    hits = _detect_unpinned(_manifest_context("package.json", text))
    assert len(hits) == 1


def test_does_not_flag_pinned_package_json_dependency():
    text = '{"dependencies": {"left-pad": "1.3.0"}}'
    assert _detect_unpinned(_manifest_context("package.json", text)) == []


def test_ignores_files_not_classified_as_manifest():
    context = RuleContext(
        relative_path="requirements.txt",
        language=None,
        component_type="documentation",
        text="requests\n",
        tree=None,
    )
    assert _detect_unpinned(context) == []


def test_malformed_package_json_does_not_raise():
    context = _manifest_context("package.json", "{not valid json")
    assert _detect_unpinned(context) == []
