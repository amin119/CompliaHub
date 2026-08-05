# Phase 3 — Entity & Relation Extraction

Status: **Part 1 done and verified live** (ontology → extraction → caching →
entity resolution → Neo4j loading). Part 2 (community detection + LLM
community summaries) is **not started** — see "What's left" below. 51/51
backend tests pass; the extraction pipeline was verified end-to-end against
real Postgres + real Neo4j with a mocked LLM (no real Anthropic key was
available yet during this build — see "Live verification").

## Goal

Turn chunks into a knowledge graph — this is where "GraphRAG" actually starts,
and the highest-leverage phase for the project's core use cases (cross-standard
mapping, gap analysis, multi-hop traversal).

## Concepts learned

- **LLM-based structured extraction via forced tool-use.** Claude's tool-use
  mechanism, given a single tool whose `input_schema` *is* a Pydantic model's
  JSON schema, reliably returns schema-conformant output — but "reliably"
  isn't "always": the result is still validated with Pydantic afterward
  (never trust "guaranteed" structured output blindly), and a validation
  failure triggers a retry, since output is stochastic and a fresh sample can
  succeed.
- **A fixed ontology beats an open-ended one.** Entity/relation types are a
  closed `Enum`, not free text the model can invent — an LLM free to emit
  `:SecurityControl` one time and `:Control` another makes entity resolution
  and Cypher queries unreliable. Under-extraction (empty lists) is the
  correct behavior for a chunk that doesn't fit cleanly, not inventing a
  new type.
- **Content-hash caching, not id-based.** Caching by `sha256(chunk.text)`
  rather than by chunk id means identical boilerplate text repeated across
  chunks/documents (a definition restated verbatim in multiple standards)
  only ever gets sent to the LLM once.
- **Entity resolution needs two stages.** Exact-match on a normalized name
  catches the bulk of duplicates for free; embedding similarity (reusing
  Phase 2's Voyage embedder) catches the rest ("PII" vs. "Personal Data") —
  neither alone is enough.
- **Composite uniqueness constraints need Neo4j Enterprise; per-label
  constraints don't.** Using `EntityType` as the node *label* (`:Control`,
  `:Risk`, ...) rather than a property means a single-property uniqueness
  constraint on `canonical_name`, scoped per label, achieves the same
  duplicate-prevention as a composite `(type, name)` constraint would — on
  `neo4j:5-community`, which we're running.

## What was built

```
backend/
├── alembic/versions/0003_extraction_cache.py  # chunk_extractions table + documents.graph_status
├── app/
│   ├── core/config.py                 # + anthropic_api_key/anthropic_extraction_model
│   ├── models/
│   │   ├── document.py                # + Document.graph_status/graph_error_message
│   │   └── extraction.py              # ChunkExtractionCache (own file — Phase 3's own concern)
│   ├── services/
│   │   ├── ontology.py                # EntityType/RelationType enums, ChunkExtraction Pydantic schema
│   │   ├── extraction.py              # ExtractionClient Protocol, Anthropic adapter, retry loop
│   │   ├── extraction_cache.py        # get_cached/store_result (content-hash keyed)
│   │   ├── entity_resolution.py       # normalize_name, cosine_similarity, resolve_entities
│   │   └── graph_store.py             # Neo4j driver wrapper: constraints, upsert, relations, fetch
│   ├── schemas/graph.py                # GraphEntity/GraphRelation/DocumentGraphResponse
│   ├── tasks/
│   │   ├── ingestion.py                # pipeline_stage generalized (status_field/error_field params)
│   │   └── extraction.py               # extract_document_task, resolve_and_load_document_task
│   └── api/routes/extraction.py        # POST /documents/{id}/extract, GET /documents/{id}/graph
└── tests/
    ├── test_ontology.py, test_extraction.py, test_entity_resolution.py   # no infra needed
    ├── test_graph_store.py                                               # needs live Neo4j
    └── test_extraction_api.py                                            # needs live Postgres+Neo4j
```

## Decisions made

- **Extraction LLM: Anthropic Claude Haiku** (`claude-haiku-4-5-20251001`).
  `ANTHROPIC_API_KEY` scaffolded empty (in `.env.example`, `backend/.env.example`,
  and `docker-compose.yml`'s `worker` service) — a real key wasn't available
  during this build; the live-verification section below reflects that.
- **Trigger: separate, explicit `POST /documents/{id}/extract`** — not
  auto-chained after Phase 2's embedding stage. Requires `document.status ==
  "ready"` first. Lets extraction be re-run later (improved prompt, larger
  corpus) without re-uploading/re-parsing, which the content-hash cache is
  specifically designed to make cheap.
- **`graph_status`/`graph_error_message` are separate columns from `status`/
  `error_message`.** A document is `ready` for vector/lexical search (Phase 2)
  independent of whether graph extraction has ever run — extraction must
  never clobber the ingestion status those other features depend on.
- **`pipeline_stage` (Phase 1's context manager) generalized, not
  duplicated.** Added `status_field`/`error_field` parameters, defaulting to
  the original `"status"`/`"error_message"` so Phase 1/2's three ingestion
  tasks needed zero changes; Phase 3's two extraction tasks pass
  `"graph_status"`/`"graph_error_message"`. Caught during implementation,
  not planning — the original plan assumed no changes were needed here,
  which turned out to be wrong on closer inspection.
- **Sequential per-chunk extraction, not fanned out concurrently** — same
  reasoning as Phase 2's `embed_chunks_task`: a fresh API key's rate limits
  are the binding constraint, and concurrent Celery tasks hitting them
  immediately is worse than one call at a time.
- **Community detection: Python-side (`igraph` + `leidenalg`), not Neo4j's
  GDS plugin** — avoids another new Docker/infra dependency. Not built yet
  (Part 2); the library itself is installed and sanity-checked (Step 0: a
  toy 6-node graph correctly split into its two true communities).
- **Roadmap deviation, mirroring Phase 1's:** entity resolution's "compare
  against existing entities" step does a plain Python cosine-similarity scan
  over every entity currently in Neo4j (`fetch_all_entities`), not a vector
  index (Qdrant or Neo4j's native one). Fine at this project's scale
  (hundreds-to-low-thousands of entities); revisit only if it becomes a real
  bottleneck at Phase 8 scale.

## Gotchas worth remembering

- **Embedding cost: don't compute it twice.** The first version of
  `resolve_and_load_document_task` called `embed_texts` a second time per
  resolved entity to get its embedding for the Neo4j upsert — but
  `entity_resolution.resolve_entities` had *already* computed that same
  embedding internally for the similarity comparison. Fixed by adding an
  `embedding: list[float] | None` field to `ResolvedEntity`, populated
  during resolution and reused by the caller — cut the embedding calls for
  this stage roughly in half.
- **Mismatched embedding dimensions crash `cosine_similarity` with
  `zip(strict=True)`, not just theoretically.** Hit this for real: earlier
  manual testing of `graph_store.py` had left a couple of 3-dimensional test
  vectors in the shared dev Neo4j instance; comparing them against real
  1024-dimensional Voyage embeddings during a later test run raised
  `ValueError: zip() argument 2 is shorter than argument 1`. Fixed properly
  (not just by deleting the stray data): `cosine_similarity` now returns
  `0.0` for mismatched lengths instead of crashing — mismatched-dimension
  vectors can never be meaningfully "similar" anyway, and this also guards
  against a future embedding-model migration (Phase 8) leaving old and new
  dimensionalities mixed in the graph.
- **Test repeatability against a never-cleaned-up dev database.**
  `create_relation` always `CREATE`s a new edge (deliberately, for
  provenance — see "Decisions made" in the roadmap). That means an
  integration test reusing the same document across repeated test-suite runs
  would accumulate duplicate parallel edges and eventually fail its own
  count assertion. Fixed by embedding a fresh random UUID into the test
  document's *text content* (not just its filename) in
  `test_extraction_api.py`, guaranteeing a new `sha256` hash — and therefore
  brand new `Document`/`Chunk` rows — every run.
- **Schema docstrings are prompt content, not just documentation.**
  Pydantic's `model_json_schema()` embeds class docstrings verbatim as the
  `description` field in the JSON schema handed to Claude's tool-use call —
  this schema *is* sent as part of every single extraction call's context.
  The first draft of `ontology.py` had long docstrings explaining internal
  design rationale ("normalization happens later, in entity_resolution.py");
  trimmed to be LLM-relevant only, cutting the serialized schema from
  several KB down to ~1.5KB — a real, recurring token cost at "once per
  chunk across the whole corpus" scale, not a one-time nitpick.

## Live verification

1. `uv run pytest` — 51/51 pass (full project total, all phases). Ran
   directly against this session's live docker stack:
   - `test_ontology.py`, `test_extraction.py`, `test_entity_resolution.py` —
     no infra needed, pure functions + fake clients.
   - `test_graph_store.py` — real Neo4j: constraint creation, upsert
     idempotency (same name/type twice → one node, first embedding wins),
     same-name-different-type creating distinct nodes, relation creation +
     `fetch_document_graph` round-trip — all confirmed live.
   - `test_extraction_api.py` — real Postgres + real Neo4j, Voyage and
     Anthropic both mocked (no real API keys needed for this test):
     `POST /documents/{id}/extract` → `graph_status: "ready"` →
     `GET /documents/{id}/graph` returns the expected resolved
     entities/relation.
2. `uv run alembic upgrade head` — applied; `chunk_extractions` table and
   `documents.graph_status`/`graph_error_message` columns confirmed.
3. **Not yet run**: a real end-to-end extraction against real ISO 27001/GDPR
   chunks with a real `ANTHROPIC_API_KEY` — the key wasn't available during
   this build session. Once it is:
   ```
   docker compose build worker && docker compose up -d worker
   POST /documents/{id}/extract   (on the already-ingested iso-27001.pdf)
   poll GET /documents/{id} until graph_status == "ready"
   GET /documents/{id}/graph      → eyeball real entities/relations
   ```
   Worth watching for on that first real run: does the ontology's fixed
   entity/relation types actually fit ISO 27001's real clause language, or
   does something common get systematically under-extracted? That's exactly
   the kind of thing only a real run against real text can surface — same
   lesson as Phase 1's Docling PDF pipeline and Phase 2's Voyage rate limits.

## What's left (Part 2 — not built yet)

- **Community detection**: pull the graph via the `neo4j` driver into
  `igraph`, run `leidenalg.find_partition`, write a `community_id` property
  back onto each node. Library already installed and sanity-checked.
- **LLM-generated summary per community** — the piece that actually enables
  "global" questions (e.g. gap analysis across standards) per GraphRAG's
  core design; reuses the same Anthropic client pattern.
- Both depend on Part 1's graph having real data in it first (i.e. a real
  extraction run), so a natural next step once a real API key is available
  and Part 1 has been exercised against the real corpus.

## What Phase 4 needs from here

Phase 4 (graph retrieval) queries the entities/relations this phase writes
into Neo4j, plus (once Part 2 exists) the community summaries for global
search. The `chunk_id`/`document_id` provenance properties on every relation
edge are what let a Phase 4 answer cite back to an exact clause.
