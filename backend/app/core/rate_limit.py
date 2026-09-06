"""Platform Phase 8: a real, minimal rate limiter for `/query` — closes a
genuine, currently-live exposure (each call can trigger several unthrottled
paid Gemini/Voyage/Cohere calls). Uses Redis (already a hard dependency, no
new package) via the same `redis.from_url` pattern `health.py`'s deep check
already uses, rather than a library like `slowapi` this project doesn't
otherwise depend on.

Fixed-window, not sliding/token-bucket — a client can burst up to double the
threshold across a window boundary, a known, accepted imprecision for this
scale (a single-operator project, not a multi-tenant SaaS needing exact
fairness); simplicity here matches this project's own repeated bias against
building more precision than the real use case demands.
"""

import time

import redis
from fastapi import HTTPException, Request

from app.core.config import get_settings


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def enforce_query_rate_limit(request: Request) -> None:
    settings = get_settings()
    client = redis.from_url(settings.redis_url, socket_connect_timeout=2)

    window = int(time.time() // 60)
    key = f"ratelimit:query:{_client_ip(request)}:{window}"

    count = client.incr(key)
    if count == 1:
        client.expire(key, 60)

    if count > settings.query_rate_limit_per_minute:
        raise HTTPException(status_code=429, detail="rate limit exceeded, try again shortly")
