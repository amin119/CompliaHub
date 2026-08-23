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
