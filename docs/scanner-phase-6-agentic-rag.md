# Compliance Scanner — Phase 6: Agentic RAG

## Goal

Add an on-demand, LLM-based review layer on top of Phases 2-5's deterministic
findings — a `ComplianceRetriever` that grounds a finding in whatever standards
text the user has ingested via `/documents`, and a `FindingValidationAgent` that
judges whether a finding looks like a real issue or a rule misfire. The first
scanner phase to make any LLM/embedding call — every prior phase was strictly
deterministic, and every prior phase's docs explicitly reserved both of these
concepts for "Phase 6."

**The one non-negotiable constraint, restated from Phase 5**: this agent must
never claim `VERIFIED`/`PARTIALLY_VERIFIED`/`NOT_APPLICABLE` compliance status.
It only ever adds interpretive commentary to a finding — `Finding.status` is
never touched.

## What was built

**Two new service modules, reusing Part 1's existing Agentic RAG infrastructure
directly rather than building a second one:**

- `app/services/compliance_retrieval.py` — `ComplianceRetriever`. Deliberately
  a thin wrapper: `retrieve_context_for_finding(db, finding, top_k=5)` builds a
  query string from a Finding's own fields (`title`, humanized `category`,
  `framework`, `summary`, `reasoning` when distinct from summary —
  **deliberately never from `Evidence.snippet`**, since raw code excerpts could
  carry secrets/PII with no reason to leave this process just to embed a
  search query) and calls `retrieval.vector_search(db, query, top_k)` — the
  exact same dense+lexical+RRF-fusion+rerank function the platform's main
  chat feature (`/query`) already uses, over the same Qdrant `chunks`
  collection a user's ingested standards land in. Raises
  `NoStandardsContextError` on zero chunks (a fresh install with nothing
  ingested is the common case, not a bug) — never lets the LLM improvise from
  empty context.
- `app/services/finding_validation.py` — `FindingValidationAgent`. Mirrors
  `query_classifier.py`'s Protocol+adapter+structured-output+retry pattern
  exactly: `FindingValidationVerdict` (Pydantic model with
  `context_relationship`/`finding_assessment`/`confidence`/`rationale`),
  `_GeminiValidationClient` (forced JSON schema, re-validated via
  `model_validate_json`), `validate_finding(finding, context_chunks,
  client=None)` with the same 3-retry exponential-backoff loop as
  `classify_query`. `persist_verdict(...)` writes the result as a new
  `Evidence(source_type="llm_reasoning", ...)` row — **the already-reserved
  value that had been sitting unused in the model's own comment since Phase
  1/2** — no schema change, no migration.

**Verdict vocabulary — the one product/trust decision, resolved by the user
via `AskUserQuestion` before implementation** (same pattern as Phase 5's
licensing question): a two-axis structured verdict rather than free text or a
single true/false-positive flag —

```python
context_relationship: "supports_concern" | "contradicts_concern" | "not_addressed"
finding_assessment: "likely_true_positive" | "likely_false_positive" | "insufficient_evidence"
confidence: "high" | "medium" | "low"
rationale: str
```

Forces the model to ground its true/false-positive call in what it actually
retrieved rather than letting retrieval be decorative. The system prompt
explicitly forbids the words "compliant"/"non-compliant"/"verified"/
"certified" and frames `insufficient_evidence`/`not_addressed` as legitimate,
common, correct-default answers — not failures.

**API — two new synchronous endpoints on `app/api/routes/scans.py`, zero new
Celery infrastructure**: `POST /scans/{id}/findings/{id}/validate` (404 if
finding missing, 422 if `NoStandardsContextError`, 503 if the LLM call fails
after retries) and a capped, sequential `POST
/scans/{id}/findings/validate-bulk` (`_MAX_BULK_FINDINGS = 10`, partial
success per item — one bad id never loses the others' results; backend-only
this phase, not wired into the frontend). Confirmed against `/query`'s own
precedent that a single retrieval+LLM round trip belongs in-request, not
behind a Celery task — this is the **first scanner phase that needed no
`task_routes` entry and no dual-restart checklist**, since nothing was added
to the chained pipeline.

**Frontend** — `frontend/src/lib/api.ts` gained `evidence_metadata` on
`FindingDetail`'s evidence type (a real pre-existing gap: it was fetched by
the backend but never typed/rendered) and `validateFinding()`/
`ValidateFindingError` (carries the HTTP status so 422 can be styled as an
informational fresh-install note, distinct from a real error). The scanner
detail page's already-built findings-expand row gained a "Validate with AI" /
"Re-validate with AI" button (computed from whether an `llm_reasoning`
Evidence row already exists — no new column needed anywhere) and distinct
rendering for `llm_reasoning` evidence: a purple-tinted "AI review" chip
instead of the generic `source_type` label, two verdict badges, and a
"Grounded in:" citation list.

## A real bug found and fixed during the live-infra test

Not a bug in the production code — a test design flaw caught by actually
running the live-infra suite, not assumed correct. The first version of
`test_validate_finding_creates_llm_reasoning_evidence_with_real_retrieval`
seeded a fabricated one-paragraph standard doc with a unique nonce and
asserted the validate call's citations pointed back to *that* document. It
failed: the shared dev/test Qdrant collection already holds a real ISO 27001
PDF ingested in much earlier phases, and — since embeddings are faked as an
identical constant vector for every call in this test file, exactly like
`test_query_api.py`'s own documented caveat — dense-search ranking is
meaningless, while real lexical search legitimately favored the older,
richer, more keyword-dense real document over a thin fabricated stub on a
generic term like "cryptography." The nonce didn't help because it only
appeared in the ingested document's text, not in the retrieval query (which
is built from the Finding's own fields, never from injected test content).
Fixed by relaxing the assertion to match `test_query_api.py`'s own stated
philosophy — verify the endpoint's real plumbing (non-empty, well-formed
citations) rather than asserting this test's content specifically wins a
ranking race that fake embeddings make meaningless. This is the same "shared
dev/test database" limitation this project has documented and deliberately
not "fixed" (resetting it would paper over the real root cause) since Phase 3
of the platform's main GraphRAG work.

## Verification

- **17 unit tests** (`test_compliance_retrieval.py`, `test_finding_validation.py`):
  query construction (title/category/framework/summary included, reasoning
  skipped when identical to summary, **snippets never included** — a direct
  data-egress regression test), zero-chunks → `NoStandardsContextError`,
  the same 3-retry structural copies of `test_query_classifier.py`'s tests,
  every enum value round-tripping, a direct regression test that the verdict
  vocabulary can never contain "verified"/"partially_verified"/
  "not_applicable", `persist_verdict`'s exact Evidence shape, and
  **`test_persist_verdict_never_touches_finding_status`**.
- **5 live-infra integration tests** (`test_finding_validation_api.py`):
  a real end-to-end validate call (real Postgres+Qdrant+MinIO, Voyage/
  Cohere/Gemini calls mocked) producing a real `llm_reasoning` Evidence row
  with well-formed citations; 404 for a wrong scan/finding id; 422 when
  retrieval finds nothing (via `monkeypatch`, not by depending on the shared
  DB's actual contents); bulk-validate rejecting >10 ids; bulk-validate
  partial success on a mixed valid/invalid id list.
- **Real end-to-end pass with real Voyage/Cohere/Gemini keys** against the
  running stack: uploaded a real weak-MD5-hash sample repo, called
  `POST /scans/{id}/findings/{id}/validate` for real (~7.6s round trip),
  got back a genuinely coherent verdict (`likely_true_positive`,
  `supports_concern`) citing real ISO 27001 Annex A clauses (A.12.3, A.16)
  from documents ingested in much earlier phases of this project, with a
  substantive, non-fabricated rationale. Confirmed the finding's own
  `status` (`POTENTIAL_NON_COMPLIANCE`) was untouched and the new evidence
  row landed alongside the original `ast_analysis` one. No Celery worker
  restart was needed this time — only the FastAPI process, confirming the
  "no new Celery infrastructure" design choice held in practice, not just
  in theory.
- Lint (`ruff check`) clean. **Full backend suite: 372 passed** (up from
  350 at the end of Phase 5 — 22 new tests: 17 unit + 5 live-infra),
  confirmed via a clean run (909.85s, 0:15:09).
- Frontend `pnpm lint`/`pnpm build` clean.

## Explicitly out of scope

`RemediationAgent` (Phase 9, per `Finding.recommendation`'s own model
comment). Any change to `Finding.status` or `decide_control_status`'s logic —
this agent only ever adds an Evidence row. Full corpus-wide semantic search
across all scans — retrieval is exactly `retrieval.vector_search` as-is,
scoped only by whatever the user has already ingested; nothing scan-specific
enters the vector store. Any new Celery task/queue/status-track. LLM-generated
`VERIFIED`/`PARTIALLY_VERIFIED`/`NOT_APPLICABLE` — still requires new
deterministic positive-evidence rules per Phase 5's own "explicitly out of
scope," not an LLM judgment call. Wiring the bulk-validate endpoint into the
frontend (built and tested, but no "validate selected" UI this phase).
