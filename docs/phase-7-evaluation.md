# Phase 7 — Evaluation Harness

Status: **done and verified live.** Everything through Phase 6 was verified
live but only ever judged by eye ("does this answer look right"); this phase
adds real, repeatable quality measurement on top of the same `/query`
pipeline.

## Goal

Stop trusting gut feel about answer quality — measure it quantitatively via
RAGAS-style metrics (faithfulness, answer relevance, context precision,
context recall) over a real question set, tracking routing path/latency/cost
per question, with the capability to compare two runs over time.

## What was built

**The user resolved the roadmap's own explicitly-flagged open decision, via
`AskUserQuestion`** (same pattern as every scanner phase): a **custom
Gemini-based LLM-judge module**, not the `ragas` pip package — reusing this
project's existing Protocol+adapter+retry pattern (`query_classifier.py`'s
shape), no new dependency tree, and structured so a later swap to real
`ragas` would only touch one file.

**Research going in found the roadmap doc's own planned components didn't
quite match reality**: `/query`'s routing category, latency, and (for agent
turns) iteration count were all computed internally then silently discarded
before `QueryResponse` was built; `Citation` carried no excerpt text, so real
retrieved context wasn't recoverable from the HTTP response at all; and there
was zero token/cost tracking anywhere in the codebase. This phase had to
build real plumbing for all of that, not just bolt scoring onto an existing
signal.

**1. Shared query-orchestration extraction — `app/services/query_orchestration.py`.**
`query.py`'s `query()` route body (classify → off_topic/agent/vector/graph
branches) was extracted into `run_query()`, so the HTTP route and the eval
harness call the exact same real pipeline — never a second, subtly-different
code path built just for scoring (same reasoning Phase 5 used extracting
`retrieval.py`'s primitives out of Phase 4's inline route code). `run_query`
wraps the existing logic with latency timing (`time.perf_counter()`) and
token-usage tracking, returning an `OrchestrationResult(response,
context_texts, token_usage)` — `context_texts`/`token_usage` are eval-only
internals, deliberately never added to the public schema.
`_context_texts_for_citations` reconstructs retrieved context text from a
response's own citations (works uniformly across vector/graph/agent
categories without needing `agent.run_agent` to expose its internal chunk
cache) — a disclosed simplification: it treats vector-retrieved chunk text as
*the* context every metric scores against, not also the separate
`graph_facts`/`community_context` strings.

`QueryResponse` gained three additive fields — `category`, `latency_ms`,
`iteration_count` — a genuine, honest product improvement now that this data
isn't silently thrown away, mirroring Phase 6's earlier `Citation.document_id`
addition. `agent.run_agent` gained one line populating `iteration_count` from
`AgentState`'s already-tracked `iteration` field. `/query/stream` was
deliberately left untouched — forcing the streaming path through a
single-return-value function would mean buffering every token before
yielding, defeating streaming's purpose, and the eval harness never needs
token-by-token output.

**2. Custom LLM-judge metrics — `app/services/eval_metrics.py`.** Same
Protocol + `@lru_cache`d client + retry-with-backoff shape as
`query_classifier.py`. Each metric is a real, RAGAS-equivalent methodology,
not a hand-waved score:
- **Faithfulness**: decomposes the generated answer into atomic claims,
  judges each against retrieved context in the same call. Score = supported
  claims / total claims.
- **Context recall**: the same claim-decomposition-and-judge mechanism
  applied to the *ground-truth* answer instead of the model's own answer — a
  low score means retrieval, not the answer model, is where quality is being
  lost.
- **Answer relevance**: generates 3 hypothetical questions the answer alone
  would address (without showing the real question, avoiding leakage), embeds
  them via the existing `embedding.embed_texts` (reused, not reimplemented),
  averages cosine similarity against the real question's embedding.
- **Context precision**: judges every retrieved chunk (rank order) as
  relevant/not, then computes RAGAS's actual weighted-average-precision
  formula (`sum(precision@k * relevant_k) / total_relevant`).

Every `MetricResult` carries a `detail` dict with the judge's raw
claims/verdicts, persisted as JSONB — never trust a bare float, same
discipline `finding_validation.py`'s `rationale` field established.

**3. Ground truth — new `eval_questions` table**, not a JSON fixture: needs
the same mutable, auditable, endpoint-editable row `FindingReview` established
for the scanner's human-review discipline. Rows carry `use_case_category`
(the roadmap's 5 categories: cross-standard mapping, gap analysis, multi-hop
traversal, audit evidence lookup, impact analysis), `ground_truth_answer`,
`ground_truth_citations` (JSONB), `source` (`llm_drafted`/`human_authored`),
and `human_reviewed` (defaults `False` — unverified until a person confirms
it via `PATCH /eval/questions/{id}`, mirroring the scanner's `FindingReview`
discipline exactly). New one-off script, `scripts/generate_eval_questions.py`
— samples real chunks from the 3 already-ingested standards and asks Gemini
to draft realistic question/answer/citation triples per category, grounded
in the given real excerpts (not free-form).

**4. Storage — migration `0010_evaluation_harness.py`**: `eval_questions`,
`eval_runs` (denormalized rollup columns — `avg_faithfulness`,
`avg_answer_relevance`, `avg_context_precision`, `avg_context_recall`,
`avg_latency_ms`, `total_estimated_cost_usd` — computed once when a run
finishes, so comparing runs never re-aggregates raw results), and
`eval_results` (one row per question per run, `error_message` nullable so one
bad question never aborts the whole run).

**5. Cost tracking — `app/services/token_tracking.py`**: a `contextvars`-based
accumulator, opt-in (`record()` no-ops when nothing is tracking). Instrumented
at 4 Gemini call sites (`query_classifier`, `answer_generation`'s
completion/streaming paths, `agent`'s condense/critique/rewrite calls) —
ingestion/scanner call sites deliberately not instrumented, since this phase
only prices the `/query` path. `app/core/pricing.py` holds a small, disclosed
best-effort per-1K-token cost table.

**6. Triggering and inspecting runs — `app/api/routes/evaluation.py` +
`app/tasks/evaluation.py`**: `POST /eval/runs` (async via Celery — the only
new task this phase adds, `"eval.run_evaluation"` on its own `"eval"` queue,
colocated on `worker-vector` since everything it needs is already in base
dependencies), `GET /eval/runs/{id}`, `GET /eval/runs/{id}/results`,
`GET /eval/runs/compare?a=&b=` (per-metric deltas plus questions whose score
dropped by more than a 0.15 threshold between two runs — a comparison
capability, not a pass/fail gate). `GET`/`PATCH /eval/questions` for the
human-review workflow. **Deliberately no frontend UI** — a dev-facing quality
tool, not a user-facing product surface; API responses are enough at this
project's scale, matching the established bias against adding new subsystems.

## Real bugs found via live verification, not caught by unit tests alone

1. **A FastAPI route-ordering bug**: `GET /runs/{run_id}` (parameterized) was
   registered before `GET /runs/compare` (static), so any request to
   `/runs/compare` matched the parameterized route first, tried to parse
   `"compare"` as a UUID, and 422'd instead of ever reaching the real
   handler. Fixed by moving the static route before the parameterized one —
   exactly the kind of thing only a real HTTP call surfaces, not a unit test
   calling the handler function directly.
2. **Gemini's structured-output schema rejects a bare `dict` field**
   (`additionalProperties` isn't supported in Developer API/non-Enterprise
   mode) — `scripts/generate_eval_questions.py`'s `DraftedQuestion
   .ground_truth_citations: list[dict]` failed on its very first real call.
   Fixed with a named `DraftedCitation` model (`document_filename`,
   `clause_number`) instead of a bare dict — the same lesson every other
   Gemini structured-output schema in this codebase already followed
   without ever hitting this specific failure mode.
3. **This Windows host's known TLS-interception issue** (documented since
   Phase 2 — outbound HTTPS from Python running natively here fails cert
   verification, fixed in `app/main.py` via `truststore.inject_into_ssl()`)
   hit two NEW places this phase touches that `main.py`'s fix never reaches:
   the standalone `generate_eval_questions.py` script, and a host-run Celery
   worker (this project's own established fallback for when a Docker
   rebuild is blocked, per Phase 1's precedent). Fixed by adding the same
   `truststore.inject_into_ssl()` call to both the script and
   `app/tasks/celery_app.py` (harmless no-op on the normal Linux container
   deployment path).
4. **A `PoolClosed` bug in the checkpointer's real, already-documented
   "can never reopen once closed" constraint** (`psycopg_pool.ConnectionPool`,
   first hit in Phase 5 Part 2): the eval task's first draft called
   `open_checkpointer()` unconditionally at the top of every run, regardless
   of whether any question in the batch was actually agent-classified. In
   the full test suite, `test_conversations_api.py`'s own fixture had
   already opened *and closed* the shared global pool earlier
   (alphabetically first) — so the unconditional call crashed even though
   most eval runs never touch the agent path at all. Fixed properly at the
   source: `app/core/checkpointer.py` gained an idempotent `ensure_open()`
   (a one-way "have I ever opened this" latch, distinct from "is it
   currently usable"), called lazily only inside `query_orchestration.py`'s
   AGENT branch — a no-op in the host FastAPI process (already opened via
   `main.py`'s lifespan) and correct for a worker process that has none of
   its own. A related test fragility surfaced by the same mechanism: a test
   question phrased broadly enough ("What is ISO 27001?") occasionally
   classified as `agent` by the real classifier, hitting the
   now-permanently-closed pool with no per-question error isolation (unlike
   the Celery task, which catches this per-question) — fixed by rephrasing
   the test to the exact single-clause factual shape
   `query_classifier`'s own system prompt gives as its `vector` example,
   confirmed stable across repeated runs.

## Verification

- **27 unit tests** (`test_eval_metrics.py`, `test_eval_aggregation.py`,
  `test_token_tracking.py`): exact hand-computed scores for all 4 metrics
  (including context precision's weighted-average-precision formula and
  answer relevance's cosine-averaging against fake fixed vectors), the
  retry helper's rate-limit/validation-error backoff, run-aggregation
  (average-excluding-errored-rows, cost-always-counted) and run-comparison
  (signed deltas, regression-threshold flagging) against in-memory fakes,
  and `token_tracking`'s contextvar isolation across sequential fake
  requests.
- **6 live-infra integration tests** (`test_evaluation_api.py`) —
  **deliberately does not reuse the `_mock_external_apis` convention** every
  other test file uses: faking the answer/embedding/judge LLM would make
  these tests assert only "the harness calls a mock and gets a mock number
  back," defeating the feature's purpose. Adds a parallel
  `_real_llm_available()` skip condition (checks real API keys are
  configured) alongside the usual infra check. Question/answer review CRUD,
  a real 2-question eval run with scores confirmed in `[0, 1]`, run
  comparison returning all 5 expected metric deltas, and a direct assertion
  that `token_tracking` captures nonzero token counts on a real Gemini call.
- Lint (`ruff check`) clean. **Full backend suite: 511 passed, 0 failed, 0
  skipped** (up from 478 at the end of the scanner's Phase 9 — 33 new tests:
  27 unit + 6 live-infra), confirmed via a clean run (1129s, ~18:49).
- **Live end-to-end** via a real, non-eager dispatch: `worker-vector`'s
  Docker container was down due to a pre-existing, documented network/TLS
  interception issue unrelated to this work (same class of issue hit in
  Phase 1/Phase 4's own history), so verification used this project's
  established fallback — a Celery worker run directly on the host venv,
  alongside a fresh non-`--reload` uvicorn process. A real `POST /eval/runs`
  against 2 real, LLM-drafted-and-corpus-grounded questions (from the 40
  drafted by `generate_eval_questions.py`) dispatched genuinely
  asynchronously (202, `status: "running"`), and a real completed run came
  back with real scores: `faithfulness=1.0`, `answer_relevance≈0.79`,
  `context_precision=1.0`, `context_recall=1.0` for one question, with
  readable claim-level judge reasoning in `metric_detail` confirming the
  scores weren't nonsense (not just trusting the floats). A second question
  hit a transient `getaddrinfo` DNS error — correctly isolated to just that
  one row's `error_message` without crashing the run, confirming the
  per-question error-isolation design works in practice, not just in
  tests — and succeeded cleanly on a retry.
- Frontend: none — no UI in this phase's scope, by design.

## Explicitly out of scope

Langfuse (Postgres tables suffice, matches the roadmap's own tech-stack
table which lists Langfuse under Phase 8, not 7). Any frontend UI — argued
against above. Sharding/observability (Phase 8, which depends on this phase
existing). CI-wired regression gating — `/eval/runs/compare` is a manual
comparison capability only. The `ragas` package — the user's resolved
decision; `eval_metrics.py` is structured so a later swap only touches that
one file. Adding `category`/`latency_ms` to `/query/stream`'s `done` event —
a disclosed, deferred small follow-up. Making the ground-truth generation
script idempotent/repeatable — a one-off authoring aid, not a normal
operation. Full human review of all 40 drafted `eval_questions` rows — they
were drafted and spot-checked as genuinely coherent and corpus-grounded, but
marking them `human_reviewed=True` at scale is left as follow-up work for the
user, not automated away.

## Learning checkpoint (from the roadmap)

You can quantitatively say "this change improved retrieval quality by X%"
instead of guessing — and, concretely from this phase's own live
verification, you've seen a real answer's claims individually checked
against real retrieved context rather than trusting a single aggregate score.

**Only Phase 8 (Scaling & Hardening) remains of the original platform
roadmap.**
