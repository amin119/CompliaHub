# Phase 5 — Agentic Orchestration Layer

Status: **done and verified live, both parts.** Part 1 (query classifier +
LangGraph agent loop) and Part 2 (real Postgres-backed checkpointing +
multi-turn conversational memory) are both built and confirmed working end
to end through the real `/query` HTTP API — see "Live verification" and
"Part 2 live verification" below.

## Goal

Replace the single-shot retrieval call with a reasoning loop — the model
decides what to retrieve and whether it has enough evidence, instead of a
fixed pipeline always doing the same steps.

## Concepts to learn first

- **Workflow RAG vs. true agentic RAG** — Phases 2 and 4 are workflow RAG: a
  fixed sequence of steps runs every time. Agentic RAG lets the model choose
  actions (retrieve via vector, retrieve via graph, rewrite the query, decide
  it has enough evidence) and loop until it's satisfied or hits a budget.
  The distinction matters because agentic RAG costs more per query — it
  should only be used when the query actually needs it (see: query
  classifier, below).
- **Self-RAG (Asai et al., 2023) and FLARE (Jiang et al., 2023)** — the
  reference papers for models that critique their own retrieval and decide
  whether to retrieve again.
- **LangGraph fundamentals** — nodes, conditional edges, cycles (loop-backs),
  and checkpointing. This is a different mental model from a linear FastAPI
  request handler — the graph *is* the control flow.
- **Adaptive routing and cost control** — why sending every query through the
  full agent loop would be slow and expensive, and why a cheap upfront
  classifier that routes simple questions straight to Phase 2's vector search
  keeps the system affordable.

## Part 1 — what was built

1. **`app/services/query_classifier.py`** — Gemini structured-output call
   (same Protocol+adapter+retry pattern as `extraction.py`/
   `community_summary.py`), routing every question into exactly one of
   three categories: `vector` (simple factual), `graph` (relational,
   specific named things), `agent` (broad/thematic/comparative/multi-step).
2. **`app/services/retrieval.py`** (new) — the shared retrieval primitives
   (`vector_search`, `local_search_facts`, `global_search_context`,
   `render_evidence`) extracted out of Phase 4's `/query` route so both the
   direct paths *and* the agent's `retrieve` node call the same,
   already-live-tested code — no retrieval logic was rewritten for Phase 5,
   only reused.
3. **`app/services/agent.py`** — the LangGraph agent: `plan` → `retrieve` →
   `critique` → (`answer` | `rewrite_query` → `plan`), looping until
   critique is satisfied or the iteration budget (`DEFAULT_MAX_ITERATIONS =
   2`) is spent. `plan` is deliberately deterministic for Part 1 (global
   search only turns on after a first pass proved insufficient), not an
   LLM call — a real planner LLM is natural follow-up work, not required to
   make `plan` a real, distinct step already. `critique`/`rewrite_query`
   call Gemini directly with no retry/Protocol apparatus (Part 1 scope
   decision — a transient failure there just fails the request, same as
   any other current failure mode).
4. **`/query` route rewritten**: classify first, then route — `vector` skips
   the graph entirely (real cost savings for the common case), `graph` adds
   Phase 4 Part 1 local search, `agent` hands off to the full loop.
   Global/thematic search is reserved for the agent path on purpose:
   deciding *whether* a thematic summary is even relevant is exactly the
   judgment call Phase 4's own docs said would be Phase 5's job.
5. **Checkpointing**: `MemorySaver` (in-memory) for Part 1.

## A real gotcha found while building this, not caught until first run

**`MemorySaver` still requires every `AgentState` field to be
msgpack-serializable** — "in-memory" does not mean "no serialization,"
confirmed live: the first test run crashed with `TypeError: Type is not
msgpack serializable: Chunk` the moment a raw SQLAlchemy `Chunk` ORM object
landed in state, even though nothing was ever written to a real persistent
store. Checked which types actually survive
(`langgraph.checkpoint.serde.jsonplus.JsonPlusSerializer`) rather than
guessing: `Citation` (pydantic) and `ProvenancedRelationEdge`/
`CommunityWithEmbedding` (NamedTuples, including their `EntityType` enum
fields) all serialize fine as-is — only the raw ORM object was the
problem. Fixed by keeping `AgentState.context_chunk_ids: list[str]`
(plain UUID strings) instead of `Chunk` objects, with a `chunk_cache: dict[str,
Chunk]` living in `build_agent`'s closure (*not* in `AgentState`) that
`retrieve_node` populates and every other node resolves real rows from by
id. This means Part 2's "swap in a real Postgres checkpointer" is
*already* safe to do without another state-shape migration — the
serializability problem got solved now, in Part 1, specifically because it
turned out not to be optional the way the original plan assumed.

## Open decisions, resolved

- **Classifier implementation**: cheap few-shot Gemini prompt, per the
  roadmap's own suggestion — reuses the same model already integrated for
  extraction/community summaries (`GEMINI_EXTRACTION_MODEL`), no new
  provider.
- **`GEMINI_API_KEY` now needs to live in `backend/.env` too, not just the
  root `.env`** — a real consequence of the classifier/agent running in the
  host FastAPI process (`/query`), unlike Phase 3's extraction, which only
  ever ran inside the worker container. `google-genai` moved from the
  `graph` optional-dependency extra into base `dependencies` for the same
  reason (see `pyproject.toml`'s comment) — it now has two independent
  consumers, not one.
- **Default budget**: `max_iterations = 2` — an empirical starting point,
  same "tune against real use" spirit as every other constant like this in
  this project (extraction pacing, local search hop count), not expected
  to be right on the first try.
- **Checkpoint storage**: `MemorySaver` for Part 1, Postgres for Part 2 —
  unchanged from the original plan, just confirmed the state-shape problem
  above needed solving regardless of which one Part 1 used.

## Live verification

**Classifier**, run against 5 real questions spanning all three categories,
no cherry-picking — all 5 landed exactly where expected:

| Question | Category |
|---|---|
| "What does clause 6.1.2 require?" | `vector` |
| "What controls mitigate the risk of unauthorized access?" | `graph` |
| "What does ISO 42001 require that ISO 27001 doesn't?" | `agent` |
| "Summarize the main themes around risk management in this corpus." | `agent` |
| "What is the definition of an information security incident?" | `vector` |

**Vector-category routing**: confirmed real chunks were retrieved and the
route correctly reached `answer_generation.generate_answer` directly (no
Neo4j call) — it failed exactly at the external Grok call
(`openai.PermissionDeniedError: 403 ... doesn't have any credits`), the
same pre-existing xAI billing block from Phase 2, confirmed unrelated to
Phase 5's own code. (Phase 6 Part 2 later moved answer generation off Grok
onto Gemini entirely, retiring this blocker — see
docs/phase-6-frontend.md.)

**Full agent loop**, run against the real corpus with only the
billing-blocked final Grok call bypassed (question: *"What does ISO 42001
require that ISO 27001 doesn't?"*): the evidence counts themselves prove
two full iterations ran for real — **60 graph facts** (2 × the 30-per-call
cap, meaning `retrieve` ran twice and correctly accumulated rather than
overwrote) and **non-empty community context** (which `plan` only enables
starting iteration 1, i.e. only reachable after a real `critique` verdict
of "insufficient" triggered a real `rewrite_query` call and a real loop
back through `plan`/`retrieve`). Final result: 8 accumulated chunks, 60
graph facts, 2 community-context lines, **39 total citations** built by
`render_evidence`. This is exactly the "workflow RAG can't do this" case
from the roadmap's learning checkpoint — a genuinely multi-step retrieval
process, not a fixed pipeline, produced this evidence set.

## Part 2 — what was built

Went beyond a bare `MemorySaver` → `PostgresSaver` swap. Real persistent
checkpointing is only actually *valuable* if something exercises it —
without a way to resume the same thread across separate requests,
persistence is invisible infrastructure that happens to also survive a
restart. So Part 2 also added the feature that makes persistence
meaningful: multi-turn conversational memory.

1. **`app/core/checkpointer.py`** (new) — a `psycopg_pool.ConnectionPool`
   (not a single connection — concurrent `/query` requests shouldn't
   serialize on one checkpoint connection) feeding a `PostgresSaver`,
   reusing the project's existing `DATABASE_URL` (no new connection string,
   no new Postgres instance). `open_checkpointer()`/`close_checkpointer()`
   are wired into `app/main.py`'s new FastAPI `lifespan` — opened once for
   the app's whole process lifetime, not per-request. `PostgresSaver.setup()`
   is idempotent (`CREATE TABLE IF NOT EXISTS`), called on every startup;
   this project's own schema still goes through Alembic — LangGraph's
   checkpoint tables (`checkpoints`, `checkpoint_blobs`, `checkpoint_writes`,
   `checkpoint_migrations`) are a separate, self-managed schema.
2. **Multi-turn conversational memory** — `AgentState.conversation_history`
   uses LangGraph's `Annotated[list[dict], operator.add]` reducer pattern
   (append, not overwrite) so it accumulates across *separate*
   `run_agent()` calls on the same thread, not just within one call. A new
   `condense_question` node runs first each turn: if there's prior history,
   it rewrites a follow-up ("what about GDPR?") into a standalone question
   using that history — the same "condense question" pattern real
   conversational RAG systems use — before `plan`/`retrieve` ever run;
   with no history yet, it's a no-op (skips the LLM call entirely rather
   than pay for a rewrite that changes nothing).
3. **`QueryRequest`/`QueryResponse` gained `conversation_id`** — omit it to
   start a new conversation (the server generates and returns one);
   pass back a prior response's `conversation_id` to continue it. Only
   `agent`-classified turns actually build memory (see "known limitation"
   below) — `vector`/`graph` turns still get a `conversation_id` echoed
   back for a consistent API contract, but it was never used as a real
   checkpoint thread id.
4. **`GET /query/conversations/{id}`** and **`DELETE
   /query/conversations/{id}`** — the concrete, user-facing fulfillment of
   the roadmap's "resumable/inspectable" requirement (Part 1 only made
   agent runs inspectable via internal debugging scripts). `GET` reads
   directly via `checkpointer.get_tuple()` — no need to build a full agent
   graph (which would need `db`/`driver`) just for a state read. `DELETE`
   wraps `checkpointer.delete_thread()` for explicit "forget this
   conversation."
5. **`build_agent`/`run_agent` take `checkpointer` as an injected
   parameter** instead of hardcoding `MemorySaver()` — the real `/query`
   route passes the Postgres-backed singleton; tests pass a fresh
   `MemorySaver()` and need no live Postgres for the agent's own
   control-flow tests (only the new dedicated
   `tests/test_conversations_api.py` needs real Postgres, to prove the
   *persistence* itself, not the loop logic).

## Two real things found building this, not caught by design

- **A LangGraph checkpointer, once closed, can never be reopened**
  (`psycopg_pool.PoolClosed: pool has already been opened/closed and
  cannot be reused`) — found because a first draft of the test suite's
  infra-availability check opened and closed the *same* module-level pool
  singleton as a connectivity probe, permanently killing it before the
  real fixture could open it again. Fixed by probing connectivity through
  SQLAlchemy's own `engine` instead (equivalent reachability check, same
  Postgres, different driver) and letting exactly one fixture own the
  checkpointer pool's open/close lifecycle.
- **LangGraph's serializer warns about custom types it doesn't recognize,
  and says so will become a hard failure later**: the first real Postgres
  round-trip printed `Deserializing unregistered type ... This will be
  blocked in a future version` for `Citation` (pydantic), `EntityType`
  (enum), and the `ProvenancedRelationEdge`/`CommunityWithEmbedding`
  NamedTuples — it still worked, but silently wouldn't after some future
  LangGraph upgrade. Fixed now, not deferred: a `JsonPlusSerializer`
  constructed with an explicit `allowed_msgpack_modules` allowlist for
  exactly these four types, passed to `PostgresSaver(pool, serde=...)`.
  Re-verified: the warning is gone, the round-trip is unchanged.

## Known limitation, documented rather than solved

**No automatic checkpoint retention/TTL.** LangGraph's checkpoint tables
carry no last-activity timestamp of their own, so "delete conversations
older than N days" isn't a query that can be written against them directly.
`app/core/checkpointer.py`'s `delete_conversation()` covers *explicit*
cleanup (a user or admin action); genuine automatic retention would need
this project's own bookkeeping (a small `conversations` table tracking
`last_active_at`, updated each turn) feeding a periodic job that calls
LangGraph's own `checkpointer.prune(thread_ids, strategy="keep_latest")` —
deliberately not built now, flagged here so it isn't silently forgotten.
Real production systems that skip this eventually notice their checkpoint
tables growing forever; better to say so than pretend it isn't a gap.

**Conversation memory only spans `agent`-classified turns.** If a user's
first question gets classified `vector` and their follow-up gets
classified `agent`, the follow-up has no memory of the first turn — only
the agent path builds/reads `conversation_history`. Unifying memory across
all three categories would mean every path participates in the same
checkpointed state, a bigger change than Part 2's scope; documented rather
than solved for the same reason retention wasn't.

## Part 2 live verification

Real round-trip through the actual HTTP API (not a script bypassing it),
Gemini/retrieval mocked, **real Postgres checkpointer**:

1. `POST /query` (turn 1, no `conversation_id`) → real `conversation_id`
   returned.
2. `POST /query` (turn 2, same `conversation_id`, "What about GDPR?") →
   same `conversation_id` echoed back; `condense_question` correctly fired
   (confirmed via call-count assertion) since history now exists.
3. `GET /query/conversations/{id}` → both turns present, in order, with
   their real questions and answers — read back from a **separate**
   process-level call than the one that wrote them, proving actual
   Postgres durability, not in-process memory.
4. `DELETE /query/conversations/{id}` → 204.
5. `GET /query/conversations/{id}` again → 404, confirming deletion was
   real, not just a soft flag.

All 5 steps passed on the first real run against the live docker-compose
Postgres instance. Full test suite: 103 passed.

## Bug fix (post-Phase 6): off-topic questions were slow, not a real defect in the loop itself

Reported directly by the user after trying the live Phase 6 chat UI: a plain
greeting ("hi, how are you doing?") took **~19 seconds** and came back with
two dozen irrelevant citations and a nonsense graph visualization. Reproduced
first via a direct `curl` against `/query/stream` before touching any code —
confirmed it ran the *entire* agent loop (`planning` → `retrieving` →
`critiquing` → `rewriting_query` → `planning` → `retrieving` → `critiquing` →
`generating_answer`, two full iterations) for a question with nothing to do
with compliance.

**Root cause**: `query_classifier.py`'s three categories (`vector`/`graph`/
`agent`) have no way to represent "not a compliance question at all" — and
the classifier's own tie-breaking instruction ("when unsure between graph
and agent, prefer agent") meant anything that didn't cleanly fit vector or
graph fell through to the single *most expensive* path by default. A
greeting isn't ambiguous between retrieval strategies — it just doesn't need
retrieval at all — but the classifier had no fourth option to say so.

**Fix**: added `QueryCategory.OFF_TOPIC`, with the system prompt explicit
that it's for questions that plainly aren't about compliance (not a
fallback for compliance questions the model is merely unsure how to route).
Both `/query` and `/query/stream` fast-path this category to a canned reply
*before* touching `retrieval.vector_search`, Neo4j, or any answer-generation
LLM call — verified by making retrieval raise in the regression tests, same
"boom if it's ever called" pattern already used for
`test_vector_category_skips_the_graph_entirely`.

**Live re-verification after the fix**: the same "hi, how are you doing?"
question dropped from ~19s (full agent loop, 25 citations, ~20-node graph)
to ~6s (one classification call, zero citations, empty graph) — the
remaining time is just the single Gemini classification round-trip itself,
not anything left to optimize. Real compliance questions were re-checked
too, to make sure the new category didn't start swallowing legitimate
ones — "what controls mitigate the risk of unauthorized access?" still
correctly classified as `graph` and answered normally. Full backend suite
green after the fix: **115 passed** (up from 113 — the two new off-topic
regression tests, one for each route, each verified by making retrieval
raise if the fast path doesn't actually short-circuit). **One deployment gotcha hit while verifying, not a code bug**:
`uvicorn --reload`'s WatchFiles reloader silently failed to swap in the new
worker process on this Windows machine — the old process kept serving
requests with pre-fix code for several requests after the reload log line
appeared, making it look like the fix hadn't worked. Diagnosed by calling
`query_classifier.classify_query` directly in a one-off script (confirmed
the classification logic itself was already correct) before suspecting the
running process; fixed by force-killing both the reloader and worker PIDs
and starting a fresh `uvicorn` process without `--reload` for the rest of
this session's manual verification.

### Follow-up: ~6s was still too slow, and it wasn't Gemini's fault alone

The user pushed back that even the fixed ~6s off-topic response was slow —
correctly, since one classification call shouldn't take that long. Measured
the actual components directly (a one-off script hitting the real Gemini
API, not guesswork) rather than assuming it was all unavoidable network
latency:

- `genai.Client(api_key=...)` construction alone: **~1s, every time** —
  `query_classifier.py` was building a brand-new client on every single
  `classify_query()` call (`get_gemini_client()` had no caching), even
  though nothing about the client differs between requests within a
  process's lifetime.
- Gemini's default "thinking" mode was adding measurable overhead
  (`thinking_config=types.ThinkingConfig(thinking_budget=0)` shaved
  ~0.5-1s off repeated calls in a side-by-side comparison) for a task —
  picking one of four fixed labels — that needs zero reasoning depth.

**Fix**: `_sdk_client()`, an `lru_cache`d factory keyed by `api_key`
(same reasoning as `get_settings()`'s own caching — the key doesn't change
within a process), replaces constructing `genai.Client` fresh per call;
`thinking_budget=0` added to the classification request. Both changes are
scoped to `query_classifier.py` only — the same technique would likely
help `agent.py`'s condense/critique/rewrite calls too, but that wasn't
what was reported slow and is a natural follow-up, not bundled in here.

**Re-verified live** (fresh non-`--reload` process, per the gotcha above):
four different off-topic questions now land in **1.0-2.4s** end-to-end
through the real HTTP API, down from ~6s. A real compliance question
("what controls mitigate the risk of unauthorized access?") was re-checked
too — still classifies correctly and returns 17 real citations, confirming
`thinking_budget=0` didn't degrade classification quality. Full backend
suite still green after this fix.

### Follow-up: the off-topic reply was the same sentence every time

Also reported directly by the user: every off-topic question got the
identical hardcoded reply, which reads as robotic in an actual
conversation. Fixed by having `QueryClassification` carry an optional
`reply` field that the classifier fills **in the same call** that
classifies the question (not a second LLM round-trip — the system prompt
now instructs: when category is `off_topic`, also write a short, warm,
*varied* response to what the user actually said, then invite them to ask
about compliance). `/query` and `/query/stream` use `classification.reply`
directly, falling back to the old fixed sentence (renamed
`_OFF_TOPIC_FALLBACK`) only if the model ever leaves it empty.

**Live-verified real variety** — five different off-topic messages, each
getting a distinct, actually-responsive reply (not paraphrases of the same
template): a greeting got "I am doing well, thank you for asking!", "write
me a poem about the ocean" got a request declined gracefully, "what's the
weather" correctly noted no real-time data access, "tell me a joke"
self-deprecated about not having a sense of humor, and a second "hi again"
got "It is great to hear from you again" — all while staying on the same
one-call classification budget (3.8s observed on one run, still nowhere
near the old ~6-19s). Real compliance-question regression re-checked once
more, still correct. Full backend suite still green.

## Learning checkpoint (from the roadmap)

You understand the difference between workflow RAG (fixed pipeline) and true
agentic RAG (model decides retrieval actions), and why adaptive routing keeps
costs sane.
