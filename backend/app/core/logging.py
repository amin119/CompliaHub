"""Platform Phase 8: structured logging + a correlation id, so one
document's ingestion journey or one query's turn can be reconstructed from
logs alone. stdlib `logging` + a small JSON formatter, not `structlog` or
Langfuse — zero new dependency (matches this project's consistent bias
against new subsystems: no diff library, no charting library elsewhere
either), and stdlib logging is already fork-safe across Celery's worker
processes.

The correlation id is a `contextvars` accumulator, mirroring
`token_tracking.py`'s exact pattern (Phase 7) — same reasoning: safe to read
from any call site unconditionally (a `None` id just prints as `"-"`), no
special-casing needed for code paths that never set one.
"""

import json
import logging
from contextvars import ContextVar
from datetime import datetime, timezone

_correlation_id: ContextVar[str | None] = ContextVar("_correlation_id", default=None)


def set_correlation_id(value: str) -> None:
    _correlation_id.set(value)


def get_correlation_id() -> str | None:
    return _correlation_id.get()


class CorrelationIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = get_correlation_id() or "-"
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": getattr(record, "correlation_id", "-"),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging(level: int = logging.INFO, force: bool = False) -> None:
    """Idempotent by default — safe to call from both `app.main` (host
    FastAPI process) and `app.tasks.celery_app` (every worker process/fork),
    which both import this at module load. Checks `root.handlers` first so a
    second call (e.g. a test importing both modules) never double-attaches
    a handler and double-logs every line.

    `force=True` replaces whatever handlers are already there instead of
    skipping — needed because Celery's own worker bootstrap configures the
    root logger with its own handler/formatter *after* this module's own
    import-time call already ran, silently discarding it (confirmed live:
    application log lines printed as Celery's plain text, not JSON, until
    this was wired to `celery_app.py`'s `after_setup_logger`/
    `after_setup_task_logger` signals, which fire after Celery's own setup
    finishes — the only point this can reliably win).
    """
    root = logging.getLogger()
    if root.handlers and not force:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler.addFilter(CorrelationIdFilter())
    root.handlers = [handler]
    root.setLevel(level)
