import truststore

# Must run before any other import creates an SSL context: on this machine,
# outbound HTTPS from Python running natively on the Windows host (as this API
# does via `uv run uvicorn`, unlike the Celery worker which runs in Docker)
# fails cert verification against Voyage/Cohere/Grok — some local network TLS
# interception isn't in certifi's bundled CA list. truststore repoints ssl at
# the OS's own trust store instead, the same fix `--native-tls` is for `uv`
# itself. Harmless on Linux (the worker doesn't import this module at all).
truststore.inject_into_ssl()

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from app.api.routes import documents, health, query  # noqa: E402
from app.core.config import get_settings  # noqa: E402

settings = get_settings()

app = FastAPI(title="ComplianceGraph API")

# The Next.js dev server runs on a different origin (localhost:3000) than this
# API (localhost:8000) — without CORS, the browser blocks the frontend's fetch
# calls even though both are on localhost.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(documents.router)
app.include_router(query.router)
