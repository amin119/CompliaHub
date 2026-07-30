# Phase 7 — Evaluation Harness

Status: **planned** — not yet implemented. Depends on Phase 5 (needs the full
adaptive-routing `/query` endpoint to evaluate end-to-end). Pre-implementation
plan; update in place once built.

## Goal

Stop trusting gut feel about answer quality and start measuring it
quantitatively, so future changes to retrieval/extraction/prompting can be
judged as "better" or "worse" objectively, not just "feels different."

## Concepts to learn first

- **RAGAS metrics** — faithfulness (does the answer only state what's actually
  in the retrieved context, no hallucination), answer relevance (does it
  actually address the question), context precision/recall (did retrieval
  surface the right evidence, and how much of it was noise). Understanding
  what each metric actually measures matters more than just running the
  library — a high score on the wrong metric for a given failure mode is
  misleading.
- **Retrieval evaluation methodology** — why you need ground-truth
  question/answer/citation pairs to evaluate against, and why 30–50 questions
  spanning all 5 use-case categories (not just "easy" factual ones) is the
  minimum for a meaningful signal.
- **Regression testing for LLM/RAG systems** — unlike deterministic code,
  outputs vary run to run; a regression suite here means re-running the same
  eval set after every significant change and comparing aggregate metrics,
  not asserting exact string equality.

## Planned components

1. **Test set** — 30–50 real questions across the project's 5 core use-case
   categories (cross-standard mapping, gap analysis, multi-hop traversal,
   audit evidence lookup, impact analysis), each with a ground-truth
   answer/citation.
2. **RAGAS (or custom eval) integration** — faithfulness, answer relevance,
   context precision/recall computed per question.
3. **Per-query tracking** — which path was taken (vector-only / graph /
   full agentic loop, from Phase 5's classifier), latency, cost, and
   correctness, so quality can be sliced by routing path.
4. **Regression testing** — re-run the eval set on every significant pipeline
   change (retrieval tuning, prompt changes, model swaps) and compare against
   the previous run's aggregate scores.

## Open decisions to confirm before coding

- **RAGAS vs. a custom eval harness** — RAGAS is the roadmap's pick and comes
  with the four metrics above out of the box; a custom harness gives more
  control but means reimplementing metric logic that's already
  well-established.
- **Where eval results/history live** — a simple Postgres table (reuses
  existing infra, easy to query trends over time) vs. a dedicated tool like
  Langfuse datasets (richer UI, but another system to maintain).
- **How ground-truth answers get created** — fully manual (most trustworthy,
  slow for 30–50 questions) vs. LLM-drafted with human review (faster, needs
  careful review to avoid the eval set inheriting the same biases/blind spots
  as the system being evaluated).

## Learning checkpoint (from the roadmap)

You can quantitatively say "this change improved retrieval quality by X%"
instead of guessing.
