from enum import Enum

from pydantic import BaseModel, Field, model_validator

# Fixed set from the roadmap. Forced-enum, not open-ended — an LLM free to
# invent new entity types would make entity resolution and Cypher queries
# unreliable (you can't write `MATCH (n:Control)` if the model sometimes
# emits `:SecurityControl` for the same concept).
#
# These class docstrings are kept short deliberately: Pydantic's
# `model_json_schema()` embeds them verbatim as the `description` field sent
# to the LLM on every extraction call (this schema *is* the tool definition
# handed to the model) — anything here should help it extract correctly, not
# document our own internal design rationale.


class EntityType(str, Enum):
    STANDARD = "Standard"
    CLAUSE = "Clause"
    CONTROL = "Control"
    REQUIREMENT = "Requirement"
    RISK = "Risk"
    ASSET = "Asset"
    PROCESS = "Process"
    ROLE = "Role"
    DEFINITION = "Definition"


class RelationType(str, Enum):
    REQUIRES = "requires"
    REFERENCES = "references"
    IMPLEMENTS = "implements"
    MAPS_TO = "maps_to"
    IS_PREREQUISITE_FOR = "is_prerequisite_for"
    APPLIES_TO = "applies_to"
    DEFINED_IN = "defined_in"
    PART_OF = "part_of"
    SUPERSEDED_BY = "superseded_by"


class ExtractedEntity(BaseModel):
    """An entity mentioned in this chunk's text."""

    name: str
    entity_type: EntityType
    description: str = ""


class ExtractedRelation(BaseModel):
    """A relation between two entities named in this chunk's `entities`."""

    source: str
    relation_type: RelationType
    target: str


class ChunkExtraction(BaseModel):
    """All entities and relations found in this chunk. Return empty lists if
    the text doesn't contain any.
    """

    entities: list[ExtractedEntity] = Field(default_factory=list)
    relations: list[ExtractedRelation] = Field(default_factory=list)

    @model_validator(mode="after")
    def relations_reference_declared_entities(self) -> "ChunkExtraction":
        """Rejects a dangling relation (pointing at an entity name the model
        didn't also declare in `entities`) rather than silently loading a
        relation into the graph that points at nothing — malformed output
        should fail loudly and get retried, not corrupt the graph.

        (This validator's own docstring is never sent to the LLM — only
        model/field descriptions end up in the JSON schema, not method docs —
        so it's fine for this one to explain the internal rationale.)
        """
        names = {entity.name for entity in self.entities}
        for relation in self.relations:
            if relation.source not in names or relation.target not in names:
                raise ValueError(
                    f"relation {relation.source!r} --{relation.relation_type}--> "
                    f"{relation.target!r} references an entity not declared in "
                    "this chunk's own `entities` list"
                )
        return self
