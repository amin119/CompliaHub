from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import documents, health
from app.core.config import get_settings

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
