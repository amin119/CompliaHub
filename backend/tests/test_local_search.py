from app.services import local_search
from app.services.graph_store import ProvenancedRelationEdge
from app.services.ontology import EntityType

CONTROL = EntityType.CONTROL
RISK = EntityType.RISK
ASSET = EntityType.ASSET


def _edge(source_type, source_name, relation_type, target_type, target_name, chunk_id="c1"):
    return ProvenancedRelationEdge(
        source_name=source_name,
        source_type=source_type,
        relation_type=relation_type,
        target_name=target_name,
        target_type=target_type,
        chunk_id=chunk_id,
        document_id="d1",
    )


class _FakeFetcher:
    """Returns a canned response per hop, in order, and records the frontier
    it was called with each time — exercises `expand_hops`'s BFS logic
    without any live Neo4j.
    """

    def __init__(self, hop_responses):
        self._hop_responses = list(hop_responses)
        self.calls: list[list] = []

    def __call__(self, keys):
        self.calls.append(sorted(keys))
        if not self._hop_responses:
            return []
        return self._hop_responses.pop(0)


def test_empty_seed_returns_empty_without_calling_fetcher():
    fetcher = _FakeFetcher([])

    result = local_search.expand_hops(set(), fetcher, max_hops=2)

    assert result == []
    assert fetcher.calls == []


def test_single_hop_returns_the_relation_touching_the_seed():
    edge = _edge(CONTROL, "A", "requires", RISK, "B")
    fetcher = _FakeFetcher([[edge]])

    result = local_search.expand_hops({(CONTROL, "A")}, fetcher, max_hops=1)

    assert result == [edge]


def test_stops_early_when_a_hop_discovers_no_new_entities():
    """The first hop only surfaces entities already in the seed set (a
    relation between two already-known entities) — no new frontier, so a
    second hop should never be queried even though max_hops allows it.
    """
    edge = _edge(CONTROL, "A", "requires", RISK, "B")
    fetcher = _FakeFetcher([[edge]])

    local_search.expand_hops({(CONTROL, "A"), (RISK, "B")}, fetcher, max_hops=5)

    assert len(fetcher.calls) == 1


def test_multi_hop_expands_the_frontier_each_round():
    hop1 = _edge(CONTROL, "A", "requires", RISK, "B", chunk_id="c1")
    hop2 = _edge(RISK, "B", "applies_to", ASSET, "C", chunk_id="c2")
    fetcher = _FakeFetcher([[hop1], [hop2]])

    result = local_search.expand_hops({(CONTROL, "A")}, fetcher, max_hops=2)

    assert hop1 in result
    assert hop2 in result
    assert len(fetcher.calls) == 2
    # Second hop's frontier is the newly-discovered entity from hop 1, not
    # the original seed again.
    assert fetcher.calls[1] == [(RISK, "B")]


def test_max_hops_limits_how_far_it_expands():
    hop1 = _edge(CONTROL, "A", "requires", RISK, "B", chunk_id="c1")
    hop2 = _edge(RISK, "B", "applies_to", ASSET, "C", chunk_id="c2")
    fetcher = _FakeFetcher([[hop1], [hop2]])

    result = local_search.expand_hops({(CONTROL, "A")}, fetcher, max_hops=1)

    assert result == [hop1]
    assert len(fetcher.calls) == 1


def test_a_relation_rediscovered_via_a_later_hop_is_not_duplicated():
    """B is reachable from both A and (later) C — the same A-B relation
    could plausibly resurface in a later hop's results; it must only appear
    once in the final output.
    """
    hop1 = _edge(CONTROL, "A", "requires", RISK, "B", chunk_id="c1")
    hop2 = [
        _edge(CONTROL, "A", "requires", RISK, "B", chunk_id="c1"),  # re-surfaced, not new
        _edge(RISK, "B", "applies_to", ASSET, "C", chunk_id="c2"),
    ]
    fetcher = _FakeFetcher([[hop1], hop2])

    result = local_search.expand_hops({(CONTROL, "A")}, fetcher, max_hops=2)

    assert result.count(hop1) == 1
