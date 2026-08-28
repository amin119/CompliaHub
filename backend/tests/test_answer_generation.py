import uuid

from app.models.document import Chunk
from app.services import answer_generation


class _FakeAnswerClient:
    def __init__(self, response: str = "fake answer", chunks: list[str] | None = None):
        self.response = response
        self.chunks = chunks if chunks is not None else [response]
        self.last_call: dict | None = None

    def create_completion(self, model, messages, max_tokens):
        self.last_call = {"model": model, "messages": messages, "max_tokens": max_tokens}
        return self.response

    def stream_completion(self, model, messages, max_tokens):
        self.last_call = {"model": model, "messages": messages, "max_tokens": max_tokens}
        yield from self.chunks


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


def test_stream_answer_yields_each_chunk_from_the_client():
    client = _FakeAnswerClient(chunks=["The ", "answer ", "arrives ", "in ", "pieces."])

    result = list(answer_generation.stream_answer("question?", [], client=client))

    assert result == ["The ", "answer ", "arrives ", "in ", "pieces."]
    assert "".join(result) == "The answer arrives in pieces."


def test_stream_answer_uses_the_same_prompt_shape_as_generate_answer():
    client = _FakeAnswerClient()
    chunks = [_make_chunk("A.1", "first chunk text")]

    list(answer_generation.stream_answer("question?", chunks, client=client))

    system_message, user_message = client.last_call["messages"]
    assert system_message["role"] == "system"
    assert "compliance assistant" in system_message["content"]
    assert "[1] (A.1) first chunk text" in user_message["content"]
