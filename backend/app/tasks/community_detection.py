import time
import uuid

from app.services import community_detection, community_summary, graph_store
from app.tasks.celery_app import celery_app

# Fewer, less frequent calls than extraction (one per community, not per
# chunk), but the same free-tier rate-limit risk applies — same proactive
# pacing pattern as extraction.py's _SECONDS_BETWEEN_EXTRACTION_CALLS.
_SECONDS_BETWEEN_SUMMARY_CALLS = 4.0

# A "community" of one isolated entity isn't a cluster worth an LLM summary
# call — Leiden still assigns every vertex to some community, including
# ones with no relations to anything, and this project's graph is likely to
# have plenty of those.
_MIN_COMMUNITY_SIZE = 2


@celery_app.task(name="communities.detect")
def detect_communities_task() -> dict:
    """Rebuilds every community from scratch over the *whole* corpus graph —
    not scoped to one document, since a community spanning ISO 27001 *and*
    ISO 42001 entities is exactly the interesting case for cross-standard
    gap analysis. Triggered explicitly via `POST /graph/communities/detect`,
    not auto-chained after extraction: communities should reflect the whole
    ingested corpus, not be rebuilt after every single document.

    No `pipeline_stage` here — that context manager is keyed to a single
    `Document`, and this operation has none. Progress/failure is tracked via
    Celery's own result backend (`AsyncResult`) instead, surfaced through
    `GET /graph/communities/status/{task_id}`.
    """
    driver = graph_store.get_neo4j_driver()
    try:
        entities = graph_store.fetch_all_entities(driver)
        relations = graph_store.fetch_all_relations(driver)

        graph = community_detection.build_graph(entities, relations)
        communities = community_detection.detect_communities(graph)

        graph_store.clear_communities(driver)

        created = 0
        last_call_at: float | None = None
        for indices in communities:
            members = [(graph.vs[i]["entity_type"], graph.vs[i]["name"]) for i in indices]
            if len(members) < _MIN_COMMUNITY_SIZE:
                continue

            if last_call_at is not None:
                elapsed = time.monotonic() - last_call_at
                remaining = _SECONDS_BETWEEN_SUMMARY_CALLS - elapsed
                if remaining > 0:
                    time.sleep(remaining)

            result = community_summary.summarize_community(members, relations)
            last_call_at = time.monotonic()
            graph_store.create_community(
                driver, str(uuid.uuid4()), result.title, result.summary, members
            )
            created += 1

        return {
            "communities_created": created,
            "singleton_communities_skipped": len(communities) - created,
        }
    finally:
        driver.close()
