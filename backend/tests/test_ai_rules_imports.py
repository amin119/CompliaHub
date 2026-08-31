from app.services.ai_analysis.ai_imports import _detect_python, detect_ai_imports
from app.services.security_analysis.ast_utils import safe_parse
from app.services.security_analysis.base import RuleContext


def _python_context(source: str) -> RuleContext:
    return RuleContext(
        relative_path="app/llm.py",
        language="python",
        component_type="application_code",
        text=source,
        tree=safe_parse(source),
    )


def test_detects_llm_provider_import():
    hits = _detect_python(_python_context("import openai\n"))
    assert len(hits) == 1
    assert hits[0].confidence == "low"
    assert hits[0].status == "REQUIRES_HUMAN_REVIEW"


def test_detects_vector_db_import():
    hits = _detect_python(_python_context("import qdrant_client\n"))
    assert len(hits) == 1
    assert "vector db" in hits[0].summary


def test_detects_ml_framework_import():
    hits = _detect_python(_python_context("import torch\n"))
    assert len(hits) == 1


def test_does_not_flag_unrelated_import():
    assert _detect_python(_python_context("import os\nimport json\n")) == []


def test_one_finding_per_distinct_package_per_file():
    source = "import cohere\nfrom cohere import Client\n"
    assert len(_detect_python(_python_context(source))) == 1


def test_detect_ai_imports_returns_structured_kind():
    results = detect_ai_imports(_python_context("import openai\nimport qdrant_client\n"))
    kinds = {name: kind for name, _label, kind, _line in results}
    assert kinds["openai"] == "llm_provider"
    assert kinds["qdrant_client"] == "vector_db"
