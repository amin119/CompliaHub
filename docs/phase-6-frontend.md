# Phase 6 — Frontend

Status: **planned** — not yet implemented. Parallel-able with Phase 5; needs
the `/query` endpoint (Phase 5) and ingestion status (Phase 1) to wire up for
real. The Phase 0 chat placeholder (`frontend/src/app/page.tsx`) is what this
phase replaces with real functionality. Pre-implementation plan; update in
place once built.

## Goal

A usable chat UI: streaming answers, clickable citations back to exact
clauses, a graph visualization of the retrieval path, and document
upload/job-status views wired to the real ingestion pipeline.

## Concepts to learn first

- **Streaming responses (SSE vs WebSocket)** — the roadmap's architecture
  diagram specifies REST/SSE between frontend and backend; Server-Sent Events
  are simpler than WebSockets for one-directional (server → client) token
  streaming and are the more common pattern for LLM chat UIs.
- **Graph visualization in the browser** — rendering a traversal path (nodes
  = entities, edges = relations from Phase 4) as an interactive diagram,
  which needs a dedicated graph-layout library rather than hand-rolled SVG.
- **Optimistic / polling UI for async jobs** — document uploads kick off a
  Celery pipeline (Phase 1) that takes time; the UI needs to show progress
  without the user refreshing, which means either polling a job-status
  endpoint or subscribing to updates.

## Planned components

1. **Chat interface with streaming responses** — replaces the Phase 0 static
   placeholder with a real input wired to `/query` (Phase 5), rendering
   tokens as they arrive via SSE.
2. **Citation display** — clickable references in the answer that jump to (or
   at least display) the exact clause/article they came from, using the
   provenance data from Phase 3/4.
3. **Graph visualization panel** — shows the traversal path for a given
   answer; useful for demos and for debugging *why* the system answered the
   way it did.
4. **Document upload UI** — wired to the Phase 1 `/documents` intake
   endpoint.
5. **Job status view** — shows ingestion progress (parsing → chunking →
   embedding → extraction) for uploaded documents, reading from Phase 1's
   `processing_jobs` table.

## Open decisions to confirm before coding

- **Streaming transport** — SSE (simpler, matches the roadmap's diagram,
  well-supported by `fetch` + `ReadableStream` in Next.js) vs. WebSocket
  (bidirectional, more setup, only needed if the UI ever needs to send
  interrupts mid-stream).
- **Graph visualization library** — options like `react-force-graph`,
  `cytoscape.js`, or `sigma.js`; trade-off is ease of React integration vs.
  performance on larger graphs vs. how much layout customization is needed.
- **Job status updates** — simple polling (easy, works everywhere) vs. SSE/WS
  push for job progress too (more real-time, more moving parts). Given
  ingestion jobs take seconds-to-minutes not milliseconds, polling is
  probably good enough and simpler.

## Learning checkpoint

You can trace a displayed answer's citations back to their exact source
clause, and visualize the retrieval path (graph and/or vector) that produced
it, end-to-end in the browser.
