from celery import Celery

from app.core.config import get_settings

settings = get_settings()

# Redis doubles as both broker (the task queue) and result backend (where a
# task's return value is stored) — one less moving part than adding a second
# system just for results, and fine at this scale.
celery_app = Celery(
    "compliancegraph",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.ingestion"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_track_started=True,
)
