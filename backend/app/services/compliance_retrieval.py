"""ComplianceRetriever — Phase 6: grounds a Finding in whatever standards
text the user has actually ingested via `/documents`, without this project
ever storing or distributing licensed standard text itself.

Deliberately a thin wrapper, not a new retrieval system: `retrieval.
vector_search` already does embed -> dense search -> lexical search -> RRF
fusion -> Cohere rerank in one call, over the same Postgres+Qdrant a user's
ingested standards land in via Part 1's `/documents` pipeline. Nothing here
needs its own embedding/vector-store logic.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.document import Chunk
from app.models.scan import Finding
from app.schemas.query import Citation
from app.services import retrieval

_DEFAULT_TOP_K = 5


@dataclass
class ComplianceContext:
    chunks: list[Chunk]
    citations: list[Citation]


class NoStandardsContextError(Exception):
    """Raised when `retrieval.vector_search` returns zero chunks — most
    likely because no standards documents have been ingested via
    `/documents` yet (the common case for a fresh install, not a bug).
    Callers must surface this as an explicit "nothing to ground a review
    against" state and must never call the validation LLM with empty
    context — handed no grounding text, it would have nothing to do but
    improvise, exactly the overclaiming this project has avoided every
    prior phase.
    """


def build_finding_query(finding: Finding) -> str:
    """Builds the retrieval query text from a Finding's own fields —
    deliberately never from its Evidence rows' snippets. The retrieval
    query only needs to find semantically relevant *standard* text; it
    gains nothing from raw source-code excerpts, and a snippet could carry
    sensitive content (a secret, PII) with no reason to leave this process
    just to embed a search query. Snippets are reserved for the
    validation prompt itself (`finding_validation.py`), the one place that
    genuinely needs them, which only runs when a user explicitly requests
    a review of that specific finding.
    """
    category_label = finding.category.replace("_", " ")
    parts = [
        finding.title,
        f"{category_label} ({finding.framework or 'security'})",
        finding.summary,
    ]
    if finding.reasoning and finding.reasoning != finding.summary:
        parts.append(finding.reasoning)
    return "\n".join(parts)


def retrieve_context_for_finding(
    db: Session, finding: Finding, top_k: int = _DEFAULT_TOP_K
) -> ComplianceContext:
    """Retrieves standard-text chunks relevant to `finding`, reusing
    Part 1's own `retrieval.vector_search` verbatim — no caching: a
    validate call costs the same order of magnitude as one `/query` call
    (which also has none), and re-validating after a new standard is
    ingested should always see it, never serve a stale hit.
    """
    query = build_finding_query(finding)
    chunks, _ = retrieval.vector_search(db, query, top_k)
    if not chunks:
        raise NoStandardsContextError(
            "No ingested standards documents matched this finding. Ingest "
            "ISO 27001 / ISO 42001 / GDPR reference text via /documents "
            "before requesting an AI review."
        )
    _, _, citations = retrieval.render_evidence(db, chunks, [], [])
    return ComplianceContext(chunks=chunks, citations=citations)
