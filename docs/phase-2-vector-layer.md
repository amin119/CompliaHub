# Phase 2 — Vector Layer

Status: **planned** — not yet implemented. Depends on Phase 1 (needs chunks
with metadata to embed). Pre-implementation plan; update in place once built
(see `docs/README.md`).

## Goal

A working baseline vector RAG system end-to-end — hybrid search + reranking +
LLM answer generation, no graph yet. This becomes the regression baseline
every later phase (graph, agentic) is measured against: if Phase 4/5 can't
beat this, they're not pulling their weight.

## Concepts to learn first

- **Embeddings & similarity search** — what a dense vector actually encodes,
  why cosine/dot-product similarity approximates semantic closeness.
- **Hybrid search rationale** — dense vectors miss exact keyword/ID matches
  (e.g. someone searching literally for "A.8.1" or "Article 32"); lexical
  search (BM25) catches those. Anthropic's Contextual Retrieval post is the
  reference for why combining both beats either alone on real-world corpora.
- **Reciprocal Rank Fusion (RRF)** — how to merge two independently-ranked
  result lists (dense + lexical) into one ranking without needing to
  calibrate their raw scores against each other.
- **Cross-encoder reranking** — why a second, more expensive pass that scores
  (query, chunk) pairs jointly catches relevance a bi-encoder's independent
  embeddings miss, and why you only run it on the top-K candidates, not the
  whole corpus.

## Planned components

1. **Embedding model choice** — see Open Decisions.
2. **Embed + store in Qdrant** — each chunk embedded and stored with metadata
   (source doc, clause number, hierarchy path from Phase 1) so results are
   traceable back to an exact citation, not just raw text.
3. **Hybrid search** — dense (Qdrant) + BM25 (Postgres full-text, reusing the
   metadata store from Phase 1), fused with RRF.
4. **Cross-encoder reranker** — reorders the fused top-K before it reaches the
   LLM.
5. **`/query` endpoint** — hybrid search + rerank + LLM answer generation, no
   graph. This is the first end-user-facing answer path in the system.
6. **Regression test with real questions** — run the 5 core use cases from the
   roadmap's problem statement before moving to Phase 3, so there's a "before
   graph" baseline to compare against later.

## Open decisions to confirm before coding

- **Embedding model** — API-based (e.g. Voyage, OpenAI, Cohere embed) vs. a
  local open model (e.g. BGE-large, E5). Trade-off: API is zero-setup but
  costs per token and adds network latency; local is free per-call but needs
  a GPU or accepts slower CPU inference, and adds a dependency to manage.
- **BM25 implementation** — Postgres's built-in `tsvector`/`ts_rank` (no new
  infra, good enough at this corpus size) vs. a dedicated lexical engine.
  Given the corpus is 3 standards (not yet "very very large"), Postgres
  full-text is the pragmatic default unless there's a reason to expect it
  won't scale.
- **Reranker** — hosted API (e.g. Cohere Rerank) vs. a local cross-encoder
  (e.g. `bge-reranker-base`). Same cost/latency-vs-infra trade-off as the
  embedding model choice, and ideally the same answer for consistency.

## Learning checkpoint (from the roadmap)

You can explain hybrid search, RRF fusion, and reranking, and you have a
working (if limited) RAG system.
