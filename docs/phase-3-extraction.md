# Phase 3 — Entity & Relation Extraction

Status: **planned** — not yet implemented. Depends on Phase 1 (chunks to
extract from) and benefits from Phase 2 existing (entity resolution uses
embedding similarity). Pre-implementation plan; update in place once built.

## Goal

Turn chunks into a knowledge graph — this is where "GraphRAG" actually starts,
and the highest-leverage phase for the project's core use cases (cross-standard
mapping, gap analysis, multi-hop traversal).

## Concepts to learn first

- **The Microsoft GraphRAG paper (Edge et al., 2024)** — the reference
  architecture this whole project follows loosely: extract entities/relations
  per chunk, build a graph, detect communities, summarize communities so
  "global" questions become answerable. Read this before writing any
  extraction code.
- **LLM-based structured extraction** — forcing an LLM to emit validated JSON
  (entities + relations) per chunk, and why a Pydantic schema gate matters:
  without it, malformed output silently corrupts the graph instead of failing
  loudly.
- **Entity resolution / deduplication** — why "personal data" in GDPR and in
  ISO 42001 need to resolve to the *same* node for cross-standard questions to
  work at all, and why this needs both embedding similarity (fuzzy) and
  exact-match rules (precise) rather than either alone.
- **Community detection (Leiden algorithm)** — why flat entity/relation graphs
  can't answer holistic questions like "what does ISO 42001 require that ISO
  27001 doesn't cover" — you need clusters with LLM-written summaries so the
  system can search *summaries* first, then drill into raw entities. This is
  GraphRAG's key trick and the reason it beats plain vector RAG on broad
  questions.

## Planned components

1. **Ontology definition (do this first, on paper, before any code)**
   - Entity types: `Standard`, `Clause`, `Control`, `Requirement`, `Risk`,
     `Asset`, `Process`, `Role`, `Definition`.
   - Relation types: `requires`, `references`, `implements`, `maps_to`,
     `is_prerequisite_for`, `applies_to`, `defined_in`, `part_of`,
     `superseded_by`.
2. **Extraction prompting** — one structured LLM call per chunk, forced JSON
   output, validated against a Pydantic model before it's accepted into the
   pipeline.
3. **Batch processing with caching** — this is the expensive step (one LLM
   call per chunk × thousands of chunks eventually). Cache extraction results
   by chunk hash (from Phase 1) so unchanged text is never re-extracted —
   this is what makes incremental ingestion (Phase 8) actually affordable.
4. **Entity resolution / deduplication** — merge candidate entities using
   embedding similarity (Phase 2's embedding model) plus exact-match rules.
5. **Load into Neo4j** — entities as nodes, relations as edges, each edge/node
   carrying provenance (which chunk/document it came from) — this is what
   lets an answer later cite back to an exact clause.
6. **Community detection** — Leiden algorithm over the graph, LLM-generated
   summary per community.

## Open decisions to confirm before coding

- **Which LLM for extraction** — this runs once per chunk across the whole
  corpus, so cost matters more than for one-off queries. A cheaper/faster
  model (e.g. Claude Haiku) for the bulk extraction pass, reserving a stronger
  model for anything needing deeper reasoning, is worth considering vs. using
  one model everywhere for simplicity.
- **Leiden implementation** — a Python graph library (e.g. `graspologic`,
  `python-igraph`) run against data pulled from Neo4j, vs. Neo4j's own Graph
  Data Science (GDS) plugin running Leiden inside the database. GDS avoids
  round-tripping the graph in and out of Python but adds a Neo4j plugin
  dependency.
- **Entity resolution threshold** — where to set the embedding-similarity cut
  line between "same entity" and "different entity," and whether to review
  merges manually at first (given a small 3-standard corpus) before trusting
  it unsupervised at Phase 8 scale.

## Learning checkpoint (from the roadmap)

You understand LLM-based structured extraction, entity resolution, and why
community detection + summarization enables holistic/global queries that
plain graph traversal can't.
