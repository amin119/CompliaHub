from collections.abc import Callable

from app.services.graph_store import ProvenancedRelationEdge
from app.services.ontology import EntityType

# Empirical starting point — too few hops misses relevant context, too many
# pulls in noise and blows up the answer-generation prompt. Same "tune
# against the real corpus" spirit as extraction.py's pacing constants; not
# expected to be right on the first try.
DEFAULT_MAX_HOPS = 2

EntityKey = tuple[EntityType, str]


def expand_hops(
    seed_keys: set[EntityKey],
    fetch_relations: Callable[[list[EntityKey]], list[ProvenancedRelationEdge]],
    max_hops: int = DEFAULT_MAX_HOPS,
) -> list[ProvenancedRelationEdge]:
    """BFS outward from `seed_keys`, one hop per call to `fetch_relations`.

    `fetch_relations` is injected — same dependency-injection idiom
    `entity_resolution.resolve_entities`'s `embed_fn` parameter already
    established — rather than this function taking a Neo4j `Driver`
    directly, so the traversal/stopping logic (frontier tracking, dedup,
    hop limit) is pure and unit-testable with a fake fetcher, no live Neo4j
    needed for that part. The real caller passes
    `lambda keys: graph_store.fetch_relations_touching(driver, keys)`.

    Stops early if a hop discovers no new entities, even if `max_hops`
    hasn't been reached yet — a fully-explored local neighborhood doesn't
    need to keep re-querying.
    """
    seen: set[EntityKey] = set(seed_keys)
    frontier: set[EntityKey] = set(seed_keys)
    all_relations: list[ProvenancedRelationEdge] = []
    seen_relations: set[tuple] = set()

    for _ in range(max_hops):
        if not frontier:
            break

        relations = fetch_relations(list(frontier))
        next_frontier: set[EntityKey] = set()

        for relation in relations:
            key = (
                relation.source_name,
                relation.source_type,
                relation.relation_type,
                relation.target_name,
                relation.target_type,
                relation.chunk_id,
            )
            if key not in seen_relations:
                seen_relations.add(key)
                all_relations.append(relation)

            for entity_key in (
                (relation.source_type, relation.source_name),
                (relation.target_type, relation.target_name),
            ):
                if entity_key not in seen:
                    seen.add(entity_key)
                    next_frontier.add(entity_key)

        frontier = next_frontier

    return all_relations
