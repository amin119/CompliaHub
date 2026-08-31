from app.services.ai_analysis.rag_detection import _detect_python
from app.services.security_analysis.ast_utils import safe_parse
from app.services.security_analysis.base import RuleContext


def _python_context(source: str) -> RuleContext:
    return RuleContext(
        relative_path="app/rag.py",
        language="python",
        component_type="application_code",
        text=source,
        tree=safe_parse(source),
    )


def test_flags_vector_db_plus_embedding_call():
    source = "import qdrant_client\n\ndef embed_and_store(text):\n    return client.embed(text)\n"
    hits = _detect_python(_python_context(source))
    assert len(hits) == 1
    assert hits[0].confidence == "medium"


def test_flags_vector_db_plus_retrieval_function_name():
    source = (
        "import qdrant_client\n\ndef retrieve_context(query):\n    return client.search(query)\n"
    )
    hits = _detect_python(_python_context(source))
    assert len(hits) == 1


def test_does_not_flag_vector_db_alone():
    source = "import qdrant_client\n\ndef list_collections():\n    return client.list()\n"
    assert _detect_python(_python_context(source)) == []


def test_does_not_flag_embedding_call_without_vector_db():
    source = "def embed(text):\n    return model.encode(text)\n"
    assert _detect_python(_python_context(source)) == []
