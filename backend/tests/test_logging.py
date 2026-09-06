"""Pure unit tests for Phase 8's structured logging — no DB/infra involved."""

import json
import logging

from app.core import logging as app_logging


def _make_record(message: str = "hello") -> logging.LogRecord:
    return logging.LogRecord(
        name="test", level=logging.INFO, pathname=__file__, lineno=1,
        msg=message, args=(), exc_info=None,
    )


def test_correlation_id_defaults_to_dash_when_unset():
    app_logging._correlation_id.set(None)
    record = _make_record()
    app_logging.CorrelationIdFilter().filter(record)
    assert record.correlation_id == "-"


def test_correlation_id_set_and_get():
    app_logging.set_correlation_id("doc-123")
    assert app_logging.get_correlation_id() == "doc-123"
    record = _make_record()
    app_logging.CorrelationIdFilter().filter(record)
    assert record.correlation_id == "doc-123"


def test_json_formatter_produces_valid_json_with_expected_fields():
    app_logging.set_correlation_id("conv-1")
    record = _make_record("something happened")
    app_logging.CorrelationIdFilter().filter(record)

    formatted = app_logging.JsonFormatter().format(record)
    payload = json.loads(formatted)

    assert payload["message"] == "something happened"
    assert payload["level"] == "INFO"
    assert payload["correlation_id"] == "conv-1"
    assert payload["logger"] == "test"
    assert "timestamp" in payload


def test_json_formatter_includes_exc_info_when_present():
    try:
        raise ValueError("boom")
    except ValueError:
        record = logging.LogRecord(
            name="test", level=logging.ERROR, pathname=__file__, lineno=1,
            msg="failed", args=(), exc_info=__import__("sys").exc_info(),
        )
    formatted = app_logging.JsonFormatter().format(record)
    payload = json.loads(formatted)
    assert "ValueError: boom" in payload["exc_info"]


def test_configure_logging_is_idempotent():
    root = logging.getLogger()
    handlers_before = list(root.handlers)
    app_logging.configure_logging()
    app_logging.configure_logging()
    # A second (or third) call must not double-attach handlers.
    new_handlers = [h for h in root.handlers if h not in handlers_before]
    assert len(new_handlers) <= 1
