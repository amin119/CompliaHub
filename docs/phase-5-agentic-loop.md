# Phase 5 — Agentic Orchestration Layer

Status: **planned** — not yet implemented. Depends on Phases 2 and 4 (needs
both vector and graph retrieval as tools the agent can call). Pre-implementation
plan; update in place once built.

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

## Planned components

1. **Query classifier** — a cheap few-shot LLM prompt (or simple heuristics)
   that routes: simple factual → vector only (Phase 2), relational → graph
   (Phase 4), complex/multi-step → full agent loop (this phase).
2. **LangGraph agent** — nodes for `plan`, `retrieve` (agent decides vector or
   graph), `critique` (is this enough evidence?), `rewrite_query`, `answer`,
   with conditional edges and a loop-back on insufficient evidence.
3. **Budget/stop condition** — max iterations and max tokens, so the agent
   can't loop forever on an unanswerable or adversarial query.
4. **Checkpointing** — LangGraph's built-in checkpointing so long-running
   agent sessions are resumable and inspectable (you can see exactly which
   step the agent was on).
5. **Wire the classifier as the `/query` entrypoint** — this becomes the
   adaptive routing layer sitting in front of Phases 2 and 4.

## Open decisions to confirm before coding

- **Classifier implementation** — simple keyword/heuristic rules (fast,
  free, but brittle) vs. a cheap few-shot LLM prompt (roadmap's suggestion,
  more robust to phrasing variation, small but nonzero cost per query).
- **Default budget values** — max iterations and max tokens per agent run;
  needs a number that's generous enough for the hardest of the 5 core use
  cases but still bounded.
- **Checkpoint storage** — LangGraph supports Postgres or SQLite checkpointers
  out of the box; given Postgres is already in the stack (Phase 0), reusing it
  avoids adding SQLite as a second persistence mechanism.

## Learning checkpoint (from the roadmap)

You understand the difference between workflow RAG (fixed pipeline) and true
agentic RAG (model decides retrieval actions), and why adaptive routing keeps
costs sane.
