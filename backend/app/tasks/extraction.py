import time

from app.models.document import Chunk
from app.services import embedding, entity_resolution, extraction, extraction_cache, graph_store
from app.services.hashing import sha256_bytes
from app.tasks.celery_app import celery_app
from app.tasks.pipeline import pipeline_stage

_STATUS_FIELD = "graph_status"
_ERROR_FIELD = "graph_error_message"

# Proactive pacing, not just reactive retry-on-429: Gemini's free tier has a
# stricter per-minute quota than what we found for Anthropic/Voyage, so
# waiting until a 429 actually happens (then retrying) wastes calls that
# would've succeeded with a little spacing. An empirical starting point, same
# spirit as embedding.py's rate-limit constants — tune against the real
# account's actual enforced limit once that's known, not just its advertised
# one (the Voyage lesson: documented and enforced limits aren't always the
# same number).
_SECONDS_BETWEEN_EXTRACTION_CALLS = 4.0


@celery_app.task(name="extraction.extract_document")
def extract_document_task(document_id: str) -> None:
    """Stage 1: extract entities/relations from every chunk of this document.

    Processes chunks *sequentially*, not fanned out across concurrent Celery
    tasks — same reasoning as Phase 2's `embed_chunks_task`: a fresh API key
    has tight rate limits, and hitting them with N concurrent calls the
    moment extraction starts is worse than one call at a time.
    """
    with pipeline_stage(
        document_id, "extract", "extracting", status_field=_STATUS_FIELD, error_field=_ERROR_FIELD
    ) as (db, document):
        chunks: list[Chunk] = (
            db.query(Chunk).filter(Chunk.document_id == document.id).order_by(Chunk.path).all()
        )

        last_call_at: float | None = None
        for chunk in chunks:
            content_hash = sha256_bytes(chunk.text.encode("utf-8"))

            if extraction_cache.get_cached(db, content_hash) is not None:
                continue  # cache hit — no API call made, no need to pace

            if last_call_at is not None:
                elapsed = time.monotonic() - last_call_at
                remaining = _SECONDS_BETWEEN_EXTRACTION_CALLS - elapsed
                if remaining > 0:
                    time.sleep(remaining)

            result = extraction.extract_chunk_text(chunk.text)
            last_call_at = time.monotonic()
            extraction_cache.store_result(db, content_hash, result)
            db.commit()

        document.graph_status = "extracted"


@celery_app.task(name="extraction.resolve_and_load_document")
def resolve_and_load_document_task(_extract_result: None, document_id: str) -> None:
    """Stage 2: gather this document's chunk extractions, resolve entities
    against each other and against the existing graph, then load the
    resolved entities/relations into Neo4j.

    `_extract_result` is unused — same leading-arg pattern `chunk_document_task`
    uses for `parsed_tree`, since Celery's `chain()` always feeds the
    previous task's return value as the first positional argument.
    """
    with pipeline_stage(
        document_id,
        "resolve_and_load",
        "resolving",
        status_field=_STATUS_FIELD,
        error_field=_ERROR_FIELD,
    ) as (db, document):
        chunks: list[Chunk] = (
            db.query(Chunk).filter(Chunk.document_id == document.id).order_by(Chunk.path).all()
        )

        candidates = []
        relation_mentions = []  # (relation, chunk_id) — resolved to node ids below
        for chunk in chunks:
            content_hash = sha256_bytes(chunk.text.encode("utf-8"))
            cached = extraction_cache.get_cached(db, content_hash)
            if cached is None:
                continue
            candidates.extend(cached.entities)
            relation_mentions.extend((relation, chunk.id) for relation in cached.relations)

        driver = graph_store.get_neo4j_driver()
        try:
            graph_store.ensure_constraints(driver)
            existing = graph_store.fetch_all_entities(driver)

            resolved = entity_resolution.resolve_entities(
                candidates,
                existing,
                embed_fn=lambda texts: embedding.embed_texts(texts, input_type="document"),
            )

            # Map every *raw* name variant back to its resolved canonical
            # name, so relation mentions (which reference raw names exactly
            # as the LLM wrote them) can be matched to the right node.
            name_to_canonical: dict[str, str] = {
                raw_name: group.canonical_name
                for group in resolved
                for raw_name in group.source_names
            }

            node_ids: dict[str, str] = {
                group.canonical_name: graph_store.upsert_entity(
                    driver, group.entity_type, group.canonical_name, group.embedding or []
                )
                for group in resolved
            }

            for relation, chunk_id in relation_mentions:
                source_canonical = name_to_canonical.get(relation.source)
                target_canonical = name_to_canonical.get(relation.target)
                if source_canonical is None or target_canonical is None:
                    continue  # entity was mentioned in a chunk this batch didn't (re)process
                graph_store.create_relation(
                    driver,
                    node_ids[source_canonical],
                    node_ids[target_canonical],
                    relation.relation_type,
                    chunk_id=str(chunk_id),
                    document_id=str(document.id),
                )
        finally:
            driver.close()

        document.graph_status = "ready"
