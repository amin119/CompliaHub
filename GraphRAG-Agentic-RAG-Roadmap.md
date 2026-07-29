# GraphRAG + Agentic RAG — Compliance Intelligence Platform
### Full Project Roadmap (ISO 42001 / ISO 27001 / GDPR)

> Goal: build a production-grade Graph RAG + Agentic RAG system over compliance/regulatory documents, learning every layer of the architecture along the way — ingestion, extraction, graph construction, retrieval, agent orchestration, and scaling.

---

## 0. Project Definition

**Working name:** ComplianceGraph (rename as you like)

**Problem statement:** Compliance teams need to answer relationship-heavy questions across ISO 42001, ISO 27001, and GDPR — cross-references, control mappings, gap analysis, audit evidence lookup — which plain vector search handles poorly.

**Core use cases to support:**
1. "What controls satisfy GDPR Article 32?" (cross-standard mapping)
2. "What does ISO 42001 require that ISO 27001 doesn't cover?" (gap analysis)
3. "Show me everything related to data retention across all three standards." (multi-hop graph traversal)
4. "What evidence do I need for control A.8.1?" (audit prep)
5. "If I change this policy, what's affected downstream?" (impact analysis)

**Non-goals (v1):** multi-tenant SaaS, real-time collaborative editing, non-English documents, arbitrary file types beyond PDF/DOCX text.

**Success criteria:**
- Correct multi-hop answers with citations back to exact clause/article
- Sub-5s response for simple queries, sub-30s for full agentic loop
- Incremental ingestion (add one new doc without reprocessing everything)
- You can explain every component from memory by the end

---

## 1. Learning Prerequisites (do these before/alongside building)

| Topic | Why | Resource type |
|---|---|---|
| Vector embeddings & similarity search | Foundation for retrieval | Any embeddings 101 |
| Knowledge graphs & graph databases (Neo4j / Cypher) | Core data model | Neo4j official docs/sandbox |
| Named Entity Recognition & Relation Extraction | How you build the graph from text | LLM-based extraction papers |
| Microsoft GraphRAG paper (Edge et al., 2024) | The reference architecture | arXiv paper + repo |
| LightRAG, RAPTOR, HippoRAG | Alternative graph-RAG designs | Papers/repos |
| LangGraph fundamentals | Agent orchestration | LangGraph docs |
| Async task queues (Celery/RQ) | Ingestion at scale | Docs + small demo project |
| RAGAS / retrieval evaluation | How to measure if it's actually good | RAGAS docs |

Don't binge all of this upfront — read each topic right before you build that layer (Section 3).

---

## 2. High-Level Architecture

```
                          ┌─────────────────────────┐
                          │   Next.js Frontend       │
                          │  (chat UI, graph viz)    │
                          └────────────┬─────────────┘
                                       │ REST/SSE
                          ┌────────────▼─────────────┐
                          │   FastAPI Backend         │
                          │  (API, auth, orchestrator)│
                          └────────────┬─────────────┘
                                       │
                 ┌─────────────────────┼─────────────────────┐
                 │                     │                     │
        ┌────────▼────────┐  ┌─────────▼─────────┐  ┌────────▼────────┐
        │  Query Router     │  │  Agentic Loop      │  │  Ingestion       │
        │  (classifier)     │  │  (LangGraph)       │  │  Pipeline        │
        └────────┬─────────┘  └─────────┬──────────┘  └────────┬────────┘
                 │                     │                     │
        ┌────────▼─────────────────────▼─────────────────────▼────────┐
        │                       Retrieval Layer                        │
        │   Vector Search (Qdrant)   |   Graph Traversal (Neo4j)        │
        └────────┬─────────────────────┬─────────────────────┬────────┘
                 │                     │                     │
        ┌────────▼────────┐  ┌─────────▼─────────┐  ┌────────▼────────┐
        │   Postgres        │  │   Redis            │  │  Object Storage │
        │ (metadata, jobs)  │  │ (cache, queues)     │  │ (raw docs, MinIO)│
        └───────────────────┘  └────────────────────┘  └─────────────────┘
```

**Design principle:** every layer is independently swappable and independently testable. You should be able to unit-test the extraction layer without the agent, and test the agent with mocked retrieval.

---

## 3. Phase-by-Phase Roadmap

### Phase 0 — Environment & Repo Setup (Week 1)
- [x] Monorepo structure: `/backend` (FastAPI), `/frontend` (Next.js), `/ingestion` (pipeline workers), `/docs`
- [x] Docker Compose with: Postgres, Redis, Neo4j, Qdrant, MinIO (all local, no cloud cost yet)
- [x] Basic FastAPI skeleton + health check endpoint
- [x] Basic Next.js skeleton with a chat placeholder page
- [x] `.env` config management, secrets handling
- [x] CI: lint + basic tests on push (GitHub Actions)

**Learning checkpoint:** you should understand your full local dev stack and be able to spin it up with one command (`docker compose up`).

---

### Phase 1 — Document Ingestion Pipeline (Weeks 2–3)
**Goal:** get ISO 42001, ISO 27001, GDPR text into structured, hierarchical chunks with clean metadata.

Steps:
1. **File intake** — upload endpoint → store raw file in MinIO, create a `documents` row in Postgres (id, filename, hash, status).
2. **Parsing** — PDF/DOCX → structured text. Use structure-aware parsing (headings, numbered clauses), not naive text dump. Preserve hierarchy: Standard → Part → Clause → Sub-clause → Control.
3. **Chunking strategy** — chunk at the clause/sub-clause boundary (not fixed token windows) since these documents have strict semantic structure. Store parent/child chunk relationships.
4. **Deduplication & idempotency** — hash-based check so re-uploading the same file doesn't reprocess it. This is your incremental-ingestion foundation — get it right now, not later.
5. **Job queue** — Celery + Redis worker to process documents asynchronously (parse → chunk → embed → extract, each a separate task, all resumable/retryable).
6. **Metadata schema in Postgres** — `documents`, `chunks`, `chunk_hierarchy`, `processing_jobs` tables.

**Learning checkpoint:** you understand why naive fixed-size chunking breaks structured legal/compliance text, and how async job queues make ingestion resumable and scalable.

---

### Phase 2 — Vector Layer (Week 4)
**Goal:** baseline vector RAG working end-to-end before adding graph complexity.

Steps:
1. Choose embedding model (start with a solid open one or an API-based one — cost/quality tradeoff).
2. Embed each chunk, store in Qdrant with metadata (source doc, clause number, hierarchy path).
3. Build hybrid search: dense (Qdrant) + BM25 (Postgres full-text or a lightweight lexical index), fused with Reciprocal Rank Fusion.
4. Add a cross-encoder reranker on top results.
5. Build a minimal `/query` endpoint that does hybrid search + reranking + LLM answer generation, no graph yet.
6. **Test this end-to-end with real questions** before moving on — this is your regression baseline for everything after.

**Learning checkpoint:** you can explain hybrid search, RRF fusion, and reranking, and you have a working (if limited) RAG system.

---

### Phase 3 — Entity & Relation Extraction (Weeks 5–6)
**Goal:** turn chunks into a knowledge graph.

Steps:
1. **Define the ontology first** (don't skip this):
   - Entity types: `Standard`, `Clause`, `Control`, `Requirement`, `Risk`, `Asset`, `Process`, `Role`, `Definition`
   - Relation types: `requires`, `references`, `implements`, `maps_to`, `is_prerequisite_for`, `applies_to`, `defined_in`, `part_of`, `superseded_by`
2. **Extraction prompting** — structured LLM prompt per chunk, forced JSON output (entities + relations found in that chunk). Validate output against a schema (Pydantic model) before accepting it.
3. **Batch processing** — this is the expensive step. Batch chunks, run extraction jobs asynchronously, cache results by chunk hash so you never re-extract unchanged text.
4. **Entity resolution / deduplication** — "personal data" mentioned in GDPR vs referenced in ISO 42001 should resolve to the same node. Use embedding similarity + exact-match rules for merging.
5. **Load into Neo4j** — write entities as nodes, relations as edges, with provenance (which chunk/document each fact came from).
6. **Community detection** — run the Leiden algorithm over the graph to build hierarchical clusters/communities, and generate LLM summaries per community (this is what makes "global" questions like gap analysis answerable — GraphRAG's key trick).

**Learning checkpoint:** you understand LLM-based structured extraction, entity resolution, and why community detection + summarization enables holistic/global queries that plain graph traversal can't.

---

### Phase 4 — Graph Retrieval (Week 7)
**Goal:** answer relationship queries via graph traversal.

Steps:
1. Build Cypher query templates for common patterns (multi-hop traversal, cross-standard mapping lookup, "what references X").
2. Build a local search mode (start from specific entities, traverse N hops) and a global search mode (query community summaries first, drill down).
3. Combine graph results + vector results into a single context for the LLM to answer from, with citations back to exact clause numbers.
4. Test on your 5 core use cases from Section 0.

**Learning checkpoint:** you understand local vs. global search in GraphRAG and can trace exactly which graph traversal produced which answer.

---

### Phase 5 — Agentic Orchestration Layer (Weeks 8–9)
**Goal:** add the reasoning loop instead of a single-shot retrieval call.

Steps:
1. Build a **query classifier**: simple factual → vector only; relational → graph; complex/multi-step → full agent loop. Start with a cheap few-shot LLM prompt classifier.
2. Build the LangGraph agent: nodes for `plan`, `retrieve` (vector or graph, agent decides), `critique` (is this enough evidence?), `rewrite_query`, `answer`, with conditional edges and a loop-back for insufficient evidence.
3. Add a **budget/stop condition** (max iterations, max tokens) so the agent doesn't loop forever.
4. Add checkpointing (LangGraph supports this) so long-running agent sessions are resumable/inspectable.
5. Wire the classifier as the entry point of your `/query` endpoint — this is your adaptive routing layer.

**Learning checkpoint:** you understand the difference between workflow RAG (fixed pipeline) and true agentic RAG (model decides retrieval actions), and why adaptive routing keeps costs sane.

---

### Phase 6 — Frontend (Weeks 9–10, parallel-able with Phase 5)
- [ ] Chat interface (streaming responses)
- [ ] Citation display (clickable references back to exact clause/article)
- [ ] Graph visualization panel (show the traversal path for a given answer — great for demoing and for debugging)
- [ ] Document upload UI wired to the ingestion pipeline
- [ ] Job status view (ingestion progress for uploaded docs)

---

### Phase 7 — Evaluation Harness (Week 11)
**Goal:** stop trusting your gut, start measuring.

Steps:
1. Build a test set: 30–50 real questions across your 5 use-case categories, with ground-truth answers/citations.
2. Integrate RAGAS or a custom eval: faithfulness, answer relevance, context precision/recall.
3. Track per-query: which path was taken (vector/graph/agentic), latency, cost, correctness.
4. Set up regression testing — re-run the eval set on every significant pipeline change.

**Learning checkpoint:** you can quantitatively say "this change improved retrieval quality by X%" instead of guessing.

---

### Phase 8 — Scaling & Hardening (Weeks 12+)
**Goal:** prove the "very very large number of files" claim, not just the small 3-standard corpus.

Steps:
1. **Incremental updates end-to-end** — add/update/delete a document without full reprocessing; propagate changes to graph and vector store correctly (including stale-edge cleanup).
2. **Load test ingestion** — feed a large synthetic/messy corpus (thousands of files) through the pipeline, measure throughput, find bottlenecks (usually LLM extraction calls — batch/parallelize/cache aggressively).
3. **Sharding/partitioning strategy** for the graph if it grows large (per-standard subgraphs, cross-standard edges as bridges).
4. **Observability** — structured logging + tracing across ingestion jobs and agent loops (reuse your Langfuse experience here).
5. **Cost controls** — cache LLM calls aggressively (extraction is idempotent per chunk-hash), track token spend per query type.
6. **Security/access control basics** — since this is compliance data, at least sketch role-based access even if not fully implemented.

**Learning checkpoint:** you understand the real bottlenecks of graph-RAG at scale (LLM extraction cost, incremental graph maintenance) and how production systems mitigate them.

---

## 4. Tech Stack Summary

| Layer | Choice | Why |
|---|---|---|
| Backend API | FastAPI | Consistent with your existing stack |
| Frontend | Next.js | Consistent with your existing stack |
| Relational DB | PostgreSQL | Metadata, job state, provenance |
| Vector DB | Qdrant | Scales better than pgvector past ~1M vectors |
| Graph DB | Neo4j | Best tooling/ecosystem for graph RAG |
| Cache/Queue | Redis (+ Celery) | Async ingestion, caching |
| Object storage | MinIO (S3-compatible) | Raw document storage |
| Agent orchestration | LangGraph | Stateful, cyclic, checkpointed agent loops |
| Eval | RAGAS | Standard retrieval/generation eval |
| Observability | Langfuse | You already have experience here |

---

## 5. Suggested Timeline

| Phase | Weeks | Deliverable |
|---|---|---|
| 0 — Setup | 1 | Working local dev stack |
| 1 — Ingestion | 2–3 | Docs parsed & chunked with hierarchy |
| 2 — Vector RAG | 4 | Working baseline RAG |
| 3 — Extraction | 5–6 | Populated knowledge graph |
| 4 — Graph retrieval | 7 | Relationship queries answerable |
| 5 — Agentic loop | 8–9 | Adaptive routing + agent reasoning |
| 6 — Frontend | 9–10 | Usable chat UI with citations |
| 7 — Evaluation | 11 | Quantified quality metrics |
| 8 — Scaling | 12+ | Proven incremental ingestion at scale |

~12+ weeks for a solid v1, longer if done alongside school/work (which it will be — pace it realistically).

---

## 6. Key Papers/References to Read Per Phase

- Phase 3–4: Microsoft **GraphRAG** (Edge et al., 2024), **RAPTOR** (Sarthi et al., 2024), **LightRAG** (Guo et al., 2025), **HippoRAG** (Gutiérrez et al., 2025)
- Phase 5: **Self-RAG** (Asai et al., 2023), **FLARE** (Jiang et al., 2023)
- General: Anthropic's Contextual Retrieval blog post (hybrid search rationale)

---

## 7. Next Immediate Actions
1. Set up Phase 0 (repo + Docker Compose)
2. Collect and organize your ISO 42001 / ISO 27001 / GDPR source documents
3. Draft the entity/relation ontology as a Pydantic schema (I can help write this next)
4. Start Phase 1 ingestion on a single document end-to-end before scaling to all three standards
