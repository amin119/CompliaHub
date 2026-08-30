# Compliance Scanner — Phase 1: Scanner Foundation

This doc covers **Part 2 of the platform** — the Compliance Codebase
Scanner & Agentic Audit Engine — which is a separate axis of phases from
the core platform's own roadmap (`docs/phase-0-setup.md` through
`docs/phase-8-scaling.md`). Deliberately named `scanner-phase-N-*.md`, not
`phase-N-*.md`, to avoid colliding with that numbering.

The scanner's own spec breaks its work into 9 phases (Scanner Foundation →
Deterministic Security Scanner → GDPR Analyzer → AI/ISO 42001 Analyzer →
ISO 27001 Mapping → Agentic RAG → Human Review → Reports → Auto
Remediation). This doc covers **Phase 1 only**.

## Goal

Analyze an uploaded repository and produce an evidence inventory —
detected languages, frameworks, and a per-file classification — without
making any compliance claim. This is deliberately the *foundation*, not
the scanner: no security/privacy/AI-governance analysis, no framework
mapping, no LLM reasoning happens yet. Everything here is pure,
deterministic classification (extension/filename matching), consistent
with the scanner spec's own "deterministic analysis first" principle and
"never send a whole repo to an LLM" principle — Phase 1 introduces **zero
new LLM calls**.

## What was built

Reuses the platform's existing ingestion-pipeline shape end to end
(upload → hash-dedup → MinIO → DB row → Celery chain → poll-until-terminal)
for a new `Scan`/`RepositoryFile` entity pair, the same shape
`documents.py`/`tasks/pipeline.py`/`models/document.py` already implement
for standards documents.

**Models** (`app/models/scan.py`): `Scan` (mirrors `Document`),
`RepositoryFile` (mirrors `Chunk`), `ScanProcessingJob` (mirrors
`ProcessingJob`), `Evidence` (the scanner spec's normalized evidence
schema — defined now, unpopulated until Phase 2+ analyzers exist).
Deliberately **no `Repository` model yet** — `Scan.repository_name` is a
free-text label, not a foreign key; a persistent Repository entity
(tracked branch/URL, diffed across scans) only makes sense once
git-connect ingestion exists, a later phase.

**Discovery/classification** (`app/services/repo_discovery.py`,
`app/services/repo_extraction.py`) — both pure functions, no DB/MinIO, no
LLM:
- `iter_zip_entries` — safe in-memory zip extraction: rejects zip-slip
  paths and absolute/drive-letter paths before trusting any entry name,
  enforces file-count and total-declared-size caps up front (from the
  zip's central directory, before decompressing anything — a real
  zip-bomb defense), and skips (doesn't error on) any single file over a
  per-file size cap.
- `classify_file` — language from an extension map; `component_type` from
  well-known filenames (`Dockerfile`, `package.json`, ...) checked before
  falling back to extension-based `application_code`; a null-byte-in-the-
  first-N-bytes heuristic flags binaries (no `python-magic`/libmagic
  dependency needed).
- `detect_frameworks` — simple substring/JSON-key checks against only the
  small set of files already classified as manifests/CI/infra config
  during the walk, never the whole repository.

**Pipeline** (`app/tasks/scan_pipeline.py`, `app/tasks/scan.py`):
`scan_stage` is a new sibling to `tasks/pipeline.py`'s `pipeline_stage` —
same open-session/load-row/create-job/commit-or-fail shape, applied to
`Scan`/`ScanProcessingJob`. Deliberately a new module, not a generalized
one: this project already treats structurally-identical-but-distinct
concerns this way (see `query_classifier.py`'s comment on why its adapter
isn't code-shared with `extraction.py`'s despite an identical shape).
Two Celery tasks, chained: `extract_and_classify_files_task` (fetch the
archive, classify every entry, upload non-ignored/non-binary content,
clear-then-rebuild `RepositoryFile` rows for idempotent reruns — same
pattern `chunk_document_task` uses) then `detect_frameworks_task` (reads
back only the manifest-classified files, sets `detected_languages`/
`detected_frameworks`, marks the scan `ready`).

**Queue**: no new worker container, no new `pyproject.toml` extra — Phase
1's own dependencies are stdlib-only (`zipfile`, `pathlib`, `hashlib`).
Added a `"scanner"` queue in `celery_app.py`'s `task_routes` and extended
the existing `worker-ingestion` service (`docker-compose.yml`) to also
consume it (`-Q ingestion,scanner -I app.tasks.ingestion,app.tasks.scan`)
— its own queue name now costs nothing and leaves room for a dedicated
worker once a later phase adds heavier AST/tree-sitter dependencies.

**API** (`app/api/routes/scans.py`): `POST /scans` (zip upload, hash-dedup
idempotency, kicks off the chain), `GET /scans` (list, newest first — a
capability `documents.py` explicitly lacks and calls out as a known gap;
adding it here serves Phase 1's "basic dashboard" requirement directly),
`GET /scans/{id}`, `GET /scans/{id}/files` (optional
`?component_type=` filter).

**Frontend**: `frontend/src/lib/api.ts` gained `ScanStatus`/`RepositoryFile`
types + `uploadScan`/`getScan`/`listScans`/`getScanFiles`. New
`/scanner` page (upload + poll + scan history, using the now-real
`listScans()` unlike `/documents`' session-only list) and
`/scanner/[scanId]` (the "basic dashboard": detected languages/frameworks
as chips, a filterable file-classification table). `StatusBadge` was
extracted out of `documents/page.tsx`'s inline copy into
`components/StatusBadge.tsx` so both pages share it. Both new pages follow
`DESIGN-SYSTEM.md`'s existing tokens.

## Two real bugs found and fixed during verification

1. `extract_and_classify_files_task` originally returned `None`, but the
   Celery chain also passed `detect_frameworks_task.s(str(scan.id))`
   explicitly — Celery always feeds a chained task's return value as the
   *next* task's first positional argument, so `detect_frameworks_task`
   was being called with **two** positional arguments (`None` from the
   previous task, plus the explicit `scan_id`) against a one-parameter
   function signature: `TypeError: detect_frameworks_task() takes 1
   positional argument but 2 were given`. Caught by the very first real
   test run, not assumed correct from reading the code. Fixed the same
   way `parse_document_task`/`chunk_document_task` already handle this:
   the upstream task now returns `scan_id` unchanged, and the chain call
   was changed to `detect_frameworks_task.s()` (no explicit arg) so the
   value threads through the chain instead of being passed twice.
2. `classify_file`'s path-substring matching (`/docs/`, `/tests/`,
   `/migrations/`, ...) only matched a *nested* occurrence of the
   directory — a file directly at the repository root (`docs/x.md`,
   `tests/test_foo.py`) has no leading `/` before the directory name, so
   it silently fell through to `unknown`/`application_code` instead of
   `documentation`/`test_code`. Caught live: a real upload classified a
   top-level `README.md` as `unknown`. Fixed by matching against the path
   with a leading `/` prepended (`"/" + normalized`), so a root-level
   directory matches the same way a nested one already did. Also added
   `README`/`README.md`/`CHANGELOG.md` to the filename map directly
   (documentation), since a repo's own README shouldn't depend on the
   substring match at all.

## Explicitly out of scope for Phase 1

Static security analysis (secrets/deps/IaC rules) — Phase 2. GDPR analyzer
— Phase 3. AI/ISO 42001 analyzer — Phase 4. ISO 27001 mapping — Phase 5.
Agentic RAG / any LLM reasoning over scan data — Phase 6. Human review —
Phase 7. Reports — Phase 8. Auto remediation — Phase 9. AST/tree-sitter
analysis. Git-clone/local-path ingestion and a `Repository` model.
Populated `Evidence` rows (table exists, nothing writes to it yet).
Pagination/auth/multi-tenant scoping on scan endpoints.

**A CLI wrapper was discussed and deliberately deferred, not rejected.**
The user asked whether the scanner should be a CLI tool instead of a web
upload. Recommendation given (not yet built): don't replace the web flow —
a CLI can't do anything past Phase 1 standalone anyway, since the real
compliance reasoning (Phases 2-9) needs the live backend (Postgres/Neo4j/
Qdrant/the Agentic RAG loop). The highest-leverage version is a *thin*
wrapper, built later, that zips a local directory (respecting
`.gitignore`, an improvement over the current "zip it yourself" UX) and
calls this same `POST /scans` endpoint — genuinely useful for CI
integration, but additive, not a Phase 1 requirement.

## Verification

- **Unit tests** (new, all passing): `tests/test_repo_discovery.py` (14
  cases — classification, ignore-list filtering, framework detection),
  `tests/test_repo_extraction.py` (8 cases — zip-slip rejection, size/
  count-cap rejection, per-file skip, normal extraction), analog
  `tests/test_scan_pipeline.py` (3 cases, mirroring
  `test_pipeline_stage.py`), `tests/test_scans_api.py` (7 cases —
  end-to-end upload/classify/detect, idempotent re-upload, list endpoint,
  rerun-doesn't-duplicate, component-type filtering, 404, empty-file
  rejection).
- **Full backend suite re-run after adding these**: 150 passed (up from
  118) before the README-classification fix; 33/33 scanner-specific tests
  re-confirmed passing after it (full-suite re-run not repeated a second
  time for that one small fix — covered directly by
  `test_classifies_readme_as_documentation` and the existing integration
  tests, none of which touch unrelated code paths).
- **Live end-to-end — confirmed working against the real stack.** Built a
  real multi-language sample repository as a zip (a Python file importing
  FastAPI, a `package.json` with `next`/`react`, a `requirements.txt` with
  `fastapi`, a `Dockerfile`, a GitHub Actions workflow, a `node_modules/`
  directory to prove ignore-list filtering, a README, later a top-level
  `docs/architecture.md`) and uploaded it via a real
  `curl -F file=@sample-repo.zip` call against the real running API (real
  Postgres/Redis/MinIO, no mocks). Confirmed via `GET /scans/{id}`:
  `status: "ready"`, `file_count: 6` (the 7th entry, `node_modules/lodash/
  index.js`, correctly excluded), `detected_languages: ["python"]`,
  `detected_frameworks: ["docker", "fastapi", "github-actions", "next.js",
  "react"]`. `GET /scans/{id}/files` confirmed correct per-file
  classification (`.github/workflows/ci.yml` → `ci_cd_config`,
  `Dockerfile` → `infrastructure_as_code`, `package.json`/
  `requirements.txt` → `dependency_manifest`, `src/app/main.py` →
  python/`application_code`) and the `?component_type=` filter returning
  exactly the two manifest files.
- **A real environment gotcha hit and worked around, not glossed over**:
  editing `docker-compose.yml`'s `worker-ingestion` command (to add the
  `scanner` queue/task module) has no effect on an already-running
  container until it's rebuilt — the worker's code is baked into its
  image at build time, there's no source volume mount. The first upload
  sat at `status: "pending"` forever because the running container was
  still the old image. `docker compose build worker-ingestion` was
  attempted to pick up the change, but failed twice on this environment's
  network dropping mid-download of Docling's very large `torch` dependency
  (a pre-existing, unrelated-to-this-work slow/flaky rebuild problem this
  project has hit before — see the worker-split history in
  `docs/phase-1-ingestion.md`). Rather than keep retrying an unreliable
  multi-gigabyte rebuild just to verify Phase 1's own code (which has zero
  new dependencies), verification instead ran a Celery worker for the
  `scanner` queue directly on the host — `uv run celery -A
  app.tasks.celery_app worker -Q scanner -I app.tasks.scan --pool=solo`
  (`--pool=solo` because Celery's default prefork pool needs `os.fork`,
  unavailable on native Windows — the same reason this project's workers
  are normally containerized at all). This verifies the actual pipeline
  logic correctly; the docker image still needs a successful rebuild
  before this queue is served in the normal containerized deployment, and
  that rebuild should be retried when the network is stable — flagged as
  a known follow-up, not silently left broken.
