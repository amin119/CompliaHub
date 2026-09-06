<div align="center">

# CompliaHub

**A GraphRAG + Agentic RAG platform for compliance intelligence — plus an
agentic codebase compliance scanner built on top of it.**

Answering relationship-heavy questions across ISO 42001, ISO 27001, and GDPR —
cross-standard mapping, gap analysis, multi-hop traversal — the kind of
questions plain vector search handles poorly. On top of that: upload a real
codebase and get evidence-based (never fabricated) compliance findings
mapped to those same standards, with AI-assisted validation, human review,
printable reports, and AI-suggested code fixes.

[![CI](https://github.com/amin119/Complia/actions/workflows/ci.yml/badge.svg)](https://github.com/amin119/Complia/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.12%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-000000?logo=nextdotjs&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?logo=postgresql&logoColor=white)
![Neo4j](https://img.shields.io/badge/Neo4j-018BFF?logo=neo4j&logoColor=white)
![Qdrant](https://img.shields.io/badge/Qdrant-DC244C?logo=qdrant&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)
![Status](https://img.shields.io/badge/status-feature%20complete-brightgreen)

[Roadmap](GraphRAG-Agentic-RAG-Roadmap.md) · [Phase docs](docs/README.md) · [Getting started](#getting-started)

</div>

---

> [!IMPORTANT]
> This is a learning project: the goal is to understand every layer of the
> architecture deeply, not just ship a working system. Each roadmap phase has
> a companion doc in [`docs/`](docs/README.md), written *before* that phase is
> built and updated in place afterward with what was actually shipped, the
> decisions made, and the gotchas hit.
>
> Internally the codebase and phase docs still refer to the platform by its
> original engineering name, **ComplianceGraph** — "CompliaHub" is the
> product's shipped, user-facing brand (see the frontend). Both names refer
> to the same project.

## Table of contents

- [Core use cases](#core-use-cases)
- [Compliance Scanner](#compliance-scanner)
- [Architecture](#architecture)
- [Tech stack](#tech-stack)
- [Frontend](#frontend)
- [Repo structure](#repo-structure)
- [Project status](#project-status)
- [Getting started](#getting-started)
- [Known environment gotcha (Windows)](#known-environment-gotcha-windows)

## Core use cases

1. *"What controls satisfy GDPR Article 32?"* — cross-standard mapping
2. *"What does ISO 42001 require that ISO 27001 doesn't cover?"* — gap analysis
3. *"Show me everything related to data retention across all three standards."* — multi-hop graph traversal
4. *"What evidence do I need for control A.8.1?"* — audit prep
5. *"If I change this policy, what's affected downstream?"* — impact analysis

**Non-goals (v1):** multi-tenant SaaS, real-time collaborative editing,
non-English documents, arbitrary file types beyond PDF/DOCX.

## Compliance Scanner

A second, standalone initiative built on top of the same platform (see
[docs/README.md](docs/README.md) for its own 9-phase build log): upload a
repository as a `.zip`, and it's scanned for real, technical compliance
evidence — **never a bare "compliant"/"non-compliant" verdict**, always
grounded in a 6-value evidence vocabulary
(`VERIFIED`/`PARTIALLY_VERIFIED`/`NOT_VERIFIED`/`POTENTIAL_NON_COMPLIANCE`/
`NOT_APPLICABLE`/`REQUIRES_HUMAN_REVIEW`) — where only a human review can
ever assert a positive `VERIFIED`/`PARTIALLY_VERIFIED` result, never
automation on its own.

- **Deterministic rule engines** (stdlib `ast`/`re`, zero LLM calls) for
  security findings (secrets, weak crypto, hardcoded credentials, insecure
  config), GDPR-relevant patterns, and AI/ML-governance signals (ISO 42001).
- **ISO 27001 control mapping** — findings from every rule pass mapped onto
  real Annex A 2022 control IDs (public control names only — no licensed
  normative text is stored or reproduced).
- **Agentic RAG validation** — an LLM agent grounds each finding against the
  real ingested standards text via the platform's own retrieval pipeline,
  producing a reasoned relevance/true-positive verdict — it can never change
  a finding's status itself.
- **Human review** — the only mechanism that can mark a finding
  `VERIFIED`/`PARTIALLY_VERIFIED`/`NOT_APPLICABLE`, with a mandatory
  justification and a full audit trail.
- **Reports** — a printable, per-scan HTML evidence report (severity/status/
  framework breakdowns, review coverage) — deliberately no aggregate score
  or percentage anywhere, by design.
- **Auto remediation** — an AI agent suggests a concrete unified-diff code
  fix for a finding's flagged location, grounded in the real file content —
  always a copy-paste artifact for a human to review, never auto-applied.

## Architecture

```
                          ┌─────────────────────────┐
                          │   Next.js Frontend       │
                          │  (chat + scanner UI)     │
                          └────────────┬─────────────┘
                                       │ REST/SSE
                          ┌────────────▼─────────────┐
                          │   FastAPI Backend         │
                          │  (API, orchestrator)      │
                          └────────────┬─────────────┘
                                       │
                 ┌─────────────────────┼─────────────────────┐
                 │                     │                     │
        ┌────────▼────────┐  ┌─────────▼─────────┐  ┌────────▼──────┐
        │  Query Router     │  │  Agentic Loop      │  │  Ingestion   │
        │  (classifier)     │  │  (LangGraph)       │  │  Pipeline    │
        └────────┬─────────┘  └─────────┬──────────┘  └────────┬──────┘
                 │                     │                     │
        ┌────────▼─────────────────────▼─────────────────────▼────────┐
        │                       Retrieval Layer                        │
        │   Vector Search (Qdrant)   |   Graph Traversal (Neo4j)        │
        └────────┬─────────────────────┬─────────────────────┬────────┘
                 │                     │                     │
        ┌────────▼────────┐  ┌─────────▼─────────┐  ┌────────▼────────┐
        │   Postgres        │  │   Redis            │  │  Object Storage │
        │ (metadata, jobs)  │  │ (cache, queues,     │  │ (raw docs, MinIO)│
        │                   │  │  rate limiting)     │  │                 │
        └───────────────────┘  └────────────────────┘  └─────────────────┘
```

The Compliance Scanner reuses this same backend/retrieval/storage stack —
its rule engines, ISO 27001 mapping, validation/remediation agents, and
reporting all live alongside the query platform's own services and share
the same Postgres/Redis/MinIO infrastructure, with their own dedicated
tables and Celery queues (`scanner`, `eval`).

Every layer is designed to be independently swappable and independently
testable — the extraction layer can be unit-tested without the agent, the
agent can be tested with mocked retrieval, and so on.

## Tech stack

| Layer | Choice |
|---|---|
| Backend API | FastAPI (Python, `uv`-managed) |
| Frontend | Next.js 16 / React 19 (TypeScript, App Router, Tailwind v4, `pnpm`) |
| Relational DB | PostgreSQL (metadata, job state, provenance; `ltree` for clause hierarchy) |
| Vector DB | Qdrant |
| Graph DB | Neo4j |
| Cache / queue | Redis + Celery |
| Object storage | MinIO (S3-compatible) |
| Document parsing | Docling (structure-aware PDF/DOCX) |
| Embeddings | Voyage (`voyage-law-2`) |
| Reranking | Cohere Rerank (`rerank-v3.5`) |
| Answer generation | Google Gemini (`gemini-3.1-flash-lite`, streaming) |
| Entity/relation extraction | Google Gemini (`gemini-3.1-flash-lite`, free tier) |
| Community detection | `python-igraph` + `leidenalg` (Leiden algorithm) |
| Agent orchestration | LangGraph (query classifier + plan/retrieve/critique/rewrite loop) |
| Evaluation | Custom Gemini-based LLM-judge harness (faithfulness/answer relevance/context precision/context recall) — not the `ragas` package, a deliberate choice; see [docs/phase-7-evaluation.md](docs/phase-7-evaluation.md) |
| Observability | stdlib `logging` + JSON formatter + correlation IDs (no Langfuse/`structlog`) |
| Security basics | Opt-in API-key auth + Redis-backed rate limiting on `/query` |
| Scanner rule engines | stdlib `ast`/`re` (zero LLM calls — security, GDPR, AI-governance findings) |
| Scanner AI agents | Google Gemini (finding validation, code-fix remediation) |

## Frontend

Two front-of-house areas sharing one unified design system (see
`frontend/DESIGN-SYSTEM.md`): a marketing landing page (`/`, GSAP + Lenis
scroll-driven), and the app itself (`/chat`, `/documents`, `/scanner`,
`/scanner/[scanId]`, `/scanner/[scanId]/report`) — a real-time streaming
chat UI with citation chips and an interactive force-directed evidence
graph, a document-upload/ingestion-status view, and the full Compliance
Scanner UI (findings browser, AI validate/remediate actions, human review
form, printable report). Light/dark theme via a `data-theme` DOM attribute
(not just OS preference), with a real toggle, `prefers-reduced-motion`
support throughout, and print-specific styling for the scan report.

## Repo structure

```
├── backend/              FastAPI app, Celery workers, Alembic migrations
│   └── scripts/           One-off ops scripts (eval question generation, ingestion load test)
├── frontend/              Next.js app — landing page + chat/documents/scanner UI
├── docs/                  Per-phase write-ups: plan before building, updated in place after
│                          (Part 1: platform roadmap · Part 2: compliance scanner roadmap)
├── docker-compose.yml     Local dev stack: postgres, redis, neo4j, qdrant, minio, 3 Celery workers
└── GraphRAG-Agentic-RAG-Roadmap.md   Full project roadmap
```

## Project status

**Feature-complete**: all 9 phases of the platform roadmap (Part 1) and all
9 phases of the Compliance Scanner roadmap (Part 2) are done and
live-verified against the real running stack. See
[docs/README.md](docs/README.md) for the full phase-by-phase build log for
both.

| Phase | Status | Details |
|---|---|---|
| 0 — Environment & repo setup | ✅ Done | [docs/phase-0-setup.md](docs/phase-0-setup.md) |
| 1 — Document ingestion pipeline | ✅ Done | [docs/phase-1-ingestion.md](docs/phase-1-ingestion.md) |
| 2 — Vector layer | ✅ Done | [docs/phase-2-vector-layer.md](docs/phase-2-vector-layer.md) |
| 3 — Entity & relation extraction | ✅ Done | [docs/phase-3-extraction.md](docs/phase-3-extraction.md) |
| 4 — Graph retrieval | ✅ Done | [docs/phase-4-graph-retrieval.md](docs/phase-4-graph-retrieval.md) |
| 5 — Agentic orchestration | ✅ Done | [docs/phase-5-agentic-loop.md](docs/phase-5-agentic-loop.md) |
| 6 — Frontend | ✅ Done | [docs/phase-6-frontend.md](docs/phase-6-frontend.md) |
| 7 — Evaluation harness | ✅ Done | [docs/phase-7-evaluation.md](docs/phase-7-evaluation.md) |
| 8 — Scaling & hardening (final platform phase) | ✅ Done | [docs/phase-8-scaling.md](docs/phase-8-scaling.md) |

Plus the Compliance Scanner's own 9 phases (1 — Foundation through
9 — Auto Remediation), all done — see the "Part 2" table in
[docs/README.md](docs/README.md).

## Getting started

### 1. Local data stack

```bash
cp .env.example .env
docker compose up -d --build
docker compose ps          # wait for all services to show "healthy"
```

This brings up Postgres, Redis, Neo4j, Qdrant, MinIO, and the three
role-scoped Celery workers (`worker-ingestion`, `worker-vector`,
`worker-graph` — see [docs/phase-1-ingestion.md](docs/phase-1-ingestion.md)
for why it's split this way; the scanner's own tasks run on
`worker-ingestion`/`worker-vector` too, on their own `scanner`/`eval`
queues). See [docs/phase-0-setup.md](docs/phase-0-setup.md) for per-service
smoke tests and port reference.

### 2. Backend

```bash
cd backend
cp .env.example .env
uv sync --all-extras   # host dev needs every worker's deps (docling, google-genai, igraph) to run the full test suite
uv run alembic upgrade head   # creates tables + the ltree extension
uv run uvicorn app.main:app --reload --port 8000
```

| Endpoint | Purpose |
|---|---|
| `GET /health`, `GET /health/deep` | Liveness / per-service connectivity check |
| `POST /documents` | Upload a PDF/DOCX for ingestion |
| `GET /documents/{id}`, `GET /documents/{id}/chunks` | Check status and inspect results |
| `DELETE /documents/{id}` | Remove a document and rebuild the entity graph from what remains |
| `POST /query` | Ask a question — classified and routed to vector/graph/agent retrieval, optionally continuing a `conversation_id` |
| `POST /query/stream` | Same as `POST /query`, but Server-Sent Events — status updates plus real answer tokens as they're generated |
| `GET /query/conversations/{id}`, `DELETE /query/conversations/{id}` | Inspect or forget a multi-turn agent conversation |
| `POST /scans` | Upload a repository `.zip` to the Compliance Scanner |
| `GET /scans/{id}/findings`, `.../findings/{id}/validate`, `.../findings/{id}/remediate`, `.../findings/{id}/reviews`, `GET /scans/{id}/summary` | Scanner findings, AI validation/remediation, human review, printable-report data — see the `scanner-phase-*` docs for the full endpoint set |
| `POST /eval/runs`, `GET /eval/runs/{id}` | Run the evaluation harness against a reviewed question set (dev-facing, no frontend) |
| `http://localhost:8000/docs` | Interactive Swagger UI — the authoritative full endpoint list |

Two opt-in Phase 8 settings, both real no-ops until set:
`PLATFORM_API_KEY` (gates `POST /documents`, `DELETE /documents/{id}`,
`POST /graph/communities/detect`) and `QUERY_RATE_LIMIT_PER_MINUTE`
(defaults to 20, enforced on `/query`/`/query/stream`).

### 3. Frontend

```bash
cd frontend
cp .env.local.example .env.local
pnpm install
pnpm dev   # http://localhost:3000
```

### Tests

```bash
cd backend
uv run ruff check .
uv run pytest
```

Some tests require the docker stack from step 1 to be running (they skip
cleanly if it isn't) — see [docs/phase-1-ingestion.md](docs/phase-1-ingestion.md#gotchas-worth-remembering).

```bash
cd frontend
pnpm lint
pnpm exec playwright test   # NOT `npx playwright test` — see playwright.config.ts's own comment for why
```

## Known environment gotcha (Windows)

> [!WARNING]
> The Python interpreter `uv` installs by default for this project can crash
> on real TLS calls on Windows (`OPENSSL_Uplink: no OPENSSL_Applink`). The
> backend is pinned to a python.org-installed CPython instead
> (`requires-python = ">=3.12"` in `backend/pyproject.toml`) to avoid this —
> see [docs/phase-0-setup.md](docs/phase-0-setup.md#gotcha-worth-knowing-windows--openssl-crash)
> for the full story before changing the Python version.
