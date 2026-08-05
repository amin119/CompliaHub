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


class CommunityResponse(BaseModel):
    id: str
    title: str
    summary: str
    entity_count: int


class CommunityListResponse(BaseModel):
    communities: list[CommunityResponse]
