from celery import Celery

from app.core.config import get_settings

settings = get_settings()

# Redis doubles as both broker (the task queue) and result backend (where a
# task's return value is stored) — one less moving part than adding a second
# system just for results, and fine at this scale.
# No `include=[...]` here: each of the three worker services (ingestion/
# vector/graph — see docker-compose.yml) supplies its own task module via
# the `-I`/`--include` CLI flag instead, so that importing this module alone
# never pulls in another worker's (potentially heavy) dependencies.
celery_app = Celery(
    "compliancegraph",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_track_started=True,
    task_routes={
        "ingestion.parse_document": {"queue": "ingestion"},
        "ingestion.chunk_document": {"queue": "ingestion"},
        "ingestion.embed_chunks": {"queue": "vector"},
        "extraction.extract_document": {"queue": "graph"},
        "extraction.resolve_and_load_document": {"queue": "graph"},
        "communities.detect": {"queue": "graph"},
        # Its own queue name (not folded into "ingestion") even though it
        # currently runs on the same worker-ingestion container below — this
        # phase's own dependencies are stdlib-only, but a later phase adding
        # AST/tree-sitter analysis can split this onto its own worker+extra
        # without a queue-naming migration at that point.
        "scanner.extract_repository": {"queue": "scanner"},
        "scanner.detect_frameworks": {"queue": "scanner"},
    },
)
