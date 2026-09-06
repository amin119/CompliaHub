"""Unit + live-infra tests for Phase 8's API-key auth and Redis-backed rate
limiter. The rate-limit test needs a real Redis instance (fixed-window
counters live there), gated by `_infra_available()` like every other
live-infra test in this project; the auth tests are pure and need nothing.
"""

import time

import pytest
from fastapi import HTTPException
from sqlalchemy import text

from app.core import rate_limit, security
from app.core.config import get_settings
from app.core.db import engine


def _infra_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        client = rate_limit.redis.from_url(get_settings().redis_url, socket_connect_timeout=2)
        client.ping()
        return True
    except Exception:
        return False


def test_require_api_key_is_a_noop_when_unset(monkeypatch):
    monkeypatch.setattr(security, "get_settings", lambda: type("S", (), {"platform_api_key": ""})())
    security.require_api_key(x_api_key=None)  # must not raise


def test_require_api_key_rejects_wrong_key(monkeypatch):
    monkeypatch.setattr(
        security, "get_settings", lambda: type("S", (), {"platform_api_key": "secret"})()
    )
    with pytest.raises(HTTPException) as exc_info:
        security.require_api_key(x_api_key="wrong")
    assert exc_info.value.status_code == 401


def test_require_api_key_rejects_missing_key_when_configured(monkeypatch):
    monkeypatch.setattr(
        security, "get_settings", lambda: type("S", (), {"platform_api_key": "secret"})()
    )
    with pytest.raises(HTTPException):
        security.require_api_key(x_api_key=None)


def test_require_api_key_accepts_matching_key(monkeypatch):
    monkeypatch.setattr(
        security, "get_settings", lambda: type("S", (), {"platform_api_key": "secret"})()
    )
    security.require_api_key(x_api_key="secret")  # must not raise


@pytest.mark.skipif(not _infra_available(), reason="requires a reachable Redis (docker compose up)")
def test_rate_limit_enforces_threshold_within_one_window():
    settings = get_settings()
    client = rate_limit.redis.from_url(settings.redis_url, socket_connect_timeout=2)

    class _FakeClient:
        host = "203.0.113.99"  # TEST-NET-3, never a real client

    class _FakeRequest:
        client = _FakeClient()

    # Clean slate for this synthetic IP's current window.
    window = int(time.time() // 60)
    client.delete(f"ratelimit:query:{_FakeClient.host}:{window}")

    for _ in range(settings.query_rate_limit_per_minute):
        rate_limit.enforce_query_rate_limit(_FakeRequest())  # must not raise

    with pytest.raises(HTTPException) as exc_info:
        rate_limit.enforce_query_rate_limit(_FakeRequest())
    assert exc_info.value.status_code == 429

    client.delete(f"ratelimit:query:{_FakeClient.host}:{window}")
