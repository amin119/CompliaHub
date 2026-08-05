import re
from collections.abc import Callable
from dataclasses import dataclass, field

from app.services.ontology import EntityType, ExtractedEntity

# Conservative starting point — like embedding.py's rate-limit constants,
# this needs empirical tuning against the real corpus. Below this, two names
# are treated as genuinely different concepts, not merged.
SIMILARITY_THRESHOLD = 0.90

_NORMALIZE_PATTERN = re.compile(r"[^a-z0-9\s]")


def normalize_name(name: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace — catches
    "Personal Data", "personal data.", "PERSONAL DATA" as the same candidate
    before any (much more expensive) embedding comparison is needed.
    """
    lowered = name.strip().lower()
    stripped = _NORMALIZE_PATTERN.sub("", lowered)
    return " ".join(stripped.split())


def cosine_similarity(a: list[float], b: list[float]) -> float:
    # Mismatched dimensions can never be meaningfully "similar" — treat as
    # 0.0 rather than crash. Guards against stale entities in Neo4j from a
    # different embedding model/dimensionality (e.g. a future Phase 8
    # embedding-model migration), not just a theoretical concern.
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


@dataclass
class ResolvedEntity:
    """One canonical entity after merging. `source_names` keeps every raw
    name variant that resolved into this entity — useful for debugging
    ("why did these three mentions become one node"). `is_new` is False when
    this merged into an entity that already existed in Neo4j from an earlier
    document/run, True when it's a genuinely new node to create.
    """

    canonical_name: str
    entity_type: EntityType
    source_names: list[str] = field(default_factory=list)
    is_new: bool = True
    # Populated only for groups that went through the embedding-similarity
    # stage below (i.e. `is_new=True`, or merged into an existing entity via
    # similarity rather than exact match) — the caller needs this to upsert
    # a *new* node's embedding without paying for a second embed_texts call
    # on the same name. None for groups exact-matched against existing
    # entities in stage 1, which never needed an embedding computed at all.
    embedding: list[float] | None = None


def resolve_entities(
    candidates: list[ExtractedEntity],
    existing: list[tuple[str, EntityType, list[float]]],
    embed_fn: Callable[[list[str]], list[list[float]]],
) -> list[ResolvedEntity]:
    """Merges a batch of freshly-extracted candidate entities: first against
    each other (multiple chunks mentioning the same thing), then against
    `existing` entities already in the graph (name, type, embedding triples
    from `graph_store.fetch_all_entities`).

    Two-stage merge:
    1. Exact match on `normalize_name()` + `entity_type` — cheap, precise,
       catches the large majority of duplicates (case/whitespace/punctuation
       variants of the same name).
    2. Embedding similarity (cosine >= `SIMILARITY_THRESHOLD`) for whatever
       exact match missed — checked against `existing` entities first
       (preferring to merge into something already in the graph over
       creating a near-duplicate new node), then against remaining
       candidates from this same batch.

    `embed_fn` is injected rather than calling `embedding.embed_texts`
    directly, so this whole function stays pure and testable with a fake
    embedder — no network call needed to unit-test the merge logic itself.
    """
    groups: dict[tuple[str, EntityType], ResolvedEntity] = {}
    for candidate in candidates:
        key = (normalize_name(candidate.name), candidate.entity_type)
        if key in groups:
            groups[key].source_names.append(candidate.name)
        else:
            groups[key] = ResolvedEntity(
                canonical_name=candidate.name,
                entity_type=candidate.entity_type,
                source_names=[candidate.name],
            )

    existing_by_key = {
        (normalize_name(name), entity_type): name for name, entity_type, _ in existing
    }

    resolved: list[ResolvedEntity] = []
    unmatched: list[ResolvedEntity] = []
    for key, group in groups.items():
        existing_name = existing_by_key.get(key)
        if existing_name is not None:
            group.canonical_name = existing_name
            group.is_new = False
            resolved.append(group)
        else:
            unmatched.append(group)

    if not unmatched:
        return resolved

    unmatched_embeddings = embed_fn([group.canonical_name for group in unmatched])
    for group, group_embedding in zip(unmatched, unmatched_embeddings, strict=True):
        group.embedding = group_embedding

    merged_into_existing: set[int] = set()
    for i, group in enumerate(unmatched):
        best_name, best_score = None, 0.0
        for name, entity_type, embedding in existing:
            if entity_type != group.entity_type:
                continue
            score = cosine_similarity(unmatched_embeddings[i], embedding)
            if score >= SIMILARITY_THRESHOLD and score > best_score:
                best_name, best_score = name, score
        if best_name is not None:
            group.canonical_name = best_name
            group.is_new = False
            merged_into_existing.add(i)

    absorbed: set[int] = set()
    for i, group in enumerate(unmatched):
        if i in merged_into_existing or i in absorbed:
            continue
        for j in range(i + 1, len(unmatched)):
            if j in merged_into_existing or j in absorbed:
                continue
            if unmatched[j].entity_type != group.entity_type:
                continue
            score = cosine_similarity(unmatched_embeddings[i], unmatched_embeddings[j])
            if score >= SIMILARITY_THRESHOLD:
                group.source_names.extend(unmatched[j].source_names)
                absorbed.add(j)

    resolved.extend(group for i, group in enumerate(unmatched) if i not in absorbed)
    return resolved
