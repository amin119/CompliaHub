<div align="center">

# ComplianceHub

**A GraphRAG + Agentic RAG platform for compliance intelligence.**

Answering relationship-heavy questions across ISO 42001, ISO 27001, and GDPR —
cross-standard mapping, gap analysis, multi-hop traversal — the kind of
questions plain vector search handles poorly.

[![CI](https://github.com/amin119/Complia/actions/workflows/ci.yml/badge.svg)](https://github.com/amin119/Complia/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.12%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-000000?logo=nextdotjs&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?logo=postgresql&logoColor=white)
![Neo4j](https://img.shields.io/badge/Neo4j-018BFF?logo=neo4j&logoColor=white)
![Qdrant](https://img.shields.io/badge/Qdrant-DC244C?logo=qdrant&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)
![Status](https://img.shields.io/badge/status-active%20development-yellow)

[Roadmap](GraphRAG-Agentic-RAG-Roadmap.md) · [Phase docs](docs/README.md) · [Getting started](#getting-started)

</div>

---

> [!IMPORTANT]
> This is a learning project: the goal is to understand every layer of the
> architecture deeply, not just ship a working system. Each roadmap phase has
> a companion doc in [`docs/`](docs/README.md), written *before* that phase is
> built and updated in place afterward with what was actually shipped, the
> decisions made, and the gotchas hit.

## Table of contents

- [Core use cases](#core-use-cases)
- [Architecture](#architecture)
- [Tech stack](#tech-stack)
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

## Architecture

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
        │ (metadata, jobs)  │  │ (cache, queues)     │  │ (raw docs, MinIO)│
        └───────────────────┘  └────────────────────┘  └─────────────────┘
```

Every layer is designed to be independently swappable and independently
testable — the extraction layer can be unit-tested without the agent, the
agent can be tested with mocked retrieval, and so on.

## Tech stack

| Layer | Choice |
|---|---|
| Backend API | FastAPI (Python, `uv`-managed) |
| Frontend | Next.js (TypeScript, App Router, Tailwind, `pnpm`) |
| Relational DB | PostgreSQL (metadata, job state, provenance; `ltree` for clause hierarchy) |
| Vector DB | Qdrant |
| Graph DB | Neo4j |
| Cache / queue | Redis + Celery |
| Object storage | MinIO (S3-compatible) |
| Document parsing | Docling (structure-aware PDF/DOCX) |
| Embeddings | Voyage (`voyage-law-2`) |
| Reranking | Cohere Rerank (`rerank-v3.5`) |
| Answer generation | Grok (xAI), via the OpenAI-compatible SDK |
| Agent orchestration | LangGraph *(Phase 5)* |
| Evaluation | RAGAS *(Phase 7)* |

## Repo structure

```
├── backend/            FastAPI app, Celery ingestion worker, Alembic migrations
├── frontend/            Next.js chat UI
├── ingestion/            (reserved — currently folded into backend/app/services + tasks)
├── docs/                 Per-phase write-ups: plan before building, updated in place after
├── docker-compose.yml    Local dev stack: postgres, redis, neo4j, qdrant, minio, worker
└── GraphRAG-Agentic-RAG-Roadmap.md   Full project roadmap
```

## Project status

| Phase | Status | Details |
|---|---|---|
| 0 — Environment & repo setup | ✅ Done | [docs/phase-0-setup.md](docs/phase-0-setup.md) |
| 1 — Document ingestion pipeline | ✅ Done | [docs/phase-1-ingestion.md](docs/phase-1-ingestion.md) |
| 2 — Vector layer | ✅ Done | [docs/phase-2-vector-layer.md](docs/phase-2-vector-layer.md) |
| 3 — Entity & relation extraction | 🔜 Planned | [docs/phase-3-extraction.md](docs/phase-3-extraction.md) |
| 4 — Graph retrieval | 🔜 Planned | [docs/phase-4-graph-retrieval.md](docs/phase-4-graph-retrieval.md) |
| 5 — Agentic orchestration | 🔜 Planned | [docs/phase-5-agentic-loop.md](docs/phase-5-agentic-loop.md) |
| 6 — Frontend | 🔜 Planned | [docs/phase-6-frontend.md](docs/phase-6-frontend.md) |
| 7 — Evaluation harness | 🔜 Planned | [docs/phase-7-evaluation.md](docs/phase-7-evaluation.md) |
| 8 — Scaling & hardening | 🔜 Planned | [docs/phase-8-scaling.md](docs/phase-8-scaling.md) |

See [docs/README.md](docs/README.md) for how these are written and kept up to date.

## Getting started

### 1. Local data stack

```bash
cp .env.example .env
docker compose up -d --build
docker compose ps          # wait for all services to show "healthy"
```

This brings up Postgres, Redis, Neo4j, Qdrant, MinIO, and the Celery
ingestion worker. See [docs/phase-0-setup.md](docs/phase-0-setup.md) for
per-service smoke tests and port reference.

### 2. Backend

```bash
cd backend
cp .env.example .env
uv sync
uv run alembic upgrade head   # creates tables + the ltree extension
uv run uvicorn app.main:app --reload --port 8000
```

| Endpoint | Purpose |
|---|---|
| `GET /health`, `GET /health/deep` | Liveness / per-service connectivity check |
| `POST /documents` | Upload a PDF/DOCX for ingestion |
| `GET /documents/{id}`, `GET /documents/{id}/chunks` | Check status and inspect results |
| `POST /query` | Ask a question over ingested documents |
| `http://localhost:8000/docs` | Interactive Swagger UI |

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

## Known environment gotcha (Windows)

> [!WARNING]
> The Python interpreter `uv` installs by default for this project can crash
> on real TLS calls on Windows (`OPENSSL_Uplink: no OPENSSL_Applink`). The
> backend is pinned to a python.org-installed CPython instead
> (`requires-python = ">=3.12"` in `backend/pyproject.toml`) to avoid this —
> see [docs/phase-0-setup.md](docs/phase-0-setup.md#gotcha-worth-knowing-windows--openssl-crash)
> for the full story before changing the Python version.
