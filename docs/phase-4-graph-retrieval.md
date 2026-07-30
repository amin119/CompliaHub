# Phase 4 — Graph Retrieval

Status: **planned** — not yet implemented. Depends on Phase 3 (needs a
populated graph with communities to query). Pre-implementation plan; update in
place once built.

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

## Planned components

1. **Cypher query templates** for the recurring patterns: multi-hop
   traversal, cross-standard mapping lookup, "what references/implements X."
2. **Local search mode** — start from one or more matched entities, traverse
   N hops.
3. **Global search mode** — query community summaries first, drill down into
   the underlying entities/relations only for the communities that match.
4. **Combine graph results + vector results (Phase 2)** into a single context
   for the LLM to answer from, with citations back to exact clause numbers
   pulled from provenance.
5. **Test against the 5 core use cases** from the roadmap's problem statement
   — this phase is "done" when all 5 produce correct, cited answers.

## Open decisions to confirm before coding

- **Default hop count for local search** — too few hops misses relevant
  context, too many pulls in noise and blows up context size; likely needs
  empirical tuning against the 5 use cases rather than picking a number
  upfront.
- **How to merge graph + vector evidence in one prompt** — interleaved (both
  sources mixed by relevance) vs. sectioned (graph evidence and vector
  evidence presented in clearly separate blocks so the LLM can weigh them
  differently). Sectioned is more transparent for debugging which source
  drove an answer.

## Learning checkpoint (from the roadmap)

You understand local vs. global search in GraphRAG and can trace exactly which
graph traversal produced which answer.
