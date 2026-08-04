import uuid


def reciprocal_rank_fusion(rankings: list[list[uuid.UUID]], k: int = 60) -> list[uuid.UUID]:
    """Merge independently-ranked id lists (e.g. dense + lexical search) into
    one ranking, without needing to calibrate each list's raw scores against
    the other — RRF only looks at rank position, so a dense cosine-similarity
    score and a lexical ts_rank score never need to be on the same scale.

    score(id) = sum over rankings containing id of 1 / (k + rank_in_that_list)

    `k=60` is the standard constant from the original RRF paper (Cormack et
    al., 2009) — it dampens the impact of a single ranking's #1 slot enough
    that an id appearing mid-pack in *every* list can still outrank an id
    that's #1 in only one.
    """
    scores: dict[uuid.UUID, float] = {}
    for ranking in rankings:
        for rank, item_id in enumerate(ranking):
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank + 1)

    return sorted(scores, key=lambda item_id: scores[item_id], reverse=True)
