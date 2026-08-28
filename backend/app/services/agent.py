import operator
import uuid
from typing import Annotated, TypedDict

from google import genai
from google.genai import types
from langgraph.config import get_stream_writer
from langgraph.graph import END, StateGraph
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.document import Chunk
from app.schemas.query import Citation, QueryResponse
from app.services import answer_generation, retrieval
from app.services import streaming_events as events
from app.services.graph_store import CommunityWithEmbedding, ProvenancedRelationEdge

# Part 1 scope decision (still true in Part 2): critique/rewrite/condense
# below call Gemini directly, with no retry/Protocol-fake-client apparatus
# like extraction.py's or query_classifier.py's adapters have — a
# transient failure here just fails the /query request, same as any other
# current failure mode (e.g. the xAI billing block). Hardening this is
# natural follow-up work, not worth the added indirection for this loop.
_CRITIQUE_PROMPT = (
    "You are checking whether gathered evidence is enough to confidently "
    "and specifically answer a compliance question (ISO 27001/42001/GDPR). "
    "Say insufficient if the evidence is empty, off-topic, or only "
    "tangentially related — don't be lenient just because *something* was "
    "retrieved."
)
_REWRITE_PROMPT = (
    "You are reformulating a search query that didn't surface enough "
    "evidence to answer a compliance question. Given the original question "
    "and what was already tried, write a different, more specific search "
    "query likely to surface the missing information — not a restatement "
    "of the same query."
)
_CONDENSE_PROMPT = (
    "You are rewriting a follow-up question into a standalone question, "
    "using the prior conversation for context (e.g. \"what about GDPR?\" "
    "after a question about ISO 27001 access control becomes \"what does "
    "GDPR require regarding access control?\"). If the question is already "
    "standalone — doesn't reference or depend on prior turns — return it "
    "unchanged. Do not answer the question, only rewrite it."
)

# Budget/stop condition (roadmap step 3): bounds how many retrieve/critique/
# rewrite rounds the agent can spend on one question — an empirical
# starting point, same "tune against real use" spirit as every other
# constant like this in this project (extraction pacing, local search hop
# count).
DEFAULT_MAX_ITERATIONS = 2


class CritiqueResult(BaseModel):
    sufficient: bool


class RewriteResult(BaseModel):
    rewritten_query: str


class CondensedQuestion(BaseModel):
    standalone_question: str


class AgentState(TypedDict):
    """Every field here gets written to the checkpointer after each node —
    confirmed live that even `MemorySaver` (in-memory) msgpack-serializes
    state on every transition, not just a real persistent backend (Part
    2's `PostgresSaver`). `Chunk` (a SQLAlchemy ORM object) doesn't survive
    that — `context_chunk_ids` holds plain UUID strings instead, and nodes
    that need the real rows resolve them from a chunk cache living outside
    checkpointed state entirely (see `build_agent`). `Citation` (pydantic)
    and `ProvenancedRelationEdge`/`CommunityWithEmbedding` (NamedTuples,
    including their `EntityType` enum fields) were confirmed to serialize
    fine as-is.

    `conversation_history` is the one field with a non-default reducer
    (`operator.add`, append rather than overwrite) — Part 2's multi-turn
    memory depends on it *accumulating* across separate `run_agent` calls
    on the same `conversation_id`/thread, confirmed live that a persistent
    checkpointer plus an append reducer is exactly what makes "send only
    the new turn's fields, the rest resume from the last checkpoint" work
    (see docs/phase-5-agentic-loop.md's experiment).
    """

    question: str
    search_query: str
    context_chunk_ids: list[str]
    query_vector: list[float]
    graph_relations: list[ProvenancedRelationEdge]
    community_drilldowns: list[tuple[CommunityWithEmbedding, list[ProvenancedRelationEdge]]]
    use_global_search: bool
    iteration: int
    max_iterations: int
    sufficient: bool
    answer: str
    citations: list[Citation]
    conversation_history: Annotated[list[dict], operator.add]


def _call_gemini_structured(api_key: str, model: str, system_prompt: str, contents: str, schema):
    """Constructs its own `genai.Client` per call rather than taking one as
    a parameter — deliberately, so that mocking this one function (as
    tests do) never constructs a real client at all. `genai.Client(...)`
    raises immediately if `api_key` is empty, which it always is in the
    test environment (no `GEMINI_API_KEY` in `backend/.env` by default);
    building the client eagerly in `build_agent` instead would make every
    agent test require a real key just to *construct* the graph, even with
    this function itself fully mocked out.
    """
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            response_schema=schema,
        ),
    )
    # Re-validate ourselves rather than trusting response.parsed — same
    # reasoning as every other Gemini adapter in this project: .parsed may
    # be built through a path that skips a custom validator.
    return schema.model_validate_json(response.text)


def _format_history(history: list[dict]) -> str:
    return "\n".join(f"Q: {turn['question']}\nA: {turn['answer']}" for turn in history)


def _summarize_evidence(state: AgentState, context_chunks: list[Chunk]) -> str:
    if not context_chunks:
        return "(none found)"
    lines = [f"- ({c.clause_number or c.title}) {c.text[:200]}" for c in context_chunks]
    if state["graph_relations"]:
        lines.append(f"Plus {len(state['graph_relations'])} graph relations.")
    if state["community_drilldowns"]:
        lines.append(f"Plus {len(state['community_drilldowns'])} related themes.")
    return "\n".join(lines)


def build_agent(db: Session, driver, checkpointer, max_iterations: int = DEFAULT_MAX_ITERATIONS):
    """Builds the Phase 5 agent graph: condense_question -> plan -> retrieve
    -> critique -> (answer | rewrite_query -> plan), looping until critique
    is satisfied or `max_iterations` is spent.

    `checkpointer` is injected, not hardcoded — Part 1 always used an
    in-memory `MemorySaver`; Part 2 passes a real `PostgresSaver` (see
    `app/core/checkpointer.py`) for the actual `/query` route, while tests
    can still pass a fresh `MemorySaver()` (or any `BaseCheckpointSaver`)
    without needing live Postgres.

    `db`/`driver` are captured via closure, not put in `AgentState`, for
    the same reason `context_chunk_ids` (not raw `Chunk` rows) is: neither
    a live SQLAlchemy Session nor a Neo4j Driver is serializable, and
    there's no cheap "serialize as an id, resolve later" trick for either
    of them the way there is for chunks.
    """
    settings = get_settings()
    api_key = settings.gemini_api_key
    model = settings.gemini_extraction_model

    # Real `Chunk` rows this run has fetched, keyed by id — populated by
    # `retrieve_node`, read by every node that needs actual chunk text
    # (`critique`/`rewrite_query`/`answer`). Lives in this closure, *not*
    # `AgentState`, specifically because it isn't checkpointer-serializable
    # (see `AgentState`'s docstring) — one cache per agent run, discarded
    # once `run_agent` returns.
    chunk_cache: dict[str, Chunk] = {}

    def _resolve_chunks(state: AgentState) -> list[Chunk]:
        return [chunk_cache[chunk_id] for chunk_id in state["context_chunk_ids"]]

    def condense_question_node(state: AgentState) -> dict:
        # Runs once per turn, before planning/retrieval even starts. A
        # brand-new conversation (or a self-contained follow-up) has no
        # history to condense against — skip the LLM call (and the status
        # event — nothing is actually happening yet) entirely rather than
        # pay for a no-op rewrite.
        if not state["conversation_history"]:
            return {"search_query": state["question"]}
        get_stream_writer()(events.status_event("condensing_question"))
        prompt = (
            f"Conversation so far:\n{_format_history(state['conversation_history'])}\n\n"
            f"Follow-up question: {state['question']}"
        )
        result = _call_gemini_structured(
            api_key, model, _CONDENSE_PROMPT, prompt, CondensedQuestion
        )
        return {"search_query": result.standalone_question}

    def plan_node(state: AgentState) -> dict:
        # Deliberately simple/deterministic for Part 1, not an LLM call:
        # the first pass is always vector + local search (cheap, broad
        # coverage); global (thematic) search only turns on once a first
        # pass has already been tried and found insufficient — real cost
        # savings for the common case where local evidence is enough. A
        # genuinely LLM-driven planner is natural follow-up work, not
        # required to make "plan" a real, distinct step already.
        get_stream_writer()(events.status_event("planning"))
        return {"use_global_search": state["iteration"] > 0}

    def retrieve_node(state: AgentState) -> dict:
        get_stream_writer()(events.status_event("retrieving"))
        context_chunks, query_vector = retrieval.vector_search(
            db, state["search_query"], top_k=5
        )
        graph_relations = retrieval.local_search_facts(driver, context_chunks)
        community_drilldowns = (
            retrieval.global_search_context(driver, query_vector)
            if state["use_global_search"]
            else []
        )
        for chunk in context_chunks:
            chunk_cache[str(chunk.id)] = chunk

        # Accumulate across iterations — a rewritten query is meant to
        # surface *more* evidence, not replace what the first pass found.
        existing_ids = set(state["context_chunk_ids"])
        new_ids = [str(chunk.id) for chunk in context_chunks if str(chunk.id) not in existing_ids]
        return {
            "context_chunk_ids": state["context_chunk_ids"] + new_ids,
            "query_vector": query_vector,
            "graph_relations": state["graph_relations"] + graph_relations,
            "community_drilldowns": state["community_drilldowns"] + community_drilldowns,
            "iteration": state["iteration"] + 1,
        }

    def critique_node(state: AgentState) -> dict:
        get_stream_writer()(events.status_event("critiquing"))
        if state["iteration"] >= state["max_iterations"]:
            # Budget exhausted (roadmap step 3) — answer with whatever
            # evidence exists rather than looping forever.
            return {"sufficient": True}
        prompt = (
            f"Question: {state['question']}\n\n"
            f"Evidence gathered so far:\n{_summarize_evidence(state, _resolve_chunks(state))}"
        )
        result = _call_gemini_structured(api_key, model, _CRITIQUE_PROMPT, prompt, CritiqueResult)
        return {"sufficient": result.sufficient}

    def rewrite_query_node(state: AgentState) -> dict:
        get_stream_writer()(events.status_event("rewriting_query"))
        prompt = (
            f"Original question: {state['question']}\n"
            f"Search query tried: {state['search_query']}\n"
            "Evidence gathered so far (insufficient):\n"
            f"{_summarize_evidence(state, _resolve_chunks(state))}"
        )
        result = _call_gemini_structured(api_key, model, _REWRITE_PROMPT, prompt, RewriteResult)
        return {"search_query": result.rewritten_query}

    def answer_node(state: AgentState) -> dict:
        writer = get_stream_writer()
        writer(events.status_event("generating_answer"))
        context_chunks = _resolve_chunks(state)
        graph_facts, community_context, citations = retrieval.render_evidence(
            db, context_chunks, state["graph_relations"], state["community_drilldowns"]
        )
        # Always sourced via the streaming Gemini API and accumulated here,
        # whether this run was itself invoked via `.invoke()` or `.stream()`
        # — `writer` is a real no-op in the former case (see
        # `run_agent`/`stream_agent`), so there's no special-casing needed
        # to get one code path that works for both.
        answer_chunks = []
        for token in answer_generation.stream_answer(
            state["question"],
            context_chunks,
            graph_facts=graph_facts,
            community_context=community_context,
        ):
            answer_chunks.append(token)
            writer(events.token_event(token))
        answer = "".join(answer_chunks)
        return {
            "answer": answer,
            "citations": citations,
            # A single new entry — the `operator.add` reducer appends this
            # to whatever this thread's conversation_history already held
            # (empty for a new conversation, prior turns for a continuing
            # one), it does not overwrite.
            "conversation_history": [{"question": state["question"], "answer": answer}],
        }

    def route_after_critique(state: AgentState) -> str:
        return "answer" if state["sufficient"] else "rewrite_query"

    graph = StateGraph(AgentState)
    graph.add_node("condense_question", condense_question_node)
    graph.add_node("plan", plan_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("critique", critique_node)
    graph.add_node("rewrite_query", rewrite_query_node)
    graph.add_node("answer", answer_node)
    graph.set_entry_point("condense_question")
    graph.add_edge("condense_question", "plan")
    graph.add_edge("plan", "retrieve")
    graph.add_edge("retrieve", "critique")
    graph.add_conditional_edges(
        "critique", route_after_critique, {"answer": "answer", "rewrite_query": "rewrite_query"}
    )
    graph.add_edge("rewrite_query", "plan")
    graph.add_edge("answer", END)
    return graph.compile(checkpointer=checkpointer)


def _fresh_turn_fields(question: str, max_iterations: int) -> dict:
    """Fields that reset every turn, whether this is a brand-new
    conversation or the Nth turn of an existing one — retrieval starts
    over each time, only `conversation_history` persists across turns.
    """
    return {
        "question": question,
        "search_query": question,
        "context_chunk_ids": [],
        "query_vector": [],
        "graph_relations": [],
        "community_drilldowns": [],
        "use_global_search": False,
        "iteration": 0,
        "max_iterations": max_iterations,
        "sufficient": False,
        "answer": "",
        "citations": [],
    }


def run_agent(
    question: str,
    db: Session,
    driver,
    checkpointer,
    conversation_id: str | None = None,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
) -> QueryResponse:
    """Runs one turn of the agent loop and returns the answer/citations,
    with `QueryResponse.conversation_id` always set so the caller can pass
    it back to continue the same conversation later.

    `conversation_id` doubles as the LangGraph thread id. Confirmed live
    (see docs/phase-5-agentic-loop.md) that a **partial** input dict on an
    *existing* thread correctly resumes from the last checkpoint — omitted
    keys keep their checkpointed value, `conversation_history`'s append
    reducer means it accumulates rather than resets — but a **brand-new**
    thread needs the *full* state dict, or the first node to read a
    not-yet-set key raises `KeyError`. `compiled.get_state(config).values`
    is `{}` for a thread with no checkpoint yet, which is exactly the
    signal used to tell the two cases apart.
    """
    compiled = build_agent(db, driver, checkpointer, max_iterations)
    thread_id = conversation_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    is_new_conversation = not compiled.get_state(config).values

    input_state = _fresh_turn_fields(question, max_iterations)
    if is_new_conversation:
        input_state["conversation_history"] = []

    final_state = compiled.invoke(input_state, config=config)
    graph_evidence = retrieval.build_graph_evidence(
        final_state["graph_relations"], final_state["community_drilldowns"]
    )
    return QueryResponse(
        answer=final_state["answer"],
        citations=final_state["citations"],
        conversation_id=thread_id,
        graph_evidence=graph_evidence,
    )


def stream_agent(
    question: str,
    db: Session,
    driver,
    checkpointer,
    conversation_id: str | None = None,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
):
    """Phase 6 Part 2: same one-turn agent run as `run_agent`, but yields
    `streaming_events` dicts as the graph executes instead of only
    returning the final `QueryResponse`.

    `stream_mode="custom"` surfaces exactly (and only) what each node
    explicitly pushes through `get_stream_writer()` — no LangGraph-internal
    bookkeeping leaks into what reaches the frontend. The final `done` event
    is appended here, after the graph itself has finished, rather than
    pushed by a node — it needs `graph_evidence`, which (like `run_agent`)
    is computed from the finished checkpoint state, not something any single
    node has access to mid-run.
    """
    compiled = build_agent(db, driver, checkpointer, max_iterations)
    thread_id = conversation_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    is_new_conversation = not compiled.get_state(config).values

    input_state = _fresh_turn_fields(question, max_iterations)
    if is_new_conversation:
        input_state["conversation_history"] = []

    for event in compiled.stream(input_state, config=config, stream_mode="custom"):
        yield event

    final_state = compiled.get_state(config).values
    graph_evidence = retrieval.build_graph_evidence(
        final_state["graph_relations"], final_state["community_drilldowns"]
    )
    yield events.done_event(thread_id, final_state["citations"], graph_evidence)
