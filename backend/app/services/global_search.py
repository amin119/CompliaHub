from app.services.entity_resolution import cosine_similarity
from app.services.graph_store import CommunityWithEmbedding

# How many communities' summaries to consider "thematically related" to a
# question — an empirical starting point (like local_search's
# DEFAULT_MAX_HOPS), not a threshold-tuned value. No minimum-similarity
# cutoff: unlike entity_resolution's SIMILARITY_THRESHOLD (which decides
# "is this the same entity," a precise yes/no), "loosely related theme" is
# inherently fuzzier, and Phase 5's real query classifier is what's meant
# to eventually decide *whether* global search's answer is even relevant —
# this is deliberately the simple, always-on version until then.
DEFAULT_TOP_K = 3


def find_similar_communities(
    query_embedding: list[float],
    communities: list[CommunityWithEmbedding],
    top_k: int = DEFAULT_TOP_K,
) -> list[CommunityWithEmbedding]:
    """Ranks communities by cosine similarity between the question embedding
    and each community's summary embedding — brute-force, same "fine at
    this project's scale" approach `entity_resolution.py` already uses for
    entity dedup (a few dozen communities, not millions).

    Comparing against a community *summary* embedding (a full sentence)
    rather than entity-name embeddings is what makes this a well-behaved
    comparison in the first place — see docs/phase-4-graph-retrieval.md.
    """
    ranked = sorted(
        communities,
        key=lambda community: cosine_similarity(query_embedding, community.embedding),
        reverse=True,
    )
    return ranked[:top_k]
