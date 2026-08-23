from app.services import global_search
from app.services.graph_store import CommunityWithEmbedding


def _community(id_, title, embedding):
    return CommunityWithEmbedding(
        id=id_, title=title, summary=f"Summary of {title}", embedding=embedding
    )


def test_ranks_most_similar_community_first():
    query = [1.0, 0.0]
    close = _community("a", "Close", [1.0, 0.0])
    far = _community("b", "Far", [0.0, 1.0])

    result = global_search.find_similar_communities(query, [far, close], top_k=2)

    assert result[0].id == "a"
    assert result[1].id == "b"


def test_top_k_limits_results():
    query = [1.0, 0.0]
    communities = [_community(str(i), f"C{i}", [1.0, 0.0]) for i in range(5)]

    result = global_search.find_similar_communities(query, communities, top_k=2)

    assert len(result) == 2


def test_empty_communities_returns_empty():
    assert global_search.find_similar_communities([1.0, 0.0], [], top_k=3) == []


def test_default_top_k_is_three():
    query = [1.0, 0.0]
    communities = [_community(str(i), f"C{i}", [1.0, 0.0]) for i in range(5)]

    result = global_search.find_similar_communities(query, communities)

    assert len(result) == global_search.DEFAULT_TOP_K == 3
