from app.services.security_analysis.ast_utils import safe_parse
from app.services.security_analysis.base import RuleContext
from app.services.security_analysis.logging_rules import _detect_python


def _python_context(source: str) -> RuleContext:
    return RuleContext(
        relative_path="app/api/users.py",
        language="python",
        component_type="application_code",
        text=source,
        tree=safe_parse(source),
    )


def test_flags_logging_user_email():
    hits = _detect_python(_python_context("logger.info(user.email)\n"))
    assert len(hits) == 1
    assert hits[0].confidence == "medium"


def test_flags_logging_password_as_high_confidence():
    hits = _detect_python(_python_context("logger.info(user.password)\n"))
    assert len(hits) == 1
    assert hits[0].confidence == "high"
    assert hits[0].severity == "HIGH"


def test_does_not_flag_non_sensitive_logging():
    assert _detect_python(_python_context("logger.info(user.id)\n")) == []


def test_does_not_flag_calls_to_non_logger_objects():
    assert _detect_python(_python_context("emailer.info(user.email)\n")) == []


def test_flags_log_dot_attribute_receiver():
    hits = _detect_python(_python_context("self.logger.info(user.email)\n"))
    assert len(hits) == 1


def test_no_hits_for_plain_string_logging():
    assert _detect_python(_python_context('logger.info("request handled")\n')) == []
