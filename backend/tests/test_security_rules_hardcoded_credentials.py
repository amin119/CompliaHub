from app.services.security_analysis.ast_utils import safe_parse
from app.services.security_analysis.base import RuleContext
from app.services.security_analysis.hardcoded_credentials import (
    _detect_generic_regex,
    _detect_python,
)


def _python_context(source: str) -> RuleContext:
    return RuleContext(
        relative_path="app/config.py",
        language="python",
        component_type="application_code",
        text=source,
        tree=safe_parse(source),
    )


def test_flags_hardcoded_password_literal():
    hits = _detect_python(_python_context('password = "hunter2hunter2"\n'))
    assert len(hits) == 1
    assert hits[0].confidence == "high"


def test_does_not_flag_env_lookup():
    hits = _detect_python(_python_context('password = os.environ.get("PASSWORD")\n'))
    assert hits == []


def test_does_not_flag_settings_attribute_access():
    hits = _detect_python(_python_context("password = settings.password\n"))
    assert hits == []


def test_does_not_flag_placeholder_value():
    hits = _detect_python(_python_context('secret = "changeme"\n'))
    assert hits == []


def test_does_not_flag_non_sensitive_variable():
    hits = _detect_python(_python_context('greeting = "hello world 123"\n'))
    assert hits == []


def test_syntax_error_returns_no_hits_not_an_exception():
    context = RuleContext(
        relative_path="broken.py",
        language="python",
        component_type="application_code",
        text="def f(:\n",
        tree=safe_parse("def f(:\n"),
    )
    assert _detect_python(context) == []


def test_generic_regex_flags_non_python_hardcoded_value():
    context = RuleContext(
        relative_path="config.js",
        language="javascript",
        component_type="application_code",
        text='const password = "hunter2hunter2";\n',
        tree=None,
    )
    hits = _detect_generic_regex(context)
    assert len(hits) == 1
    assert hits[0].confidence == "medium"
    assert hits[0].status == "REQUIRES_HUMAN_REVIEW"


def test_generic_regex_skipped_for_python_files():
    # Python files are covered by the AST rule instead — the regex
    # fallback must not double-report the same line.
    context = _python_context('password = "hunter2hunter2"\n')
    assert _detect_generic_regex(context) == []
