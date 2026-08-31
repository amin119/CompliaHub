# Compliance Scanner — Phase 4: AI / ISO 42001 Analyzer

## Goal

Add AI-system detection and ISO 42001 governance findings
(`framework="ISO42001"`) on top of Phases 2 (security) and 3 (GDPR).
Still deterministic — zero LLM calls. The spec explicitly warns against
classifying a project as AI because of a single dependency, so detection
combines multiple independent signal types before asserting "this is an
AI system."

## What was built

**New package** `app/services/ai_analysis/` — same shape as
`privacy_analysis/`: `RuleContext`/`RuleHit`/`FunctionRule` reused
directly from `security_analysis/base.py`, an `AI_RULES` registry
separate from Phase 2's and Phase 3's (different category taxonomy, same
reasoning as Phase 3's own separation).

- `ai_imports.py` — a curated `_AI_ML_PACKAGES` dict (LLM/embedding
  providers, ML frameworks, vector databases, agent frameworks), each
  tagged with a `kind`. `detect_ai_imports` is the structural building
  block (returns `(name, label, kind, line)` tuples) both the per-file
  finding and the repo-level aggregator use — kept separate from the
  `RuleHit`-producing wrapper specifically so structured data never has
  to be re-derived from title text later (the exact anti-pattern that
  caused Phase 3's bug #3).
- `rag_detection.py`, `prompt_detection.py`, `agentic_detection.py`,
  `inference_detection.py` — conservative, same-file co-occurrence
  heuristics (vector-DB import + embedding call, prompt-named variable or
  inline string to an inference call, `@tool`/`bind_tools`/`StateGraph`
  patterns, inference-shaped call + AI import in the same file). All
  Python-first via `ast`, no dataflow tracing (same posture every prior
  phase has used).
- `repo_level_checks.py` — nine fixed governance findings (AI system
  documentation, intended purpose, risk management, human oversight,
  model evaluation, monitoring/logging, incident handling, lifecycle
  management, third-party AI providers) plus the AI system inventory,
  **all gated on a ≥2-distinct-signal-type threshold** — a deliberate
  departure from Phase 3's GDPR findings (which fire unconditionally,
  since near-any backend touches some personal data; most repos are not
  AI systems at all, so unconditional AI-governance findings would be
  noise, not a genuine gap).

**Import-detection mechanic promoted, not duplicated**:
`privacy_analysis/third_party.py`'s private `_imported_top_level_names`
was promoted to `security_analysis/ast_utils.py` as public
`imported_top_level_names` — the same kind of promotion Phase 3 did once
for `is_logger_call`/`attribute_names_matching`. Phase 3's and Phase 4's
curated package lists stay independent (they answer different questions
about the same raw import signal — a `cohere` import fires both a GDPR
`third_party_processors` finding and an ISO42001 `ai_system_detection`
finding, the same "two rows, same evidence line, different framework"
pattern `logging_pii.py` already established).

**AI system inventory**: the spec's own JSON shape (`models`, `uses_rag`,
`uses_tools`, `external_data`, `human_oversight`) doesn't fit a per-issue
row, so it's written as one repo-level `Finding` with one `Evidence` row
whose `evidence_metadata` JSONB column (existed since Phase 1, unused
until now) carries the structured JSON. `human_oversight` is hardcoded
to `"unknown"` — never inferred from code, matching the spec's own
worked example verbatim. `RuleHit` gained an `evidence_metadata: dict |
None = None` field (same per-hit-overrides-nothing-by-default shape
`category` already uses) to carry it through. `EvidenceResponse` gained
the matching field — without it the JSON would have been written to the
database but invisible through the API.

**Pipeline**: a fifth chained task, `run_ai_analyzers_task`, tracked on a
fourth independent status track, `Scan.ai_status`/`ai_error_message`
(migration `0007_ai_findings.py`) — genuinely separate failure domain,
since its idempotent-clear scope (`Finding.framework == "ISO42001"`)
differs from both Phase 2's and Phase 3's.

**No frontend code changes** — confirmed by reading
`scanner/[scanId]/page.tsx` before assuming it: the framework filter-chip
row is already generic over however many distinct framework values
appear in the findings list, so `"ISO42001"` became a third chip with
zero rework.

## Verification

- **33 unit tests** across the five detection modules and the repo-level
  checks, all passing, including a direct regression test that a single
  AI import alone must not clear the aggregate threshold.
- **5 live-infra integration tests** (`test_ai_findings_api.py`,
  structural copy of `test_privacy_findings_api.py`): a three-way
  framework partition, every expected ISO42001 category firing, the
  inventory's `evidence_metadata` shape, and — extending the bidirectional
  delete-scoping regression Phase 3 introduced — confirming a rerun of
  *any one* of the three rule-pass tasks never changes either of the
  other two's finding counts.
- **Full backend suite: 288 passed** (up from 250 at the end of Phase 3).
- **Live end-to-end, via the real queue-backed pipeline**, following the
  restart checklist from Phase 2/3's bug history — restarted both the
  FastAPI process and the Celery worker, confirmed via Redis
  (`LLEN scanner`/`LLEN celery` both `0` after completion — no
  misrouting this time), uploaded a real repo with an `openai` import, a
  `qdrant_client` import, a prompt string, and a `@tool`-decorated
  function through the running API. Confirmed all five status fields
  (`status`/`findings_status`/`privacy_status`/`ai_status`) reached
  `"ready"` and every expected category
  (`ai_system_detection`/`rag_detection`/`prompt_detection`/
  `agentic_pattern_detection`/`inference_call_detection`/
  `ai_system_inventory` + all nine governance findings) appeared in the
  real database via `GET /scans/{id}/findings?framework=ISO42001`.
- Frontend `pnpm lint`/`pnpm build` clean — confirmed no regression from
  the new framework value flowing through unchanged components.
- **No new bugs found this phase** — the restart-both-processes checklist
  (missed once in Phase 2, correctly followed in Phase 3) was followed
  correctly from the start this time, and the delete-scoping/category-
  travels-with-the-hit patterns established in Phases 2/3 were applied
  proactively rather than discovered live.

## Explicitly out of scope

ISO 27001 mapping (later phase, a future distinct `"ISO27001"` framework
value). Any LLM-based reasoning about EU AI Act risk classification or
model-evaluation adequacy — Phase 6. Actual AI risk assessment/DPIA-
equivalent generation. Full non-Python AST. Inspecting model weight files
or dataset content — only code-level usage patterns, never file bytes.
Real-time/runtime AI behavior monitoring — a governance finding can note
monitoring *code* exists or doesn't, never that it's actually working.
