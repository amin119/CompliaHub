import uuid

from langgraph.checkpoint.memory import MemorySaver

from app.models.document import Chunk, Document
from app.services import agent, answer_generation, retrieval


def _make_chunk(clause_number: str, text: str) -> Chunk:
    chunk = Chunk(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        clause_number=clause_number,
        title=None,
        text=text,
        path="standard.section",
        order_in_parent=0,
    )
    chunk.document = Document(filename="standard.docx", sha256_hash="x", minio_object_key="k")
    return chunk


class _FakeGemini:
    """Dispatches by schema — `agent.CritiqueResult` vs `agent.RewriteResult`
    vs `agent.CondensedQuestion` — so a fixed sequence of critique verdicts
    can be scripted per test without caring exactly how many rewrite calls
    happen in between.
    """

    def __init__(self, critique_sequence: list[bool]):
        self.critique_sequence = list(critique_sequence)
        self.critique_calls = 0
        self.rewrite_calls = 0
        self.condense_calls = 0

    def __call__(self, api_key, model, system_prompt, contents, schema):
        if schema is agent.CritiqueResult:
            sufficient = self.critique_sequence[self.critique_calls]
            self.critique_calls += 1
            return agent.CritiqueResult(sufficient=sufficient)
        if schema is agent.RewriteResult:
            self.rewrite_calls += 1
            return agent.RewriteResult(rewritten_query=f"rewritten query {self.rewrite_calls}")
        if schema is agent.CondensedQuestion:
            self.condense_calls += 1
            return agent.CondensedQuestion(standalone_question=f"standalone {self.condense_calls}")
        raise AssertionError(f"unexpected schema {schema}")


def _patch_retrieval(monkeypatch, chunks):
    monkeypatch.setattr(retrieval, "vector_search", lambda db, question, top_k: (chunks, [0.1]))
    monkeypatch.setattr(retrieval, "local_search_facts", lambda driver, context_chunks: [])
    monkeypatch.setattr(retrieval, "global_search_context", lambda driver, query_vector: [])
    monkeypatch.setattr(
        answer_generation, "generate_answer", lambda *a, **k: "final answer"
    )


def test_answers_immediately_when_critique_is_satisfied_on_first_pass(monkeypatch):
    chunk = _make_chunk("A.1", "relevant text")
    _patch_retrieval(monkeypatch, [chunk])
    fake_gemini = _FakeGemini(critique_sequence=[True])
    monkeypatch.setattr(agent, "_call_gemini_structured", fake_gemini)

    response = agent.run_agent(
        "some question", db=None, driver=None, checkpointer=MemorySaver(), max_iterations=3
    )

    assert response.answer == "final answer"
    assert fake_gemini.critique_calls == 1
    assert fake_gemini.rewrite_calls == 0


def test_loops_once_after_insufficient_critique_then_answers(monkeypatch):
    chunk = _make_chunk("A.1", "relevant text")
    _patch_retrieval(monkeypatch, [chunk])
    fake_gemini = _FakeGemini(critique_sequence=[False, True])
    monkeypatch.setattr(agent, "_call_gemini_structured", fake_gemini)

    response = agent.run_agent(
        "some question", db=None, driver=None, checkpointer=MemorySaver(), max_iterations=3
    )

    assert response.answer == "final answer"
    assert fake_gemini.critique_calls == 2
    assert fake_gemini.rewrite_calls == 1


def test_stops_at_max_iterations_even_if_never_satisfied(monkeypatch):
    chunk = _make_chunk("A.1", "relevant text")
    _patch_retrieval(monkeypatch, [chunk])
    # Critique always says insufficient — the budget, not the model, must
    # be what ends the loop.
    fake_gemini = _FakeGemini(critique_sequence=[False, False, False, False, False])
    monkeypatch.setattr(agent, "_call_gemini_structured", fake_gemini)

    response = agent.run_agent(
        "some question", db=None, driver=None, checkpointer=MemorySaver(), max_iterations=2
    )

    assert response.answer == "final answer"
    # Budget of 2 iterations: critique runs once per iteration, the second
    # (final) call is short-circuited to sufficient=True by the budget
    # check itself, never reaching the fake — so only 1 real critique call
    # and 1 rewrite happen before the budget forces an answer.
    assert fake_gemini.critique_calls == 1
    assert fake_gemini.rewrite_calls == 1


def test_global_search_only_enabled_after_first_pass(monkeypatch):
    chunk = _make_chunk("A.1", "relevant text")
    global_search_calls = []
    monkeypatch.setattr(retrieval, "vector_search", lambda db, question, top_k: ([chunk], [0.1]))
    monkeypatch.setattr(retrieval, "local_search_facts", lambda driver, context_chunks: [])
    monkeypatch.setattr(
        retrieval,
        "global_search_context",
        lambda driver, query_vector: global_search_calls.append(1) or [],
    )
    monkeypatch.setattr(answer_generation, "generate_answer", lambda *a, **k: "final answer")
    fake_gemini = _FakeGemini(critique_sequence=[False, True])
    monkeypatch.setattr(agent, "_call_gemini_structured", fake_gemini)

    agent.run_agent(
        "some question", db=None, driver=None, checkpointer=MemorySaver(), max_iterations=3
    )

    # First retrieve pass: use_global_search is False (iteration 0) — no
    # call. Second pass (after rewrite): iteration 1 — global search runs.
    assert len(global_search_calls) == 1


def test_new_conversation_generates_and_returns_a_fresh_id(monkeypatch):
    chunk = _make_chunk("A.1", "relevant text")
    _patch_retrieval(monkeypatch, [chunk])
    fake_gemini = _FakeGemini(critique_sequence=[True])
    monkeypatch.setattr(agent, "_call_gemini_structured", fake_gemini)

    response = agent.run_agent(
        "some question", db=None, driver=None, checkpointer=MemorySaver()
    )

    assert response.conversation_id is not None
    # No history yet on a first turn — condense_question must skip the LLM
    # call entirely rather than pay for a no-op rewrite.
    assert fake_gemini.condense_calls == 0


def test_continuing_a_conversation_condenses_the_follow_up_and_keeps_the_same_id(monkeypatch):
    chunk = _make_chunk("A.1", "relevant text")
    _patch_retrieval(monkeypatch, [chunk])
    fake_gemini = _FakeGemini(critique_sequence=[True, True])
    monkeypatch.setattr(agent, "_call_gemini_structured", fake_gemini)
    checkpointer = MemorySaver()

    first = agent.run_agent(
        "What does ISO 27001 say about access control?",
        db=None,
        driver=None,
        checkpointer=checkpointer,
    )
    assert fake_gemini.condense_calls == 0  # first turn, no history yet

    second = agent.run_agent(
        "What about GDPR?",
        db=None,
        driver=None,
        checkpointer=checkpointer,
        conversation_id=first.conversation_id,
    )

    assert second.conversation_id == first.conversation_id
    # Second turn has history from the first — condense_question must run.
    assert fake_gemini.condense_calls == 1


def test_conversation_history_survives_across_separate_run_agent_calls(monkeypatch):
    """The real point of Part 2: history isn't just passed through in
    memory within one call — it persists in the checkpointer and is read
    back on a *separate* `run_agent` invocation for the same thread.
    """
    chunk = _make_chunk("A.1", "relevant text")
    _patch_retrieval(monkeypatch, [chunk])

    captured_prompts = []

    def _fake_gemini(api_key, model, system_prompt, contents, schema):
        if schema is agent.CondensedQuestion:
            captured_prompts.append(contents)
            return agent.CondensedQuestion(standalone_question="standalone")
        if schema is agent.CritiqueResult:
            return agent.CritiqueResult(sufficient=True)
        raise AssertionError(f"unexpected schema {schema}")

    monkeypatch.setattr(agent, "_call_gemini_structured", _fake_gemini)
    checkpointer = MemorySaver()

    first = agent.run_agent(
        "What does ISO 27001 say about access control?",
        db=None,
        driver=None,
        checkpointer=checkpointer,
    )
    agent.run_agent(
        "What about GDPR?",
        db=None,
        driver=None,
        checkpointer=checkpointer,
        conversation_id=first.conversation_id,
    )

    assert len(captured_prompts) == 1
    assert "What does ISO 27001 say about access control?" in captured_prompts[0]
    assert "final answer" in captured_prompts[0]


def test_unknown_conversation_id_falls_back_to_a_fresh_conversation(monkeypatch):
    """A client passing a stale/bogus conversation_id (expired, typo'd,
    from a different environment) must not crash — treated the same as no
    conversation_id at all.
    """
    chunk = _make_chunk("A.1", "relevant text")
    _patch_retrieval(monkeypatch, [chunk])
    fake_gemini = _FakeGemini(critique_sequence=[True])
    monkeypatch.setattr(agent, "_call_gemini_structured", fake_gemini)

    response = agent.run_agent(
        "some question",
        db=None,
        driver=None,
        checkpointer=MemorySaver(),
        conversation_id="never-seen-before",
    )

    assert response.conversation_id == "never-seen-before"
    assert fake_gemini.condense_calls == 0
