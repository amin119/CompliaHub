# Compliance Scanner — Phase 7: Human Review

## Goal

Add the one mechanism in this system that can ever write
`VERIFIED`/`PARTIALLY_VERIFIED`/`NOT_APPLICABLE` onto a `Finding.status` — a
full-codebase grep confirmed these three of the spec's 6-value vocabulary had
never been written by any code path across Phases 2-6, only gap-detection
statuses (`POTENTIAL_NON_COMPLIANCE`, `REQUIRES_HUMAN_REVIEW`, and
ISO27001-mapping-only `NOT_VERIFIED`). The `Finding` model's own docstring
hinted the remaining values "only become meaningful once ... a human/LLM has
acted on the finding," and Phase 6's `FindingValidationAgent` was deliberately
restricted to never touch `Finding.status` (only adds an `Evidence` row) —
this phase restores this project's standing "only a human can claim positive
compliance, never automation" principle. Frontend had zero UI for this at
all: no status column, no status filter, `human_review_required` fetched but
never rendered.

## What was built

**New `FindingReview` model** (`app/models/scan.py`), append-only — same
"never mutate, always insert" convention as `Evidence`: a finding can be
reviewed multiple times over its life. `decision` reuses `Finding.status`'s
exact 6-value vocabulary directly (no narrower confirm/override layer — that
would just re-derive the same 6 values through indirection). `notes` is
`NOT NULL`, enforced non-empty (≥10 chars after trim) at the Pydantic layer
for every decision, not just the 3 positive-compliance ones — a human
overriding to `VERIFIED` with no written reasoning would repeat exactly the
unjustified-claim problem this project has always refused to let an LLM get
away with. `previous_status` snapshots the finding's status immediately
before each review, so history renders a clear before→after per entry.
`reviewer_name` is free text, not a foreign key to any user/auth table — this
backend has no authentication system anywhere (explicit project-wide scope
decision, not an oversight), so it's an honestly-unverified, self-reported
label, resolved via `AskUserQuestion` before implementation (same pattern as
Phase 5's licensing question).

**`Finding.status` is updated as a side effect of creating a review** — the
review is the authoritative status-setter, via a tiny pure function
`app/services/finding_review.py`'s `apply_review(finding, decision)`.
`human_review_required` is set to `decision == "REQUIRES_HUMAN_REVIEW"` —
conditional, not unconditionally cleared, so a reviewer who concludes a
finding genuinely needs escalation to a second reviewer isn't silently
swallowed by the act of reviewing it once.

**New migration** `0009_finding_reviews.py` — a brand-new table (mirroring
`0005_security_findings.py`'s `create_table` + indexes + FK shape, not
`0008`'s simple `add_column` pair), the first schema change since Phase 5
(Phase 6 needed none).

**API**: single new synchronous endpoint,
`POST /scans/{scan_id}/findings/{finding_id}/reviews` — direct DB write, no
Celery (lighter even than Phase 6's validate endpoint, which at least makes
an LLM call; this is a plain data-entry action). Review history is folded
into the existing `GET .../findings/{finding_id}` response as
`reviews: list[FindingReviewResponse]`, the same precedent `evidence` already
set — no separate endpoint, since the frontend already lazy-loads
`FindingDetail` on row-expand, the one place review history is consumed.

**Frontend**: new `FindingStatusBadge` component (a badge for the 6
`Finding.status` values — `StatusBadge` is shaped for the scan-level
ready/failed/pending vocabulary and was the wrong fit). The findings table
gained a **Status** column (right after Severity), a status filter chip row
(mirroring the existing client-side `frameworkFilter` pattern), and a
**"Needs review only"** toggle filtering on `human_review_required` — the
actual operational queue a reviewer cares about, distinct from the literal
`REQUIRES_HUMAN_REVIEW` status string. The findings-detail expand row gained
a review history list (newest first, `previous_status → decision`, reviewer,
notes, timestamp) and a review form (reviewer name, a `<select>` over the 6
statuses, a required notes `<textarea>`), inserted **after** the existing
Evidence section so any AI verdict from Phase 6 is visible as context before
a human decides. Also improved `parseErrorDetail` in `lib/api.ts` to surface
FastAPI's structured 422 validation-error list (not just a plain string
`detail`), since the review form's blank-notes rejection needed the actual
message, not a generic "Request failed (422)."

## Verification

- **51 unit tests** (`test_finding_review.py`): `FindingReviewRequest`
  schema validation (every valid decision accepted, invalid decision
  rejected, blank/too-short notes rejected, notes trimmed, blank reviewer
  name becomes `None`); `apply_review()` parametrized over all 6 decisions
  × all 6 starting statuses (36 cases) confirming `previous_status`
  snapshotting and `human_review_required` tracking, plus a direct
  re-escalation test.
- **7 live-infra integration tests** (`test_finding_review_api.py`, no
  LLM/embedding mocking needed — zero external calls in this phase):
  create-review updates finding status and appears in `reviews`; two
  sequential reviews accumulate newest-first with correct
  `previous_status` chaining; blank notes → 422; invalid decision → 422;
  404 for wrong scan/finding id; reviewing a `REQUIRES_HUMAN_REVIEW`
  finding to `VERIFIED` clears the flag, re-escalating sets it again; a
  review never mutates the finding's existing `Evidence` rows.
- Lint (`ruff check`) clean. **Full backend suite: 430 passed** (up from
  372 at the end of Phase 6 — 58 new tests: 51 unit + 7 live-infra),
  confirmed via a clean run (914.5s, 0:15:14).
- Frontend `pnpm lint`/`pnpm build` clean.
- **Live end-to-end** against the real running stack (only the FastAPI
  process needed restarting — no Celery worker, no new task, same as
  Phase 6): uploaded a real sample repo, submitted a real review on its
  weak-MD5-hash finding — `decision: "VERIFIED"` with a substantive
  justification ("already migrated to bcrypt in production, this MD5 use
  is dead code") — and confirmed the finding's `status` really did
  change from `POTENTIAL_NON_COMPLIANCE` to `VERIFIED`, the **first time
  in this project's entire history `Finding.status` has ever held that
  value**, with `human_review_required` correctly clearing and the full
  review recorded in the real database. Confirmed blank notes correctly
  422 live.

## Explicitly out of scope

Any cross-scan "review queue"/dashboard aggregating findings across
multiple scans — no such aggregate view exists anywhere in this project
yet; this phase stays scoped per-scan, like every existing findings
endpoint. Real authentication/authorization. `RemediationAgent` (Phase 9).
Reports (Phase 8) — though Phase 8 will likely want to read
`FindingReview` history for report output (reviewer/decision/notes),
worth a forward note here but not built now.
