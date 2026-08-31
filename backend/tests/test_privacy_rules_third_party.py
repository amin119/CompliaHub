from app.services.privacy_analysis.third_party import (
    _detect_cookies_tracking_regex,
    _detect_set_cookie_python,
    _detect_third_party_imports,
)
from app.services.security_analysis.ast_utils import safe_parse
from app.services.security_analysis.base import RuleContext


def _python_context(source: str) -> RuleContext:
    return RuleContext(
        relative_path="app/services/ai.py",
        language="python",
        component_type="application_code",
        text=source,
        tree=safe_parse(source),
    )


def _web_context(path: str, source: str, language: str | None) -> RuleContext:
    return RuleContext(
        relative_path=path,
        language=language,
        component_type="application_code",
        text=source,
        tree=None,
    )


def test_flags_third_party_import():
    hits = _detect_third_party_imports(_python_context("import cohere\n"))
    assert len(hits) == 1
    assert hits[0].status == "REQUIRES_HUMAN_REVIEW"


def test_flags_from_import_form():
    hits = _detect_third_party_imports(_python_context("from stripe import Charge\n"))
    assert len(hits) == 1


def test_international_transfer_language_in_same_finding():
    hits = _detect_third_party_imports(_python_context("import openai\n"))
    assert len(hits) == 1
    # International-transfer language folded into the same finding, not a
    # second near-duplicate finding for the same line.
    assert "transfer" in hits[0].reasoning.lower()


def test_does_not_flag_stdlib_import():
    assert _detect_third_party_imports(_python_context("import os\nimport json\n")) == []


def test_one_finding_per_distinct_package():
    source = "import cohere\nfrom cohere import Client\n"
    hits = _detect_third_party_imports(_python_context(source))
    assert len(hits) == 1


def test_flags_set_cookie_python():
    hits = _detect_set_cookie_python(_python_context("response.set_cookie('sid', v)\n"))
    assert len(hits) == 1
    assert hits[0].status == "REQUIRES_HUMAN_REVIEW"


def test_flags_document_cookie_in_js():
    hits = _detect_cookies_tracking_regex(
        _web_context("app.js", "document.cookie = 'a=1';\n", "javascript")
    )
    assert len(hits) == 1


def test_flags_tracking_marker_in_html():
    hits = _detect_cookies_tracking_regex(
        _web_context("index.html", "<script>gtag('config', 'GA-1');</script>\n", None)
    )
    assert len(hits) == 1


def test_cookie_regex_skips_python():
    # The regex cookie rule must not fire on Python (the AST rule owns that).
    ctx = RuleContext(
        relative_path="app.py",
        language="python",
        component_type="application_code",
        text="response.set_cookie('x')\n",
        tree=safe_parse("response.set_cookie('x')\n"),
    )
    assert _detect_cookies_tracking_regex(ctx) == []
