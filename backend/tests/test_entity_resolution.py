from app.services.entity_resolution import normalize_name, resolve_entities
from app.services.ontology import EntityType, ExtractedEntity


def _fake_embed_similar_to(target_substring: str, base_vector, near_vector):
    """Builds a fake embed_fn: texts containing `target_substring` get
    `near_vector`, everything else gets `base_vector` — lets a test control
    exactly which names should end up "similar" without a real embedder.
    """

    def embed_fn(texts: list[str]) -> list[list[float]]:
        return [near_vector if target_substring in t.lower() else base_vector for t in texts]

    return embed_fn


def test_normalize_name_collapses_case_punctuation_whitespace():
    assert normalize_name("Personal Data") == "personal data"
    assert normalize_name("  personal   data.") == "personal data"
    assert normalize_name("PERSONAL-DATA!") == "personaldata"


def test_exact_match_merges_within_batch():
    candidates = [
        ExtractedEntity(name="Personal Data", entity_type=EntityType.ASSET),
        ExtractedEntity(name="personal data.", entity_type=EntityType.ASSET),
    ]

    resolved = resolve_entities(
        candidates, existing=[], embed_fn=lambda texts: [[0.0] for _ in texts]
    )

    assert len(resolved) == 1
    assert resolved[0].source_names == ["Personal Data", "personal data."]
    assert resolved[0].is_new is True


def test_different_entity_types_never_merge():
    candidates = [
        ExtractedEntity(name="Risk Assessment", entity_type=EntityType.PROCESS),
        ExtractedEntity(name="Risk Assessment", entity_type=EntityType.CONTROL),
    ]

    resolved = resolve_entities(
        candidates, existing=[], embed_fn=lambda texts: [[1.0] for _ in texts]
    )

    assert len(resolved) == 2


def test_embedding_similarity_merges_near_duplicates_above_threshold():
    candidates = [
        ExtractedEntity(name="Personal Data", entity_type=EntityType.ASSET),
        ExtractedEntity(name="PII", entity_type=EntityType.ASSET),
    ]
    embed_fn = _fake_embed_similar_to("pii", base_vector=[1.0, 0.0], near_vector=[1.0, 0.05])

    resolved = resolve_entities(candidates, existing=[], embed_fn=embed_fn)

    assert len(resolved) == 1
    assert "PII" in resolved[0].source_names


def test_embedding_similarity_does_not_merge_below_threshold():
    candidates = [
        ExtractedEntity(name="Personal Data", entity_type=EntityType.ASSET),
        ExtractedEntity(name="Risk Register", entity_type=EntityType.ASSET),
    ]
    # Orthogonal vectors -> cosine similarity 0.0, well under the threshold.
    embed_fn = lambda texts: [  # noqa: E731
        [1.0, 0.0] if "personal" in t.lower() else [0.0, 1.0] for t in texts
    ]

    resolved = resolve_entities(candidates, existing=[], embed_fn=embed_fn)

    assert len(resolved) == 2


def test_merges_into_existing_entity_via_similarity():
    candidates = [ExtractedEntity(name="PII", entity_type=EntityType.ASSET)]
    existing = [("Personal Data", EntityType.ASSET, [1.0, 0.0])]
    embed_fn = lambda texts: [[1.0, 0.05] for _ in texts]  # noqa: E731

    resolved = resolve_entities(candidates, existing=existing, embed_fn=embed_fn)

    assert len(resolved) == 1
    assert resolved[0].canonical_name == "Personal Data"
    assert resolved[0].is_new is False


def test_exact_match_against_existing_needs_no_embedding_call():
    candidates = [ExtractedEntity(name="Personal Data", entity_type=EntityType.ASSET)]
    existing = [("Personal Data", EntityType.ASSET, [1.0, 0.0])]

    def embed_fn(texts):
        raise AssertionError("should not be called — exact match found first")

    resolved = resolve_entities(candidates, existing=existing, embed_fn=embed_fn)

    assert len(resolved) == 1
    assert resolved[0].is_new is False
