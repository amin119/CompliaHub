import uuid

from app.services.fusion import reciprocal_rank_fusion


def test_single_ranking_preserves_order():
    a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    assert reciprocal_rank_fusion([[a, b, c]]) == [a, b, c]


def test_item_in_both_lists_outranks_single_list_top_hit():
    # `shared` is #2 in both lists; `dense_only` is #1 in only the dense list.
    # RRF should still rank `shared` above `dense_only` since it accumulates
    # score from two rankings instead of one.
    shared = uuid.uuid4()
    dense_only = uuid.uuid4()
    lexical_only = uuid.uuid4()

    dense = [dense_only, shared]
    lexical = [lexical_only, shared]

    result = reciprocal_rank_fusion([dense, lexical])

    assert result[0] == shared
    assert set(result) == {dense_only, shared, lexical_only}


def test_empty_rankings_return_empty_list():
    assert reciprocal_rank_fusion([]) == []
    assert reciprocal_rank_fusion([[], []]) == []


def test_disjoint_rankings_all_ids_present():
    a, b, c, d = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    result = reciprocal_rank_fusion([[a, b], [c, d]])
    assert set(result) == {a, b, c, d}
    assert len(result) == 4
