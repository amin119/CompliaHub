import uuid

from pydantic import BaseModel


class QueryRequest(BaseModel):
    question: str
    top_k: int = 5


class Citation(BaseModel):
    chunk_id: uuid.UUID
    document_filename: str
    clause_number: str | None
    path: str


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation]
