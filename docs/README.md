# ComplianceGraph — Phase Docs

Companion docs to `GraphRAG-Agentic-RAG-Roadmap.md` (the top-level plan). Each
roadmap phase gets one file here, written in two passes:

1. **Before implementing** — the plan: goal, concepts to learn, planned
   components with design rationale, open decisions to confirm.
2. **After implementing** — the same file is updated in place (not replaced)
   to reflect what was actually built, gotchas hit, and how to verify it. It
   becomes the as-built reference for that layer of the system.

## Part 1 — Platform roadmap (GraphRAG + Agentic RAG core)

| Phase | Doc | Status |
|---|---|---|
| 0 — Environment & repo setup | [phase-0-setup.md](phase-0-setup.md) | Done |
| 1 — Document ingestion pipeline | [phase-1-ingestion.md](phase-1-ingestion.md) | Done |
| 2 — Vector layer | [phase-2-vector-layer.md](phase-2-vector-layer.md) | Done |
| 3 — Entity & relation extraction | [phase-3-extraction.md](phase-3-extraction.md) | Done |
| 4 — Graph retrieval | [phase-4-graph-retrieval.md](phase-4-graph-retrieval.md) | Done |
| 5 — Agentic orchestration | [phase-5-agentic-loop.md](phase-5-agentic-loop.md) | Done |
| 6 — Frontend | [phase-6-frontend.md](phase-6-frontend.md) | Done |
| 7 — Evaluation harness | [phase-7-evaluation.md](phase-7-evaluation.md) | Done |
| 8 — Scaling & hardening (final phase) | [phase-8-scaling.md](phase-8-scaling.md) | Done |

Two supporting docs for Phase 8 (not roadmap phases of their own):
[phase-8-sharding-strategy.md](phase-8-sharding-strategy.md) (a documented,
deliberately-not-yet-built graph-partitioning strategy) and
phase-8-load-test-results.md (real per-stage ingestion timing — not yet
generated; see phase-8-scaling.md's own disclosed gap on this).

**All 9 phases of the platform roadmap are complete.**

## Part 2 — Compliance Codebase Scanner & Agentic Audit Engine

A second, separate initiative built on top of the same platform: scans an
uploaded repository (zip upload) and maps technical evidence to ISO 27001 /
ISO 42001 / GDPR requirements — always evidence-based, never a bare
compliant/non-compliant verdict. Its own 9-phase numbering, independent of
Part 1's phases above.

| Phase | Doc | Status |
|---|---|---|
| 1 — Scanner foundation (ingestion, file classification) | [scanner-phase-1-foundation.md](scanner-phase-1-foundation.md) | Done |
| 2 — Deterministic security scanner | [scanner-phase-2-security-scanner.md](scanner-phase-2-security-scanner.md) | Done |
| 3 — GDPR analyzer | [scanner-phase-3-gdpr-analyzer.md](scanner-phase-3-gdpr-analyzer.md) | Done |
| 4 — AI / ISO 42001 analyzer | [scanner-phase-4-ai-iso42001-analyzer.md](scanner-phase-4-ai-iso42001-analyzer.md) | Done |
| 5 — ISO 27001 control mapping | [scanner-phase-5-iso27001-mapping.md](scanner-phase-5-iso27001-mapping.md) | Done |
| 6 — Agentic RAG finding validation | [scanner-phase-6-agentic-rag.md](scanner-phase-6-agentic-rag.md) | Done |
| 7 — Human review | [scanner-phase-7-human-review.md](scanner-phase-7-human-review.md) | Done |
| 8 — Reports | [scanner-phase-8-reports.md](scanner-phase-8-reports.md) | Done |
| 9 — Auto remediation (final phase) | [scanner-phase-9-auto-remediation.md](scanner-phase-9-auto-remediation.md) | Done |

**All 9 phases of the scanner roadmap are complete.** Both halves of this
project (Part 1 and Part 2) are now feature-complete per their original specs.

"Planned" (where it still appears in an individual doc's own status line)
means the pre-implementation plan exists but the phase hasn't been built
yet — no phase doc in either table above is currently in that state.
