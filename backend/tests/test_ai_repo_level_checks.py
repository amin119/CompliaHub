from dataclasses import dataclass

from app.services.ai_analysis.repo_level_checks import (
    build_ai_repo_level_findings,
    model_card_doc_present,
)


@dataclass
class _FakeFile:
    relative_path: str
    component_type: str


# --- model_card_doc_present -------------------------------------------------


def test_model_card_doc_detected():
    files = [_FakeFile("docs/MODEL_CARD.md", "documentation")]
    assert model_card_doc_present(files) is True


def test_model_card_doc_requires_documentation_component_type():
    files = [_FakeFile("model_card.md", "unknown")]
    assert model_card_doc_present(files) is False


def test_no_model_card_doc_returns_false():
    files = [_FakeFile("README.md", "documentation")]
    assert model_card_doc_present(files) is False


# --- build_ai_repo_level_findings -------------------------------------------


def test_below_threshold_produces_no_findings():
    # A single signal type — must not promote to "AI system detected".
    pairs = build_ai_repo_level_findings(
        signal_categories={"ai_system_detection"},
        ai_provider_labels=set(),
        model_card_present=False,
    )
    assert pairs == []


def test_at_threshold_produces_inventory_and_nine_governance_findings():
    pairs = build_ai_repo_level_findings(
        signal_categories={"ai_system_detection", "rag_detection"},
        ai_provider_labels={"OpenAI"},
        model_card_present=False,
    )
    categories = [category for category, _hit in pairs]
    assert categories.count("ai_system_inventory") == 1
    # Inventory + 9 fixed governance findings.
    assert len(pairs) == 10


def test_inventory_metadata_shape():
    pairs = build_ai_repo_level_findings(
        signal_categories={"ai_system_detection", "agentic_pattern_detection"},
        ai_provider_labels={"OpenAI", "Cohere"},
        model_card_present=False,
    )
    inventory_hit = next(hit for category, hit in pairs if category == "ai_system_inventory")
    metadata = inventory_hit.evidence_metadata
    assert metadata["human_oversight"] == "unknown"
    assert metadata["uses_tools"] is True
    assert metadata["uses_rag"] is False
    assert metadata["external_data"] is True
    assert {m["provider"] for m in metadata["models"]} == {"OpenAI", "Cohere"}
    assert all(m["model"] == "detected_from_code" for m in metadata["models"])


def test_model_card_present_raises_confidence():
    without = build_ai_repo_level_findings(
        signal_categories={"ai_system_detection", "rag_detection"},
        ai_provider_labels=set(),
        model_card_present=False,
    )
    with_doc = build_ai_repo_level_findings(
        signal_categories={"ai_system_detection", "rag_detection"},
        ai_provider_labels=set(),
        model_card_present=True,
    )
    governance_without = [hit for category, hit in without if category != "ai_system_inventory"]
    governance_with = [hit for category, hit in with_doc if category != "ai_system_inventory"]
    assert all(hit.confidence == "low" for hit in governance_without)
    assert all(hit.confidence == "medium" for hit in governance_with)
    assert any("not been verified" in hit.reasoning for hit in governance_with)
