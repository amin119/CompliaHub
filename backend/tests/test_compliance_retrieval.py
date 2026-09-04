import uuid

from app.models.document import Chunk, Document
from app.models.scan import Evidence, Finding
from app.services import compliance_retrieval, retrieval


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


_SECRET_MARKER = "AKIA" + "FAKEFAKEFAKEFAKEFAKE"


def _make_finding(**overrides) -> Finding:
    defaults = dict(
        scan_id=uuid.uuid4(),
        framework=None,
        category="secrets",
        rule_id="SEC-SECRET-AWS-KEY",
        title="Hardcoded AWS access key",
        status="POTENTIAL_NON_COMPLIANCE",
        severity="CRITICAL",
        confidence="high",
        summary="A hardcoded AWS access key was found.",
        reasoning="A hardcoded AWS access key was found.",
    )
    defaults.update(overrides)
    finding = Finding(**defaults)
    finding.evidence = [
        Evidence(
            scan_id=finding.scan_id,
            source_type="static_pattern",
            rule_id=finding.rule_id,
            file_path="app/auth.py",
            line_start=3,
            snippet=f'AWS_KEY = "{_SECRET_MARKER}"',
            description="Hardcoded AWS key literal.",
            confidence="high",
        )
    ]
    return finding


# --- build_finding_query -----------------------------------------------------


def test_build_finding_query_uses_title_category_framework_summary():
    finding = _make_finding()
    query = compliance_retrieval.build_finding_query(finding)

    assert finding.title in query
    assert "secrets" in query
    assert "security" in query  # framework=None falls back to "security"
    assert finding.summary in query


def test_build_finding_query_skips_reasoning_when_identical_to_summary():
    finding = _make_finding(summary="same text", reasoning="same text")
    query = compliance_retrieval.build_finding_query(finding)

    assert query.count("same text") == 1


def test_build_finding_query_includes_reasoning_when_different():
    finding = _make_finding(summary="short summary", reasoning="a longer distinct reasoning")
    query = compliance_retrieval.build_finding_query(finding)

    assert "a longer distinct reasoning" in query


def test_build_finding_query_excludes_evidence_snippets():
    """The retrieval query must never leak raw code/secrets — it only
    needs to find semantically relevant *standard* text, and a snippet
    could carry sensitive content with no reason to leave this process
    just to embed a search query."""
    finding = _make_finding()
    query = compliance_retrieval.build_finding_query(finding)

    assert _SECRET_MARKER not in query


def test_build_finding_query_uses_framework_when_present():
    finding = _make_finding(framework="GDPR", category="data_minimisation")
    query = compliance_retrieval.build_finding_query(finding)

    assert "GDPR" in query
    assert "data minimisation" in query  # underscores humanized


# --- retrieve_context_for_finding --------------------------------------------


def test_retrieve_context_raises_when_zero_chunks(monkeypatch):
    monkeypatch.setattr(retrieval, "vector_search", lambda db, question, top_k: ([], [0.1]))

    finding = _make_finding()
    try:
        compliance_retrieval.retrieve_context_for_finding(db=None, finding=finding)
        assert False, "expected NoStandardsContextError"
    except compliance_retrieval.NoStandardsContextError:
        pass


def test_retrieve_context_returns_chunks_and_citations_when_present(monkeypatch):
    chunk = _make_chunk("A.8.24", "Use of cryptography shall be governed by a policy.")
    monkeypatch.setattr(
        retrieval, "vector_search", lambda db, question, top_k: ([chunk], [0.1])
    )

    finding = _make_finding()
    context = compliance_retrieval.retrieve_context_for_finding(db=None, finding=finding)

    assert context.chunks == [chunk]
    assert len(context.citations) == 1
    assert context.citations[0].clause_number == "A.8.24"


def test_retrieve_context_passes_query_and_top_k_through(monkeypatch):
    captured = {}

    def _fake_vector_search(db, question, top_k):
        captured["question"] = question
        captured["top_k"] = top_k
        return [], [0.1]

    monkeypatch.setattr(retrieval, "vector_search", _fake_vector_search)

    finding = _make_finding()
    try:
        compliance_retrieval.retrieve_context_for_finding(db=None, finding=finding, top_k=3)
    except compliance_retrieval.NoStandardsContextError:
        pass

    assert captured["top_k"] == 3
    assert finding.title in captured["question"]
