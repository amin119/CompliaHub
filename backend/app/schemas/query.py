import uuid

from pydantic import BaseModel


class QueryRequest(BaseModel):
    question: str
    top_k: int = 5
    # Phase 5 Part 2: omit for a new conversation; pass back the id a prior
    # response returned to continue it (only meaningful for `agent`-
    # classified questions — see docs/phase-5-agentic-loop.md for why
    # vector/graph-classified turns don't build conversation memory).
    conversation_id: str | None = None


class Citation(BaseModel):
    chunk_id: uuid.UUID
    # Phase 6: without this, the frontend has no way to fetch a citation's
    # full clause text (GET /documents/{id}/chunks needs the document id,
    # not just its filename) — added specifically to make "clickable
    # citations" a real feature instead of a metadata-only stub.
    document_id: uuid.UUID
    document_filename: str
    clause_number: str | None
    path: str


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation]
    conversation_id: str | None = None


class ConversationTurn(BaseModel):
    question: str
    answer: str


class ConversationResponse(BaseModel):
    conversation_id: str
    turns: list[ConversationTurn]
