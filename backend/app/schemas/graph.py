from pydantic import BaseModel


class GraphEntity(BaseModel):
    name: str
    entity_type: str


class GraphRelation(BaseModel):
    source: GraphEntity
    relation_type: str
    target: GraphEntity
    chunk_id: str


class DocumentGraphResponse(BaseModel):
    relations: list[GraphRelation]
