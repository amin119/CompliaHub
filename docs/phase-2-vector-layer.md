# Phase 2 — Vector Layer

Status: **built, pending live verification**. All code is written, lint-clean,
and covered by tests (16/16 passing against the real docker stack, with
Voyage/Cohere/Grok mocked). What's *not* yet done: an actual end-to-end run
against real GDPR data with real API keys — see "What's left" below.

## Goal

A working baseline vector RAG system end-to-end — hybrid search + reranking +
LLM answer generation, no graph yet. This becomes the regression baseline
every later phase (graph, agentic) is measured against: if Phase 4/5 can't
beat this, they're not pulling their weight.

## Concepts learned

- **Embeddings & similarity search** — a dense vector encodes semantic
  meaning; cosine similarity between two chunks' vectors approximates how
  close their meaning is, independent of shared keywords.
- **Hybrid search rationale** — dense vectors miss exact keyword/ID matches
  (e.g. someone searching literally for "Article 6" or "A.8.1"); lexical
  search catches those. Combining both beats either alone.
- **Reciprocal Rank Fusion (RRF)** — merges two independently-ranked result
  lists (dense + lexical) into one ranking using only rank *position*, so a
  Qdrant cosine score and a Postgres `ts_rank_cd` score never need to be
  calibrated onto the same scale.
- **Cross-encoder reranking** — a second, more expensive pass that scores
  (query, chunk) pairs jointly catches relevance a bi-encoder's independent
  embeddings miss. Only run on the top-K fused candidates (~20-40), not the
  whole corpus — this is what makes it affordable.

## What was built

```
backend/
├── alembic/versions/0002_lexical_search.py   # tsvector generated column + GIN index
├── app/
│   ├── core/config.py                # + voyage/cohere/anthropic Settings fields
│   ├── services/
│   │   ├── embedding.py               # Voyage embed wrapper, batched, doc/query modes
│   │   ├── vector_store.py            # Qdrant collection ensure/upsert/search
│   │   ├── lexical_search.py          # Postgres ts_rank_cd full-text search (raw SQL)
│   │   ├── fusion.py                  # reciprocal_rank_fusion — pure function
│   │   ├── reranking.py               # Cohere rerank wrapper
│   │   └── answer_generation.py       # Claude answer generation with citation prompt
│   ├── tasks/ingestion.py             # + embed_chunks_task (3rd chain stage)
│   ├── schemas/query.py               # QueryRequest / Citation / QueryResponse
│   └── api/routes/query.py            # POST /query — the new end-user answer path
└── tests/
    ├── test_fusion.py                  # pure unit tests, no infra
    └── test_query_api.py               # integration test, mocks Voyage/Cohere/Anthropic
```

## Decisions made

- **Embedding: Voyage, model `voyage-law-2`.** API-based over local (no GPU
  needed, zero-setup), and `voyage-law-2` specifically over general-purpose
  `voyage-3` — it's tuned for legal/regulatory text, which is exactly this
  corpus (ISO standards, GDPR).
- **Reranker: Cohere Rerank (`rerank-v3.5`).** Same API-first rationale as
  the embedding choice, for consistency.
- **Answer generation: Grok (xAI), model `grok-4`.** Not an open decision in
  the original plan — added because Phase 2 needs *some* LLM to generate the
  final answer from reranked context. Originally built against Anthropic
  Claude, swapped to Grok because the user has free API access there and not
  on Anthropic. xAI's API is OpenAI-compatible, so this uses the `openai`
  SDK pointed at `grok_base_url` (`https://api.x.ai/v1`) rather than a
  dedicated xAI SDK — no other code needed to change since the whole call is
  isolated behind `answer_generation.generate_answer()`.
- **Lexical search: Postgres `tsvector`/`ts_rank_cd`**, exactly as planned —
  no new infra at this corpus size (`migration 0002`). Precision note: this
  is *not* literally BM25 (no document-length normalization) — the roadmap
  and this doc call it "BM25 (Postgres full-text)" loosely; it's the
  pragmatic Postgres equivalent, not the real BM25 formula.
- **Qdrant point IDs = `chunk.id` directly.** UUIDs are a native Qdrant point
  ID type, so no separate id-mapping table between Postgres and the vector
  store was needed.
- **Citations are the reranked context chunks, not parsed model output.**
  `generate_answer()` returns plain text; the `/query` route builds the
  `Citation` list directly from the chunks fed to the LLM rather than trying
  to determine exactly which ones the model actually leaned on. Precise
  per-claim citation attribution/faithfulness scoring is Phase 7
  (evaluation harness) territory, not this baseline.

## Gotchas worth remembering

- **Celery chain argument-count bugs bypass `_fail()` entirely.** The first
  version of `embed_chunks_task` only accepted `document_id`, but Celery's
  `chain()` always feeds the previous task's return value as a leading
  positional arg (`chunk_document_task` returns `None`) — so the real call
  was `embed_chunks_task(None, document_id)`, a `TypeError`. This error is
  raised by Celery's `apply_async()` argument-checking *before* the task
  body ever runs, so it never hits our own `try/except` — the document was
  left stuck in `"embedding"` forever instead of being marked `"failed"`.
  Caught by checking worker logs (`docker logs <worker>`), not by the API's
  own state. Fixed by giving every non-first chain stage a leading
  `_unused_result` parameter, matching the pattern `chunk_document_task`
  already used for `parsed_tree`.
- **`GENERATED ALWAYS AS (...) STORED` columns can't be mapped on the ORM
  model.** Postgres rejects any explicit value — even `NULL` — for such a
  column on INSERT. Mapping `text_search_vector` onto `Chunk` would have
  broken every existing chunk insert in `app/tasks/ingestion.py` the moment
  SQLAlchemy included it in an INSERT's column list. Fixed by querying it
  with raw SQL (`lexical_search.py`) instead of through the ORM — it only
  ever needs to be *read*.
- **Docker port collisions with unrelated projects on the same machine.**
  The root `.env`'s default ports (5432, 6379, 9000) collided with other
  running docker-compose projects on this host. Bumped to 5435/6381/9002 in
  both the root `.env` (docker-compose) and `backend/.env` (host-run FastAPI
  process) — the two must stay in sync since one configures the containers
  and the other configures how the host process reaches them.

## Verification

1. `uv run pytest` — 16/16 pass against the live docker stack (`test_fusion.py`
   needs no infra; `test_documents_api.py`/`test_query_api.py` mock
   Voyage/Cohere/Grok so CI never makes paid API calls, but do exercise real
   Postgres + Qdrant wiring).
2. `uv run alembic upgrade head` → `0002` applied, `chunks.text_search_vector`
   + its GIN index confirmed via `\d chunks`.
3. Real document, real questions (**not yet run** — needs real API keys):
   - GDPR (Regulation (EU) 2016/679) fetched from the official EUR-Lex text,
     restructured into a `.docx` with Chapter/Article headings the existing
     `parsing.py` regex already recognizes (`Article\s+\d+`) — verified via a
     direct `parse_document()` dry run: 11 chapters, 15 sections, 99
     articles, correct clause numbers, no parser changes needed.
   - `POST /documents` with the GDPR `.docx` → parse/chunk stages confirmed
     working against real legal text (not just the synthetic test fixture).
   - Embed stage confirmed *failing correctly* with a clear
     `AuthenticationError` and `document.status == "failed"` when
     `VOYAGE_API_KEY` is unset — proves the stage-3 error path works, but
     the happy path (chunks actually reaching Qdrant) is unverified.
   - **What's left**: real `VOYAGE_API_KEY`, `COHERE_API_KEY`, and
     `GROK_API_KEY` in `backend/.env` (placeholders already scaffolded there
     and in `.env.example`), then re-run the GDPR upload to `ready` and
     `POST /query` with a real question (e.g. "What are the conditions for
     lawful processing of personal data under Article 6?") to confirm the
     answer cites the correct Article end-to-end.

ISO 42001/27001 are not part of this verification — they're paid copyrighted
standards, out of scope for automated fetching; added later, through this
same unmodified pipeline, once purchased.

## What Phase 3 needs from here

Phase 3 (entity/relation extraction into Neo4j) reads from the same `chunks`
table Phase 1 produced — Phase 2's additions (Qdrant vectors, `/query`) are
orthogonal to it, not a dependency. The one shared piece worth reusing:
`answer_generation.py`'s pattern of numbering context with clause/article
labels for citation is a template Phase 4 (graph retrieval) will likely want
too, once graph results get merged into the same answer-generation context.
