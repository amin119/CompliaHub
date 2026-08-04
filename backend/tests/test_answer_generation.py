import uuid

from app.models.document import Chunk
from app.services import answer_generation


class _FakeAnswerClient:
    def __init__(self, response: str = "fake answer"):
        self.response = response
        self.last_call: dict | None = None

    def create_completion(self, model, messages, max_tokens):
        self.last_call = {"model": model, "messages": messages, "max_tokens": max_tokens}
        return self.response


def _make_chunk(clause_number: str, text: str) -> Chunk:
    return Chunk(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        clause_number=clause_number,
        title=None,
        text=text,
        path="standard.section",
        order_in_parent=0,
    )


def test_generate_answer_returns_client_response():
    client = _FakeAnswerClient(response="the answer")
    result = answer_generation.generate_answer("question?", [], client=client)
    assert result == "the answer"


def test_generate_answer_includes_system_prompt():
    client = _FakeAnswerClient()
    answer_generation.generate_answer("question?", [], client=client)
    system_message = client.last_call["messages"][0]
    assert system_message["role"] == "system"
    assert "compliance assistant" in system_message["content"]


def test_generate_answer_formats_citations_with_clause_numbers():
    client = _FakeAnswerClient()
    chunks = [_make_chunk("A.1", "first chunk text"), _make_chunk("A.2", "second chunk text")]

    answer_generation.generate_answer("question?", chunks, client=client)

    user_message = client.last_call["messages"][1]
    assert "[1] (A.1) first chunk text" in user_message["content"]
    assert "[2] (A.2) second chunk text" in user_message["content"]
