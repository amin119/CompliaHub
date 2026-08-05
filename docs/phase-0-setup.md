# Phase 0 — Environment & Repo Setup

Status: done. This covers the local dev stack, backend/frontend skeletons, config
management, and CI set up before any real feature work (see the top-level
`GraphRAG-Agentic-RAG-Roadmap.md` for the full phase-by-phase plan).

## What exists

```
├── docker-compose.yml + .env.example   # local data stack
├── backend/                            # FastAPI
│   ├── app/core/config.py              # pydantic-settings, typed config
│   ├── app/api/routes/health.py        # GET /health, GET /health/deep
│   ├── app/main.py                     # FastAPI app + CORS
│   ├── tests/test_health.py
│   └── .env.example / .env             # backend app config
├── frontend/                           # Next.js (TypeScript, App Router, Tailwind)
│   └── src/app/page.tsx                # chat placeholder UI
└── .github/workflows/ci.yml            # lint + test on push/PR
```

## Local data stack (`docker-compose.yml`)

| Service  | Image               | Ports (host)   | Role                                   |
|----------|---------------------|----------------|-----------------------------------------|
| postgres | postgres:16-alpine  | 5432           | Metadata, job state, provenance         |
| redis    | redis:7-alpine      | 6379           | Cache + future Celery broker            |
| neo4j    | neo4j:5-community   | 7474, 7687     | Knowledge graph (7474 UI, 7687 bolt)     |
| qdrant   | qdrant/qdrant       | 6333, 6334     | Vector store (6333 REST, 6334 gRPC)      |
| minio    | minio/minio         | 9000, 9001     | Raw document storage (9000 API, 9001 UI) |

Setup:
```
cp .env.example .env
docker compose up -d
docker compose ps          # wait for all 5 to show "healthy"
```

Per-service smoke tests:
```
curl http://localhost:6333/readyz              # Qdrant
curl http://localhost:7474                      # Neo4j (or open in a browser)
curl http://localhost:9000/minio/health/live     # MinIO
docker compose exec redis redis-cli ping         # PONG
docker compose exec postgres psql -U compliancegraph -d compliancegraph -c '\conninfo'
```

## Config management

Two separate `.env` layers, both gitignored (only `.env.example` files are committed):
- **Root `.env`** — credentials/ports for `docker-compose.yml` (the containers themselves).
- **`backend/.env`** — the FastAPI app's view of those same services (connection
  strings, not raw credentials), loaded via `app/core/config.py`'s `Settings`
  class (pydantic-settings).

`Settings` fields all have defaults matching `docker-compose.yml`'s dev
credentials, so the app and test suite work with **no `.env` file present at
all** — this is what makes CI and a fresh clone work without extra setup. A real
`.env` or real environment variables override these defaults for anything
other than local dev.

Frontend uses `frontend/.env.local` (see `.env.local.example`) for
`NEXT_PUBLIC_API_URL` — the only var it needs, since it doesn't talk to the
data stack directly.

## Backend (FastAPI)

- Entrypoint: `app/main.py` — `FastAPI()` instance, CORS open to
  `http://localhost:3000` (the Next.js dev server), health router included.
- `GET /health` — liveness only, no dependencies checked.
- `GET /health/deep` — pings Postgres, Redis, Neo4j, Qdrant, and MinIO each with
  their real client library, catching failures independently so one down
  service reports as `"degraded"` rather than 500ing the whole endpoint.
- Dev tooling: `ruff` (lint) and `pytest` + `httpx` (tests against
  `fastapi.testclient.TestClient`).

Run it:
```
cd backend
uv sync --all-extras   # host dev needs every worker's deps (docling, google-genai, igraph) for the full test suite
uv run uvicorn app.main:app --reload --port 8000
# http://localhost:8000/health
# http://localhost:8000/health/deep
```

Lint + test:
```
uv run ruff check .
uv run pytest
```

## Frontend (Next.js)

TypeScript, App Router, Tailwind, pnpm. `src/app/page.tsx` is a static chat
placeholder (message list + disabled input) — no backend wiring yet, that's
Phase 6.

```
cd frontend
pnpm dev       # http://localhost:3000
pnpm lint
pnpm build
```

## CI

`.github/workflows/ci.yml` runs two jobs on push/PR to `main`: `backend`
(`uv sync --all-extras`, `ruff check`, `pytest`) and `frontend` (`pnpm install`,
`pnpm lint`, `pnpm build`). Both run on `ubuntu-latest`.

## Gotcha worth knowing: Windows + OpenSSL crash

The Python interpreter `uv` first installs by default (a portable
"python-build-standalone" build) had a Windows-only bug: any real TLS call —
even the stdlib's `ssl.create_default_context()` — crashed the whole process
with `OPENSSL_Uplink(...): no OPENSSL_Applink`. This wasn't specific to
Postgres or Qdrant; it would have broken every future HTTPS call (including
LLM API calls in later phases).

Fix: the project's venv now points at the python.org-installed CPython 3.12.2
instead (`backend/.python-version` = `3.12`, `requires-python = ">=3.12"` in
`pyproject.toml`). That build includes the `OPENSSL_Applink` shim and doesn't
have the issue. If you ever recreate the venv, make sure it's built against a
python.org (or otherwise non-python-build-standalone) interpreter, not
whatever `uv` downloads by default.

## Verification checklist

- [x] `docker compose up -d` → all 5 services healthy
- [x] `uv run ruff check .` / `uv run pytest` pass (with or without `backend/.env`)
- [x] `pnpm lint` / `pnpm build` pass
- [x] `/health` and `/health/deep` respond correctly with containers up
- [x] `pnpm dev` renders the chat placeholder at `localhost:3000`
