from app.services import community_detection
from app.services.graph_store import RelationEdge
from app.services.ontology import EntityType


def _entity(name: str, entity_type: EntityType) -> tuple[str, EntityType, list[float]]:
    return (name, entity_type, [0.0])


def test_two_disconnected_pairs_form_two_communities():
    """The core sanity check for Leiden: two edges with no connection between
    them can never increase modularity by merging, so they must land in
    separate communities regardless of resolution — same shape as the
    original toy 6-node sanity check mentioned in the project's own notes.
    """
    entities = [
        _entity("A", EntityType.CONTROL),
        _entity("B", EntityType.RISK),
        _entity("C", EntityType.CONTROL),
        _entity("D", EntityType.RISK),
    ]
    relations = [
        RelationEdge("A", EntityType.CONTROL, "applies_to", "B", EntityType.RISK),
        RelationEdge("C", EntityType.CONTROL, "applies_to", "D", EntityType.RISK),
    ]

    graph = community_detection.build_graph(entities, relations)
    communities = community_detection.detect_communities(graph)

    names_by_community = [{graph.vs[i]["name"] for i in indices} for indices in communities]
    assert {"A", "B"} in names_by_community
    assert {"C", "D"} in names_by_community


def test_isolated_entity_forms_its_own_singleton_community():
    entities = [_entity("Lonely", EntityType.ASSET)]

    graph = community_detection.build_graph(entities, [])
    communities = community_detection.detect_communities(graph)

    assert communities == [[0]]


def test_repeated_relation_increases_edge_weight():
    """Independent mentions across chunks should collapse into one edge
    whose weight reflects how many times it was stated — stronger evidence
    two entities belong together than a single mention.
    """
    entities = [_entity("A", EntityType.CONTROL), _entity("B", EntityType.RISK)]
    relations = [
        RelationEdge("A", EntityType.CONTROL, "applies_to", "B", EntityType.RISK),
        RelationEdge("A", EntityType.CONTROL, "applies_to", "B", EntityType.RISK),
        RelationEdge("A", EntityType.CONTROL, "applies_to", "B", EntityType.RISK),
    ]

    graph = community_detection.build_graph(entities, relations)

    assert graph.ecount() == 1
    assert graph.es[0]["weight"] == 3


def test_same_name_different_type_are_distinct_vertices():
    """canonical_name is only unique within an entity-type label — two
    entities sharing a name but not a type must not collapse into one
    vertex.
    """
    entities = [
        _entity("Ambiguous", EntityType.CONTROL),
        _entity("Ambiguous", EntityType.RISK),
    ]

    graph = community_detection.build_graph(entities, [])

    assert graph.vcount() == 2


def test_relation_referencing_unknown_entity_is_ignored():
    """Defensive: a relation pointing at an entity not in the fetched
    entities list (shouldn't happen since both come from the same live
    graph) must not crash the graph build.
    """
    entities = [_entity("A", EntityType.CONTROL)]
    relations = [RelationEdge("A", EntityType.CONTROL, "applies_to", "Ghost", EntityType.RISK)]

    graph = community_detection.build_graph(entities, relations)

    assert graph.ecount() == 0
