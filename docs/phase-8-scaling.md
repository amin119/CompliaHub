# Phase 8 — Scaling & Hardening

Status: **planned** — not yet implemented. Depends on Phases 1–7 all existing
in working form; this phase stress-tests and hardens them rather than adding
new user-facing features. Pre-implementation plan; update in place once built.

## Goal

Prove the "very very large number of files" claim from the project's
non-goals/success criteria — not just that the pipeline works on the small
3-standard corpus, but that it holds up at real scale, and that incremental
updates actually work end-to-end.

## Concepts to learn first

- **Incremental graph maintenance** — adding a new document is easy
  (Phase 1's hashing already supports it); *updating* or *deleting* one is
  harder, because entities/edges from Phase 3 may have been merged across
  multiple source documents (entity resolution) — removing one document's
  contribution without breaking shared nodes needs careful provenance
  tracking, not just deleting everything tagged with that document's ID.
- **LLM extraction cost as the real bottleneck** — at scale, Phase 3's
  per-chunk extraction calls (not parsing, not embedding) are almost always
  where time and money go; this phase is about proving that batching,
  parallelizing, and chunk-hash caching (already designed into Phase 1/3)
  actually hold up under real load, not just in theory.
- **Observability for pipelines and agent loops** — structured logging and
  tracing across async, multi-step processes (Celery jobs, LangGraph agent
  runs) is qualitatively different from logging a synchronous request — you
  need to be able to reconstruct one document's or one query's entire journey
  after the fact.

## Planned components

1. **Incremental updates end-to-end** — add/update/delete a document without
   full reprocessing; propagate changes to the graph and vector store
   correctly, including cleaning up stale edges left behind when a document
   is removed or changed.
2. **Load test ingestion** — feed a large synthetic/messy corpus (thousands of
   files) through the full pipeline, measure throughput, and find the actual
   bottleneck (expected to be Phase 3's LLM extraction calls).
3. **Sharding/partitioning strategy for the graph** — if it grows large,
   per-standard subgraphs with cross-standard edges as explicit bridges,
   rather than one undifferentiated graph.
4. **Observability** — structured logging + tracing across ingestion jobs
   (Phase 1) and agent loops (Phase 5), reusing prior Langfuse experience.
5. **Cost controls** — aggressive LLM call caching (extraction is already
   idempotent per chunk-hash from Phase 3), plus tracking token spend broken
   down by query type (from Phase 7's per-query tracking).
6. **Security/access control basics** — at minimum a sketch of role-based
   access, since this is compliance data, even if not fully implemented.

## Open decisions to confirm before coding

- **Stale-edge detection strategy** — provenance-tagged edges (from Phase 3)
  with a cleanup job that removes edges whose only supporting document was
  deleted/changed, vs. a full graph rebuild on every update (simpler but
  defeats the purpose of "incremental").
- **Langfuse deployment** — self-hosted (more control, more ops burden) vs.
  their cloud offering (less setup, data leaves the local stack).
- **Whether sharding is actually needed yet** — the real corpus is only 3
  standards; sharding might only matter for the synthetic large-corpus load
  test in this phase, not for production use at the project's actual scope —
  worth confirming before investing in partitioning logic that may not be
  needed for the real dataset.

## Learning checkpoint (from the roadmap)

You understand the real bottlenecks of graph-RAG at scale (LLM extraction
cost, incremental graph maintenance) and how production systems mitigate them.
