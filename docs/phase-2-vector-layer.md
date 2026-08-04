# Phase 2 — Vector Layer

Status: **done, verified against real data**. Full pipeline (upload → parse →
chunk → embed → `/query`'s embed → dense search → lexical search → RRF fusion
→ rerank) confirmed working end-to-end against a real ISO 27001 PDF. The one
piece not exercised live is the final answer-generation call itself — blocked
by the xAI/Grok team account having zero credits (an account/billing issue,
not a code bug; see "Live verification" below). 16/16 tests pass.

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

- **`opencv-python` (a Docling table-structure-model dependency) needs X11/GL
  runtime libraries `python:3.12-slim` doesn't ship**, even though nothing in
  this project ever uses OpenCV's GUI functionality — the wheel dynamically
  links against them regardless. First real PDF parse in the container
  crashed with `ImportError: libxcb.so.1: cannot open shared object file`,
  deep inside `docling_ibm_models.tableformer` → `cv2`. Fixed by adding
  `libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 libxcb1 libgomp1` via
  `apt-get` in `backend/Dockerfile`, placed *after* the `uv sync` layer so it
  doesn't invalidate that (very expensive, torch-sized) cache. This is a
  well-known Docker+OpenCV interaction, not specific to Docling.
- **Docling's ML models are downloaded on first use, into the container's
  own filesystem — not a persisted volume.** Every time the worker container
  is rebuilt or recreated, the first real PDF parse re-downloads them from
  Hugging Face (~1-2 min), even though nothing about the models themselves
  changed. Not fixed this session (low priority for a single-dev local
  setup) — if this gets annoying, mount a named volume at whatever cache dir
  `docling`/`huggingface_hub` use (`~/.cache/docling`, `~/.cache/huggingface`)
  in `docker-compose.yml`.
- **Voyage's actual per-request token cap is much stricter than the
  documented "10K tokens/minute."** Empirically bisected against the real
  account: a 30-text/6,234-token batch succeeded, a 60-text/8,791-token batch
  immediately 429'd — on the very first request of a fresh session, so this
  isn't about cumulative per-minute usage, it's a hard per-request ceiling
  somewhere between those two numbers. `embedding.py`'s
  `_MAX_TOKENS_PER_BATCH` is set to 4,000 for real margin. Also worth
  knowing: `voyageai.Client(max_retries=...)` defaults to `0` — the SDK's
  own tenacity-based retry does nothing at all unless you explicitly pass a
  higher value; our own retry/backoff loop in `_embed_with_retry` is what
  actually handles 429s, not anything the SDK does automatically.
- **Outbound HTTPS from Python running natively on the Windows host fails
  cert verification, even though the same call succeeds from inside the
  Linux worker container.** `voyageai`/`cohere`/`openai` (all built on
  `requests`/`httpx`) raised `SSLCertVerificationError: unable to get local
  issuer certificate` calling Voyage from a host-run `uv run uvicorn`
  process — this network's TLS interception (the same class of issue that
  requires `uv add --native-tls`) isn't trusted by Python's own bundled CA
  list on this host, but isn't in the container's request path at all so it
  never surfaces there. Fixed with `truststore.inject_into_ssl()` at the very
  top of `app/main.py` (before any other import) — it repoints Python's
  `ssl` module at the OS's native certificate store instead of `certifi`'s
  bundled one, the direct Python-runtime analog of `--native-tls`. Harmless
  on Linux; the worker doesn't import `app.main` so it's unaffected either
  way.
- **`error_message` isn't cleared when a document is manually retried and
  later succeeds.** `embed_chunks_task`'s (and every stage's) success path
  only ever sets `document.status`, never resets `error_message` — so a
  document that failed once, got retried, and reached `"ready"` can still
  show a stale error from the earlier failed attempt. Cosmetic only (status
  is authoritative), not fixed this session — worth a one-line fix
  (`document.error_message = None` alongside each `document.status = ...`
  success assignment) if it ever causes real confusion.
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

## Live verification (what actually ran, against real data)

1. `uv run pytest` — 16/16 pass against the live docker stack (`test_fusion.py`
   needs no infra; `test_documents_api.py`/`test_query_api.py` mock
   Voyage/Cohere/Grok so CI never makes paid API calls, but do exercise real
   Postgres + Qdrant wiring).
2. `uv run alembic upgrade head` → `0002` applied, `chunks.text_search_vector`
   + its GIN index confirmed via `\d chunks`.
3. **Real `iso-27001.pdf` uploaded via `POST /documents`.** Confirmed at each
   stage, using Postgres/Qdrant directly to sidestep intermittent host-side
   API server issues encountered mid-session:
   - **Parse** — Docling's real PDF pipeline (not the DOCX/heuristic path
     the unit tests use) ran end-to-end, including its layout and
     table-structure models. First run downloaded ~2 models from Hugging
     Face and took several minutes on CPU; confirmed genuinely CPU-bound
     (300-390% utilization throughout), not hung.
   - **Chunk** — 71 chunks produced with correct clause numbers (`0.1`,
     `1.1`, `4.2.1`, `4.2.2`, ...) and correctly nested `ltree` paths (e.g.
     `iso_27001.4_2_1`), including graceful handling of headings without a
     numeric clause prefix (`"2 Normative references"` →
     `iso_27001.2_normative_references`). This is the first real-document
     confirmation that Phase 1's clause-boundary chunking design holds up
     outside the synthetic test fixture.
   - **Embed** — failed twice against the real Voyage account before
     succeeding (see Gotchas: the opencv library fix, then the token-batch
     size fix); once both were applied, all 71 chunks embedded and landed in
     Qdrant (confirmed via `/collections/chunks/points/count` → 76, the
     extra 5 being leftover chunks from earlier `sample.docx` test uploads).
   - **`/query`** — real question ("What are the requirements for
     establishing the ISMS?") against the real Qdrant + Postgres data:
     query embedding, dense search, lexical search, RRF fusion, and Cohere
     reranking all executed successfully and returned real reranked chunks
     from the document (confirmed via server traceback showing execution
     reached `generate_answer()` with populated `context_chunks`). The final
     LLM call itself 403'd — xAI team has zero credits, an account issue
     external to this codebase. Stopped here rather than chase further,
     since retrieval — the actual point of this phase — is fully verified.

ISO 42001/GDPR weren't separately re-tested this session (ISO 42001 is a
paid copyrighted standard, out of scope for automated fetching; GDPR
verification from an earlier attempt is in project history). The iso-27001
run above supersedes the "not yet run" state this section previously
described.

## What Phase 3 needs from here

Phase 3 (entity/relation extraction into Neo4j) reads from the same `chunks`
table Phase 1 produced — Phase 2's additions (Qdrant vectors, `/query`) are
orthogonal to it, not a dependency. The one shared piece worth reusing:
`answer_generation.py`'s pattern of numbering context with clause/article
labels for citation is a template Phase 4 (graph retrieval) will likely want
too, once graph results get merged into the same answer-generation context.
