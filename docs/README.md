# ComplianceGraph — Phase Docs

Companion docs to `GraphRAG-Agentic-RAG-Roadmap.md` (the top-level plan). Each
roadmap phase gets one file here, written in two passes:

1. **Before implementing** — the plan: goal, concepts to learn, planned
   components with design rationale, open decisions to confirm.
2. **After implementing** — the same file is updated in place (not replaced)
   to reflect what was actually built, gotchas hit, and how to verify it. It
   becomes the as-built reference for that layer of the system.

| Phase | Doc | Status |
|---|---|---|
| 0 — Environment & repo setup | [phase-0-setup.md](phase-0-setup.md) | Done |
| 1 — Document ingestion pipeline | [phase-1-ingestion.md](phase-1-ingestion.md) | Done |
| 2 — Vector layer | [phase-2-vector-layer.md](phase-2-vector-layer.md) | Done |
| 3 — Entity & relation extraction | [phase-3-extraction.md](phase-3-extraction.md) | Part 1 done |
| 4 — Graph retrieval | [phase-4-graph-retrieval.md](phase-4-graph-retrieval.md) | Planned |
| 5 — Agentic orchestration | [phase-5-agentic-loop.md](phase-5-agentic-loop.md) | Planned |
| 6 — Frontend | [phase-6-frontend.md](phase-6-frontend.md) | Planned |
| 7 — Evaluation harness | [phase-7-evaluation.md](phase-7-evaluation.md) | Planned |
| 8 — Scaling & hardening | [phase-8-scaling.md](phase-8-scaling.md) | Planned |

"Planned" means the pre-implementation doc exists (goal, concepts, planned
components, open decisions) but the phase hasn't been built yet. Each becomes
"Done" once implemented, with the same file updated in place to reflect what
was actually built.
