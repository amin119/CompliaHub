"""Platform Phase 8: minimal, real API-key auth for mutating routes. Not a
full user/session system — a single shared key, applied via `Depends`,
matching the roadmap's own "security/access control basics" bar rather than
building RBAC this project has no real users for yet (see
docs/phase-8-scaling.md's "RBAC — documented sketch" section for the
follow-up shape).
"""

from fastapi import Header, HTTPException

from app.core.config import get_settings


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """A real no-op until `PLATFORM_API_KEY` is actually set — same
    "safe, opt-in integration" convention every provider key in
    `core/config.py` already uses, so this never breaks local dev, the test
    suite, or the current frontend (which sends no such header) unless
    someone deliberately configures it.
    """
    settings = get_settings()
    if not settings.platform_api_key:
        return
    if x_api_key != settings.platform_api_key:
        raise HTTPException(status_code=401, detail="invalid or missing API key")
