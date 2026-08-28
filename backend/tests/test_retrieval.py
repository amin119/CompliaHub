import uuid

from app.models.document import Chunk, Document
from app.services import retrieval
from app.services.graph_store import CommunityWithEmbedding, ProvenancedRelationEdge
from app.services.ontology import EntityType


def _make_chunk(clause_number: str, text: str, filename: str = "standard.docx") -> Chunk:
    chunk = Chunk(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        clause_number=clause_number,
        title=None,
        text=text,
        path="standard.section",
        order_in_parent=0,
    )
    chunk.document = Document(filename=filename, sha256_hash="x", minio_object_key="k")
    return chunk


def _edge(chunk_id: str) -> ProvenancedRelationEdge:
    return ProvenancedRelationEdge(
        source_name="A",
        source_type=EntityType.CONTROL,
        relation_type="requires",
        target_name="B",
        target_type=EntityType.RISK,
        chunk_id=chunk_id,
        document_id="d1",
    )


def test_render_evidence_with_no_graph_data_returns_only_chunk_citations():
    chunk = _make_chunk("A.1", "some text")

    graph_facts, community_context, citations = retrieval.render_evidence(None, [chunk], [], [])

    assert graph_facts == []
    assert community_context == []
    assert len(citations) == 1
    assert citations[0].chunk_id == chunk.id
    assert citations[0].clause_number == "A.1"


def test_render_evidence_formats_graph_facts_citing_an_existing_chunk():
    chunk = _make_chunk("A.1", "some text")
    relation = _edge(str(chunk.id))

    graph_facts, _, citations = retrieval.render_evidence(None, [chunk], [relation], [])

    assert len(graph_facts) == 1
    assert "[A.1]" in graph_facts[0]
    assert "Control:'A'" in graph_facts[0]
    assert "Risk:'B'" in graph_facts[0]
    # No new chunk needed — the relation's chunk was already in context_chunks.
    assert len(citations) == 1


def test_render_evidence_formats_community_theme_and_drilldown_facts():
    chunk = _make_chunk("A.1", "some text")
    community = CommunityWithEmbedding(
        id="c1", title="Access Control Theme", summary="About access control.", embedding=[0.1]
    )
    relation = _edge(str(chunk.id))

    _, community_context, _ = retrieval.render_evidence(
        None, [chunk], [], [(community, [relation])]
    )

    assert community_context[0] == "Theme: Access Control Theme — About access control."
    assert len(community_context) == 2
    assert "Control:'A'" in community_context[1]


def test_build_graph_evidence_with_no_relations_is_empty():
    evidence = retrieval.build_graph_evidence([])

    assert evidence.nodes == []
    assert evidence.edges == []


def test_build_graph_evidence_builds_deduped_nodes_and_one_edge():
    chunk_id = str(uuid.uuid4())
    relation = _edge(chunk_id)

    evidence = retrieval.build_graph_evidence([relation])

    assert {node.id for node in evidence.nodes} == {"Control:A", "Risk:B"}
    assert len(evidence.edges) == 1
    edge = evidence.edges[0]
    assert edge.source == "Control:A"
    assert edge.target == "Risk:B"
    assert edge.relation_type == "requires"
    assert str(edge.chunk_id) == chunk_id


def test_build_graph_evidence_dedups_identical_relations():
    chunk_id = str(uuid.uuid4())
    relation = _edge(chunk_id)

    # Same relation surfacing twice (e.g. local search plus a community
    # drill-down both touching it) must collapse to one edge in the
    # visualization, not render as a duplicate.
    evidence = retrieval.build_graph_evidence([relation, relation])

    assert len(evidence.edges) == 1
    assert len(evidence.nodes) == 2


def test_build_graph_evidence_includes_community_drilldown_relations():
    chunk_id = str(uuid.uuid4())
    relation = _edge(chunk_id)
    community = CommunityWithEmbedding(
        id="c1", title="Theme", summary="summary", embedding=[0.1]
    )

    evidence = retrieval.build_graph_evidence([], [(community, [relation])])

    assert len(evidence.edges) == 1
    assert len(evidence.nodes) == 2
