"""Platform Phase 8: rebuilds the entire entity graph from every currently-
existing document, from scratch. The user's own resolved decision (via
`AskUserQuestion`) for cleaning up a deleted document's graph contributions:
full rebuild over incremental provenance-tracked deletion — simpler and
trivially correct at this project's real corpus size, though it doesn't
scale (a disclosed trade-off, not an oversight — see docs/phase-8-scaling.md).
"""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.services import graph_store
from app.tasks import extraction

logger = logging.getLogger(__name__)


def rebuild_graph_from_remaining_documents(db: Session, driver) -> None:
    """Cheap today, not a real re-run of the LLM extraction calls:
    `ChunkExtractionCache` is keyed by chunk-content hash, so every
    remaining document's chunks are cache hits — this is a pure Neo4j-write
    replay. Calls the existing Celery task functions directly (not
    `.delay()`) — valid since neither is bound (`self`-less), same as how
    eager-mode tests already invoke task logic synchronously.
    """
    graph_store.clear_entity_graph(driver)

    remaining_documents = list(db.scalars(select(Document)))
    logger.info(
        "rebuilding entity graph from %d remaining document(s)", len(remaining_documents)
    )
    for document in remaining_documents:
        extraction.extract_document_task(str(document.id))
        extraction.resolve_and_load_document_task(None, str(document.id))
    logger.info("entity graph rebuild complete")
