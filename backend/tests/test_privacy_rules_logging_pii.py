from app.services.privacy_analysis.logging_pii import _detect_python as _detect_gdpr
from app.services.security_analysis.ast_utils import safe_parse
from app.services.security_analysis.base import RuleContext
from app.services.security_analysis.logging_rules import _detect_python as _detect_security


def _python_context(source: str) -> RuleContext:
    return RuleContext(
        relative_path="app/api/users.py",
        language="python",
        component_type="application_code",
        text=source,
        tree=safe_parse(source),
    )


def test_logging_email_fires_both_frameworks():
    ctx = _python_context("logger.info(user.email)\n")
    security_hits = _detect_security(ctx)
    gdpr_hits = _detect_gdpr(ctx)
    # Two distinct findings at the same evidence line, not a silent duplicate.
    assert len(security_hits) == 1
    assert len(gdpr_hits) == 1
    assert gdpr_hits[0].status == "POTENTIAL_NON_COMPLIANCE"


def test_logging_password_fires_only_security_framework():
    ctx = _python_context("logger.info(user.password)\n")
    assert len(_detect_security(ctx)) == 1
    # password is deliberately excluded from the PII-only regex — GDPR rule
    # must NOT fire (password/token/secret stay Phase 2's concern).
    assert _detect_gdpr(ctx) == []


def test_logging_phone_fires_gdpr_rule():
    hits = _detect_gdpr(_python_context("logger.warning(user.phone)\n"))
    assert len(hits) == 1


def test_does_not_flag_non_logger_call():
    assert _detect_gdpr(_python_context("emailer.info(user.email)\n")) == []


def test_does_not_flag_plain_string_logging():
    assert _detect_gdpr(_python_context('logger.info("handled")\n')) == []
