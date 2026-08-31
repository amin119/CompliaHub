from app.services.security_analysis.base import RuleContext
from app.services.security_analysis.secrets import (
    _detect_aws_key,
    _detect_generic_high_entropy_secret,
    _detect_github_token,
    _detect_pem_key,
    _detect_slack_token,
)


def _context(text: str) -> RuleContext:
    return RuleContext(
        relative_path="config.py", language="python", component_type="application_code",
        text=text, tree=None,
    )


def test_detects_aws_access_key():
    hits = _detect_aws_key(_context('AWS_KEY = "AKIAIOSFODNN7EXAMPLE"\n'))
    assert len(hits) == 1
    assert hits[0].severity == "CRITICAL"
    assert "AKIA" not in hits[0].snippet or "…" in hits[0].snippet


def test_no_false_positive_on_normal_text():
    assert _detect_aws_key(_context("this is just a normal comment\n")) == []


def test_detects_pem_private_key_header():
    text = "-----BEGIN RSA PRIVATE KEY-----\nMIIB...\n-----END RSA PRIVATE KEY-----\n"
    hits = _detect_pem_key(_context(text))
    assert len(hits) == 1


def test_detects_github_token():
    # Built by concatenation, not as one contiguous literal: a real-shaped
    # fake token in the source text (even one that never worked as a real
    # credential) trips GitHub's own push-protection secret scanner, which
    # matches on this exact prefix/length shape.
    fake_token = "ghp_" + "abcdefghijklmnopqrstuvwxyz0123456789"
    hits = _detect_github_token(_context(f'TOKEN = "{fake_token}"\n'))
    assert len(hits) == 1


def test_detects_slack_token():
    fake_token = "xoxb-" + "1234567890-abcdefghijklmnop"
    hits = _detect_slack_token(_context(f'SLACK = "{fake_token}"\n'))
    assert len(hits) == 1


def test_generic_entropy_flags_high_entropy_secret():
    hits = _detect_generic_high_entropy_secret(
        _context('api_key = "aZ8x!k2Qw9mP4rT7vY1s"\n')
    )
    assert len(hits) == 1
    assert hits[0].confidence == "medium"


def test_generic_entropy_ignores_placeholder():
    assert _detect_generic_high_entropy_secret(_context('password = "changeme"\n')) == []


def test_generic_entropy_ignores_low_entropy_value():
    assert _detect_generic_high_entropy_secret(
        _context('secret_token = "aaaaaaaaaaaaaaaa"\n')
    ) == []


def test_generic_entropy_ignores_non_sensitive_name():
    hits = _detect_generic_high_entropy_secret(_context('some_var = "aZ8x!k2Qw9mP4rT7vY1s"\n'))
    assert hits == []


def test_redacted_snippet_never_contains_full_secret():
    hits = _detect_aws_key(_context('AWS_KEY = "AKIAIOSFODNN7EXAMPLE"\n'))
    assert "AKIAIOSFODNN7EXAMPLE" not in hits[0].snippet
