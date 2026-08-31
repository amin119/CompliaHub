from app.services.security_analysis.redaction import redact_secret


def test_short_value_gets_fixed_length_mask():
    result = redact_secret("abc")
    assert result == "*" * 8
    assert "abc" not in result


def test_long_value_keeps_first_and_last_chars():
    result = redact_secret("AKIAIOSFODNN7EXAMPLE")
    assert result.startswith("AKIA")
    assert result.endswith("MPLE")
    assert "IOSFODNN7EXA" not in result


def test_empty_value_gets_masked():
    assert redact_secret("") == "*" * 8


def test_custom_keep_length():
    result = redact_secret("0123456789abcdef", keep=2)
    assert result == "01…ef"
