import pytest
from pydantic import ValidationError

from app.services.ontology import (
    ChunkExtraction,
    EntityType,
    ExtractedEntity,
    ExtractedRelation,
    RelationType,
)


def test_valid_extraction_accepted():
    extraction = ChunkExtraction(
        entities=[ExtractedEntity(name="Risk Assessment", entity_type=EntityType.PROCESS)],
        relations=[],
    )
    assert extraction.entities[0].name == "Risk Assessment"


def test_out_of_enum_entity_type_rejected():
    with pytest.raises(ValidationError):
        ExtractedEntity(name="Something", entity_type="NotARealType")


def test_out_of_enum_relation_type_rejected():
    with pytest.raises(ValidationError):
        ExtractedRelation(source="A", relation_type="not_a_real_relation", target="B")


def test_dangling_relation_rejected():
    """A relation whose source/target isn't in this chunk's own `entities`
    list is malformed output — must fail loudly (and get retried by the
    extraction client), not silently load a relation pointing at nothing.
    """
    with pytest.raises(ValidationError, match="not declared"):
        ChunkExtraction(
            entities=[ExtractedEntity(name="A", entity_type=EntityType.CONTROL)],
            relations=[
                ExtractedRelation(source="A", relation_type=RelationType.REQUIRES, target="B")
            ],
        )


def test_empty_extraction_is_valid():
    """A chunk with no clear entities/relations should under-extract (empty
    lists), not be forced to invent something.
    """
    extraction = ChunkExtraction()
    assert extraction.entities == []
    assert extraction.relations == []
