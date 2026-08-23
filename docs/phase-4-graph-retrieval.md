# Phase 4 — Graph Retrieval

Status: **done and verified live, both parts.** Part 1 (local search) and
Part 2 (global search) are both built and confirmed working against the
real, multi-document ISO 27001 graph from Phase 3 (see "Live verification"
and "Part 2 live verification" below).

## Goal

Answer relationship queries via graph traversal, and combine that with the
Phase 2 vector layer so answers draw on both — this is the phase where the 5
core use cases from the project's problem statement start actually working
(cross-standard mapping, gap analysis, multi-hop traversal, audit evidence
lookup, impact analysis).

## Concepts to learn first

- **Cypher fundamentals** — enough to write multi-hop pattern-matching
  queries (`(a)-[:REQUIRES]->(b)-[:REFERENCES]->(c)`) and understand query
  plans well enough to know why a traversal is slow.
- **Local vs. global search (the GraphRAG distinction)** — local search starts
  from specific named entities and traverses N hops outward (good for "what
  references X"); global search queries the Phase 3 community summaries first
  and only drills into raw entities/relations if needed (good for broad,
  holistic questions). Conflating these is the most common GraphRAG mistake —
  local search alone can't answer "what's missing across two standards"
  because there's no single starting entity for that question.
- **Provenance tracing** — every graph node/edge carries which chunk/document
  it came from (Phase 3); this phase is where that provenance actually gets
  surfaced as a citation in the final answer, not just stored.

## The key design question, resolved

How does the system decide *which* graph entities/communities are relevant to
a natural-language question? Checked how entity embeddings actually get
created (`entity_resolution.py`): they're embeddings of the bare **entity
name** ("Access Control Policy"), not a sentence — comparing that directly
against a full-question embedding is a weaker match than name-vs-name (used
for dedup) or sentence-vs-sentence (used for chunk retrieval). Rather than
build a new, separately-tuned entity-embedding-similarity path, **local
search reuses Phase 2's already-excellent chunk retrieval as its entry
point**: rerank finds the best-matching chunks, every relation edge already
carries `chunk_id` provenance (Phase 3), so "which entities did this chunk
mention" is a direct lookup — no new embedding infra needed at all.

**Global search can't use that same trick** — its whole reason to exist is
answering thematic/aggregate questions ("what are ISO 42001's main themes?")
that don't map well to any single chunk, which is exactly what chunk-seeding
would fail on. It needs its own path: embed each community summary at
creation time, compare the question embedding against those directly. This
is real, separate infrastructure — hence the Part 1/Part 2 split.

## Part 1 components (local search)

1. **`graph_store.py` additions** (new Neo4j query primitives, same style as
   existing `fetch_all_relations`/`fetch_document_graph`):
   - `fetch_entities_for_chunks(driver, chunk_ids)` — entities touched by a
     given set of chunks (the chunk→graph pivot point).
   - `fetch_relations_touching(driver, entity_keys)` — one hop's worth of
     relations from a frontier of entities (local search's BFS primitive).
   - `fetch_relations_by_type(driver, relation_type, entity_key=None)` — a
     generic relation-type-filtered lookup. Covers **two** of the roadmap's
     three named templates for free: "what references X" is
     `relation_type=REFERENCES, entity_key=X`; "cross-standard mapping
     lookup" is `relation_type=MAPS_TO` (no entity filter for a corpus-wide
     view, or filtered to one standard). One query shape, two use cases —
     didn't build three separate rigid templates since two of the three
     roadmap examples are the same shape with a different parameter.
2. **`app/services/local_search.py`** — `expand_hops(seed_keys,
   fetch_relations_fn, max_hops)`: pure BFS over the frontier, with the Neo4j
   fetch **injected as a callable** — same dependency-injection idiom
   `entity_resolution.resolve_entities`'s `embed_fn` param already
   established, so the traversal/stopping logic is unit-testable with a fake
   fetcher, no live Neo4j needed for that part.
3. **`/query` route**: after the existing rerank step (unchanged), pivot into
   the graph from the reranked chunks' entities, expand N hops, fetch any
   *additional* chunks the traversal surfaced (for their citation metadata),
   and pass the graph facts to `answer_generation.generate_answer` as a new
   optional `graph_facts` parameter — **sectioned, not interleaved**, in the
   prompt (a clearly separate "Graph-derived facts" block after the vector
   excerpts), so it stays possible to tell which source drove which part of
   an answer. Every graph fact still cites back to a real `chunk_id`/
   `clause_number` via the relation's own provenance — same `Citation` shape
   Phase 2 already returns, no schema change needed.
4. Default hop count: **2**, a plain module constant
   (`local_search.DEFAULT_MAX_HOPS`), same "empirical starting point, tune
   against real corpus" spirit as `extraction.py`'s pacing constants — see
   "Live verification" below for why that number alone wasn't enough.

## Live verification

Ran a real question ("What does the organization need to do regarding
information security risks?") against the real multi-document graph (ISO
27001 English PDF + the French ISMS training deck, both from Phase 3's live
testing) via a script exercising the actual retrieval pipeline:

- Rerank correctly surfaced real, on-topic chunks (clauses 4.2.2, 6.1.1,
  6.1.2 — risk treatment plan, risk assessment process).
- Chunk→entity pivot found 20 real seed entities from those 5 chunks
  (`Risk:'Information security risks'`, `Process:'Information security risk
  assessment process'`, `Role:'Organization'`, ...).
- Cross-document entity resolution is visible in the results: relations
  touching `Requirement:'SMSI'` (the French document's term for ISMS) came
  back alongside the English-document entities in the same traversal,
  confirming the graph really is one connected corpus-wide structure, not
  siloed per document.

**One real problem found, not caught by unit tests (which use small,
hand-built graphs where this never surfaces):** an *uncapped* 2-hop
traversal from those 20 seed entities returned **321 relations** — Neo4j
Community edition's whole graph is well-connected enough that a real corpus
makes BFS expansion grow very fast. 321 formatted relations would have
blown up the answer-generation prompt's size and cost for no real benefit
(diminishing relevance the farther a fact is from the seed chunks). Fixed
by capping how many graph facts actually reach the LLM
(`query.py`'s `_MAX_GRAPH_FACTS = 30`) — **not** by capping inside
`expand_hops` itself, so that function stays a complete, honest traversal
(useful on its own for future debugging) and the cap is purely "how much of
that evidence is worth spending prompt budget on," the same "gather
broadly, then narrow before the LLM" shape `_DENSE_TOP_K` vs. `top_k`
already uses on the vector-search side. Re-verified: 321 relations in, 30
reach `generate_answer`.

**Full end-to-end answer generation is currently blocked**, same as Phase
2: the xAI (Grok) team account has zero credits/billing
(`openai.PermissionDeniedError: 403 ... doesn't have any credits or
licenses yet`) — confirmed this is unrelated to Phase 4's own code, since
everything up through context/graph-facts construction executed correctly
and the failure is the external answer-generation API call itself. Testing
against the 5 core use cases' actual generated answers is blocked on that
billing issue being resolved, not on anything left to build here.

## Part 2 (global search) — what was built

- `Community.summary` is now embedded at creation time (Voyage,
  `input_type="document"` — one extra call per community, cheap) and stored
  as `summary_embedding`, via `graph_store.create_community`'s new required
  param and `detect_communities_task`. Reusing the *same* `query_vector`
  Phase 2 already computes for dense chunk search (no extra embedding call
  needed at query time) is what makes question-vs-summary comparison
  cheap.
- `app/services/global_search.py`'s `find_similar_communities` — brute-force
  cosine ranking over community summary embeddings, same pattern
  `entity_resolution.py` already uses for entity dedup (fine at this
  project's scale — a few dozen communities, not millions). No minimum-
  similarity threshold, deliberately: unlike entity resolution's precise
  "same entity or not" bar, "thematically related" is inherently fuzzy, and
  a real classifier is Phase 5's job, not this baseline's.
- New `graph_store.py` primitives: `fetch_community_embeddings` (id/title/
  summary/embedding, for ranking) and `fetch_community_members` (drill-down
  — every entity linked to a community via `IN_COMMUNITY`). Deliberately
  kept separate from `fetch_communities` (the API inspection endpoint),
  which excludes the embedding vector on purpose — a 1024-float array has
  no place in a human-facing response.
- `/query` route: reuses the same driver session as local search, ranks
  communities, and for each of the top matches drills into its member
  entities via the *existing* `fetch_relations_touching` (the same
  primitive local search's BFS uses, called once per matched community
  rather than expanded — a community's members are already a curated
  cluster, so one hop out from them is the citable substance, not more
  BFS expansion). Capped per community (`_MAX_DRILLDOWN_FACTS_PER_COMMUNITY
  = 10`) for the same reason local search's graph facts got capped.
  Rendered as a **third, separately-labeled** prompt section ("Related
  themes") — a community's own summary line (no citation, it's a
  synthesis) followed by its cited drill-down specifics.

## Part 2 live verification

Backfilled embeddings for the real corpus by re-running community
detection (full recompute is already this task's designed behavior — no
special migration needed). Real run: **61 communities created** (up from
the earlier 25 — the corpus had grown since Part 1's original detection
run), 98 singletons skipped.

Ran a real thematic question ("What are the main themes around risk
management in this corpus?") through `find_similar_communities` against
the real embeddings:

**Two things found live:**
1. **Global search's mechanics work correctly and rank genuinely well** —
   filtered to the corpus's substantive communities, the top match was
   *"ISMS Framework and Risk Management Lifecycle"* (52 entities), exactly
   right for the question, with sensible runners-up ("Governance and
   Implementation of...SMSI", "Core Components of the ISMS").
2. **A real, more severe version of Phase 3's already-documented test-data
   finding**: of the 61 communities, **39 have exactly 2 entities** — almost
   entirely leftover pytest fixtures accumulated across this session's many
   test runs (`test_graph_store.py`/`test_communities_api.py` etc. create
   real `Control`/`Risk` entities+relations in the shared dev Neo4j with no
   cleanup, by established test-repeatability convention). Only 12
   communities have more than 5 entities. Unfiltered, the *actual* top
   match for the same question was a trivial 2-entity "Control mitigates
   Risk" test-fixture community — generic-sounding LLM summaries of tiny
   test clusters can cosine-rank *above* large, genuinely thematic real
   clusters, since local search's chunk-seeding (immune to this — test
   fixtures aren't linked to real ingested documents) doesn't protect
   global search's corpus-wide ranking the same way.
   **Deliberately not "fixed" with an arbitrary size filter** — that would
   paper over the real root cause (shared dev/test database, not a global
   search design flaw) and risk hiding genuinely small-but-meaningful real
   clusters in a properly separated production database. Documented as a
   known consequence of this project's dev-convenience convention, same as
   Phase 3's version of this finding — a real production deployment needs
   an actually separate test database, not just unique per-test names.
- Docker rebuild note: rebuilding `worker-graph` to pick up these code
  changes hit a network-level TLS failure (`pip install uv` inside the
  build couldn't verify pypi.org's cert) unrelated to this project's own
  code — the exact same Dockerfile had built successfully earlier this
  session, so something about the host's network/VPN state changed
  in between. Worked around by running `detect_communities_task()` directly
  from the host venv (which already has every dependency via `uv sync
  --all-extras`) instead of waiting on the container rebuild — same
  workaround pattern used throughout this project's live-verification
  scripts. `worker-graph`'s container image is stale relative to the code
  until that build succeeds; not a code problem to fix.

## Test against the 5 core use cases

Retrieval itself (rerank → chunk→entity pivot → BFS traversal → capped
graph facts) is live-verified against real data — see above. Running the 5
example questions from the roadmap's problem statement through to an
actual *generated, cited answer* is next, blocked only on the xAI billing
issue above being resolved (same external blocker Phase 2 hit).

## Learning checkpoint (from the roadmap)

You understand local vs. global search in GraphRAG and can trace exactly which
graph traversal produced which answer.
