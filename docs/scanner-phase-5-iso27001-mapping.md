# Compliance Scanner — Phase 5: ISO 27001 Mapping

## Goal

Map existing Phase 2/3/4 findings onto ISO/IEC 27001:2022 Annex A controls
(`framework="ISO27001"`). Still deterministic — zero LLM calls (semantic
retrieval/reasoning stays Phase 6's job). The real architectural question
this phase raises: every prior phase wrote one `Finding` per raw
code-pattern hit; this phase's job is fundamentally different — one
assessment *per control*, aggregating potentially many existing findings
as evidence.

**Licensing constraint, resolved by explicit user decision before any
code was written**: ISO 27001's actual Annex A text is copyrighted and
this project has no licensed copy — unlike GDPR (public law) or ISO 42001
(generic governance concepts describable in this project's own words).
Raised proactively (not by the user) via `AskUserQuestion`; the user chose
to seed the catalog with **publicly-known control IDs and short titles
only**, never full normative clause text, with a mandatory `source_note`
disclaimer on every entry that must survive serialization everywhere the
data is surfaced — API, frontend, docs — not just a one-time code comment.

## What was built

**New package** `app/services/iso27001/`:

- `catalog.py` — a frozen `ISO27001Control` dataclass
  (`control_id`/`title`/`theme`/`description`/`assessment_type`/
  `automatable`/`evidence_types`/`source_note`), populated with **48 of
  the standard's 93 controls**: all 34 Technological (A.8) controls (6
  marked `automatable=False` where the control is organizational in
  practice despite the theme — user endpoint devices, capacity
  management, redundancy, clock sync, software-installation governance,
  outsourced development) plus 14 Organizational (A.5) controls with a
  plausible existing Finding category to map from (asset inventory,
  classification, supplier relationships, incident management,
  legal/regulatory, privacy). **People (A.6) and Physical (A.7) are
  deliberately uncatalogued** — zero existing Finding category relates to
  personnel/HR security, and physical-security controls are structurally
  unassessable from a source-code scan under any circumstance.
- `mapping.py` — a hand-authored `CATEGORY_TO_CONTROLS: dict[(framework,
  category), list[control_id]]` connecting 15 existing Finding categories
  to control IDs, plus an explicit `DELIBERATELY_UNMAPPED_CATEGORIES`
  dict recording every category with no real Annex A analog (GDPR's
  legal constructs — `lawful_basis`/`consent_mechanisms`/`dpia`/etc. —
  and most of Phase 4's AI-specific detection categories), each with a
  one-line reason, asserted by a parametrized unit test so the omission
  can't silently regress. A `CONTROL_TO_CATEGORIES` reverse index is
  built once from the same dict (never hand-duplicated, so the two can't
  drift apart). `decide_control_status(automatable, mapped_findings)`
  returns a `ControlAssessment(status, severity, reasoning)`, deliberately
  producing only 3 of the spec's 6 statuses:
  - `automatable=False` → always `REQUIRES_HUMAN_REVIEW`.
  - `automatable=True`, ≥1 mapped finding is `POTENTIAL_NON_COMPLIANCE` →
    the control is too, with max-severity propagated.
  - `automatable=True`, mapped findings exist but all
    `REQUIRES_HUMAN_REVIEW` → the control is too.
  - `automatable=True`, zero mapped findings → `NOT_VERIFIED`.
  - **`VERIFIED`/`PARTIALLY_VERIFIED` are never produced** — nothing in
    Phases 2-4's rule set produces positive evidence a control is
    satisfied, only gap detection; synthesizing "verified" from "no
    negative finding fired" would claim more than the evidence supports.

**Evidence: duplicated, not FK-shared.** `Evidence.finding_id` is a
single nullable FK (one Evidence row belongs to at most one Finding) —
this is the first phase where one Finding needs to aggregate many other
findings' worth of evidence. Rather than a schema change, each mapped
source finding's Evidence rows are **copied** onto the new ISO27001
Finding (`source_type="control_mapping"`, `evidence_metadata` carrying
`source_finding_id`/`source_framework`/`source_category`/
`catalog_source_note`). This is forced, not stylistic: every prior task
clear-then-rebuilds its own findings with **new UUIDs** on every rerun —
referencing the original rows by FK would let a routine upstream rerun
silently orphan this stage's evidence via the existing
`ondelete="SET NULL"`. A control with zero mapped findings still gets one
synthetic `repo_aggregate` Evidence row, matching the repo-level-finding
pattern Phase 3/4 already use.

**Pipeline**: a sixth chained task, `run_iso27001_analyzers_task`,
tracked on a fifth independent status track,
`Scan.iso27001_status`/`iso27001_error_message` (migration
`0008_iso27001_findings.py`) — the idempotent-clear scope
(`Finding.framework == "ISO27001"`) is distinct from all four prior
scopes, same "genuinely separate failure domain" test every phase has
applied. Unlike every prior stage, this one reads no repository files at
all — only `Finding` rows Phases 2-4 already wrote, looping the 48
catalogued controls (not the scanned files) and writing exactly one
Finding per control per scan.

**API**: new `GET /compliance/frameworks/iso27001/controls`
(`app/api/routes/compliance.py`) returns the catalog with a top-level
disclaimer plus each entry's own `source_note` — belt-and-suspenders
labeling. `GET /scans/{id}/findings?framework=ISO27001` needed zero
backend changes (the existing filter was already generic).

**Frontend**: fixed a pre-existing gap found while reviewing the polling
code before assuming it was fine — `ScanStatus`/the polling
`useEffect`/the findings-refetch `useEffect` never accounted for
`ai_status` at all (a gap that predates this phase, from Phase 4). Fixed
`ai_status` and added `iso27001_status` in the same pass across
`lib/api.ts` and `scanner/[scanId]/page.tsx` — polling, header status
badges, and failure messages all now cover all five status tracks. New
`components/ComplianceDisclaimerBanner.tsx`, shown when the findings view
is filtered to `ISO27001`. The unofficial-data note is also folded
directly into each ISO27001 finding's `summary` text (backend-side,
`f"{control.title}. {assessment.reasoning} {control.source_note}"`),
since the findings list view doesn't show the fuller `reasoning` field
without a click-through.

## A real environment bug found and fixed along the way

Not a code bug in this phase's logic, but a genuine environment
regression discovered while running the Alembic migration: `DATABASE_URL`
in `backend/.env` pointed at `localhost`, which resolves to `::1` on this
machine — and Postgres's Docker port-forward for `::1` had stopped
working after the container's last unclean-shutdown/WAL-recovery cycle,
while `127.0.0.1` connected fine. This silently broke every live-infra
test's `_infra_available()` check (they'd have shown as *skipped*, not
failed, which is easy to miss) and would have broken Alembic/the host
FastAPI process too. Fixed by repointing `DATABASE_URL` at `127.0.0.1`.
Confirmed Redis and MinIO were unaffected (both connected fine over
`localhost`) — this was specifically a Postgres/IPv6 issue, not a general
Docker-networking one, so only that one line needed changing.

## Verification

- **52 unit tests**: catalog integrity (48 entries, no duplicate IDs,
  every entry has a `source_note`, `automatable=False` never paired with
  `assessment_type="technical"`, exactly the 6 expected A.8 controls
  marked non-automatable) and mapping (referential integrity via
  `validate_mapping_integrity()`, every expected category mapped,
  every deliberately-unmapped category asserted absent from the mapping
  table, all four branches of `decide_control_status` including a direct
  regression test that `VERIFIED`/`PARTIALLY_VERIFIED` are never
  returned).
- **10 live-infra integration tests** (`test_iso27001_findings_api.py`,
  structural extension of `test_ai_findings_api.py`'s pattern): a
  four-way framework partition, exactly 48 ISO27001 findings per scan
  (one per catalogued control, unique `rule_id`s), never
  `VERIFIED`/`PARTIALLY_VERIFIED` live, a non-automatable control (A.8.1)
  always `REQUIRES_HUMAN_REVIEW`, a real hardcoded-crypto finding tracing
  through to `A.8.24`'s `POTENTIAL_NON_COMPLIANCE` status with its
  evidence's `source_finding_id` matching the real source Finding, a
  zero-mapped control (A.8.23) correctly `NOT_VERIFIED` with one
  synthetic evidence row, and the bidirectional delete-scoping regression
  extended to **four-way** (parametrized over all three upstream
  rule-pass tasks, confirming a rerun of any one never changes the
  ISO27001 finding count, and a rerun of the ISO27001 pass itself never
  changes the other three).
- **One pre-existing test updated, not a regression**:
  `test_ai_findings_api.py::test_three_way_framework_partition` asserted
  an exact `{None, "GDPR", "ISO42001"}` framework set — now correctly
  `{None, "GDPR", "ISO42001", "ISO27001"}` since the chain has a sixth
  stage. Caught by a full-suite run, not missed.
- Lint (`ruff check app/ tests/`) clean.
- **Full backend suite: 350 passed** (up from 288 at the end of Phase 4 —
  62 new tests: 52 unit + 10 live-infra), confirmed via a clean run with
  zero concurrent activity (`1476s`, `0:24:36`). One earlier background
  full-suite run showed 3 transient failures (`ConnectionResetError`
  against MinIO) caused by this session's own concurrent live-upload/
  process-restart activity happening *during* that run, not a real
  regression — confirmed by re-running the affected tests in isolation (2
  of 3 passed immediately; the third, the framework-set assertion above,
  was the one real pre-existing-test update needed).
- **Live end-to-end via the real queue-backed pipeline**: killed and
  restarted both the FastAPI process and the Celery worker (the
  `task_routes` dual-restart checklist, now required a fifth time),
  confirmed the new `scanner.run_iso27001_analyzers` task registered on
  the worker, uploaded a real sample repo (hardcoded AWS-style key split
  across a string concatenation to avoid tripping secret scanners, weak
  MD5 hashing, a hardcoded SSN-shaped field, an `openai`+`qdrant_client`
  import pair, a prompt string, a `@tool`-decorated function) through the
  running API. Confirmed all five status fields reached `"ready"`, 48
  ISO27001 findings with the expected status distribution (24
  `REQUIRES_HUMAN_REVIEW` / 22 `NOT_VERIFIED` / 2
  `POTENTIAL_NON_COMPLIANCE`, matching the weak-MD5-hash → A.8.24 and
  PII-in-log → A.8.15 mappings), `A.8.24`'s evidence correctly traced
  back to the real cryptography Finding's id, and `LLEN scanner`/`LLEN
  celery` both drained to `0` (no misrouting). Also verified
  `GET /compliance/frameworks/iso27001/controls` live — 48 controls, the
  top-level disclaimer, and each entry's own `source_note` all present.
- Frontend `pnpm lint`/`pnpm build` clean.

## Explicitly out of scope

Any LLM-based reasoning about whether evidence actually satisfies a
control's intent, and the `FindingValidationAgent` concept — both Phase
6. Semantic/embedding-based `ComplianceRetriever` — Phase 6; this phase's
mapping is a static hand-authored dict. Full 93-control coverage — see
the catalog's own docstring for the exact list of what's left out and
why (People/Physical themes entirely, plus 23 of A.5's 37 controls).
Any certification claim or authoritative score — this project's standing
"technical evidence coverage, not certification" framing still applies.
Real positive-evidence `VERIFIED`/`PARTIALLY_VERIFIED` checks — new
rule-authoring work outside this phase's charter.
