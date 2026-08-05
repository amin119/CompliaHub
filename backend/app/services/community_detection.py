import igraph
import leidenalg

from app.services.graph_store import RelationEdge
from app.services.ontology import EntityType

# RBConfigurationVertexPartition is leidenalg's tunable stand-in for plain
# modularity optimization: resolution_parameter=1.0 is mathematically
# equivalent to maximizing standard modularity, but the same knob lets us
# make communities coarser/finer later without switching algorithms — worth
# tuning once real corpus output is visible, same "empirical starting point"
# spirit as extraction.py's pacing constants.
_RESOLUTION_PARAMETER = 1.0


def build_graph(
    entities: list[tuple[str, EntityType, list[float]]],
    relations: list[RelationEdge],
) -> igraph.Graph:
    """Builds an undirected, weighted `igraph.Graph` from raw Neo4j fetch
    results (`fetch_all_entities` + `fetch_all_relations`).

    Vertices are keyed by `(entity_type, name)`, not name alone —
    `canonical_name` is only unique *within* an entity-type label (see
    `ensure_constraints`), so a bare name could collide across types.

    Undirected because Leiden's modularity objective measures "how strongly
    connected two entities are," not "which direction" — this project's
    relations are directional for querying (Phase 4), but community
    structure only cares about connectivity. Parallel edges (the same pair
    related via multiple chunk mentions, or via different relation types)
    collapse into one edge whose weight is the mention count — a relation
    independently stated across 5 chunks is stronger evidence these entities
    belong together than one stated once.
    """
    vertex_keys = sorted({(entity_type, name) for name, entity_type, _ in entities})
    key_to_index = {key: index for index, key in enumerate(vertex_keys)}

    edge_weights: dict[tuple[int, int], int] = {}
    for relation in relations:
        source_key = (relation.source_type, relation.source_name)
        target_key = (relation.target_type, relation.target_name)
        if source_key not in key_to_index or target_key not in key_to_index:
            continue  # defensive: entities/relations both come from the same live graph
        i, j = sorted((key_to_index[source_key], key_to_index[target_key]))
        if i == j:
            continue  # skip self-loops — irrelevant to community structure
        edge_weights[(i, j)] = edge_weights.get((i, j), 0) + 1

    graph = igraph.Graph()
    graph.add_vertices(len(vertex_keys))
    graph.vs["entity_type"] = [key[0] for key in vertex_keys]
    graph.vs["name"] = [key[1] for key in vertex_keys]
    if edge_weights:
        graph.add_edges(list(edge_weights.keys()))
        graph.es["weight"] = list(edge_weights.values())
    return graph


def detect_communities(graph: igraph.Graph) -> list[list[int]]:
    """Runs Leiden over the graph, returning each community as a list of
    vertex indices. A single flat partition, not hierarchical/multi-level —
    a deliberate scope decision for this project's corpus size (a few
    hundred entities); see docs/phase-3-extraction.md for the reasoning.
    """
    partition = leidenalg.find_partition(
        graph,
        leidenalg.RBConfigurationVertexPartition,
        weights="weight" if graph.ecount() > 0 else None,
        resolution_parameter=_RESOLUTION_PARAMETER,
    )
    return list(partition)
