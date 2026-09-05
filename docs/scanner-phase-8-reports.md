# Compliance Scanner — Phase 8: Reports

## Goal

Add a per-scan compliance report a human can read and print/save as a PDF —
aggregating findings by severity/status/framework, plus human review
coverage from Phase 7 (a scan-level counterpart to what Phase 7 recorded per
finding). Must respect this project's standing "technical evidence
coverage, not certification" constraint (established in
`docs/scanner-phase-5-iso27001-mapping.md`): no aggregate compliance score
or percentage anywhere.

## What was built

**The user resolved the report-format decision, via `AskUserQuestion`**
(same pattern as Phases 5/6/7): a printable HTML report page, not a
backend-generated PDF and not a bare CSV/JSON export. Zero new backend
dependencies — confirmed via research that none exist anywhere in this
stack (no reportlab/weasyprint/jinja2-as-templating; `jinja2`/`xlsxwriter`
in `uv.lock` are transitive-only, pulled in by `docling`/`torch`).

**New `GET /scans/{scan_id}/summary`** endpoint, backed by a pure,
DB-free aggregation function `app/services/scan_summary.py`'s
`build_scan_summary(findings)` — mirrors `finding_review.py`'s
`apply_review` and `iso27001/mapping.py`'s `decide_control_status`: one
query with `Finding.reviews` eager-loaded (`selectinload`), one Python
grouping pass. Zero-fills every fixed-vocabulary axis (severity/status/
framework) so a report always shows the full spec vocabulary — "0
VERIFIED" is more honest than an absent row. Surfaces
`requires_human_review_unreviewed_count` — currently-flagged findings that
have never been looked at by a human, distinct from `unreviewed_findings`
(which also includes already-settled findings like `NOT_APPLICABLE`) — the
single most report-worthy number this phase newly makes visible. No
migration needed — a pure aggregate read over existing tables.

**New printable report page** at `/scanner/[scanId]/report`: header with
scan metadata and a generation timestamp, an always-visible
`ReportDisclaimerBanner` (new component — distinct from the existing
`ComplianceDisclaimerBanner`, which is ISO27001-specific and conditional;
this one is project-wide and unconditional), an incomplete-coverage warning
if any status track hadn't finished when the report was generated, three
breakdown tables (severity/status/framework — no charts, no charting
library in this stack), a review-coverage stat grid, the existing
ISO27001 disclaimer when relevant, and the full findings list as
un-collapsible cards (print output can't expand anything) — each showing
evidence and review history inline, reusing `SeverityBadge`/
`FindingStatusBadge` and the same AI-verdict rendering Phase 6 built.

**Findings-list data**: no new bulk-detail endpoint — the report page
calls the existing `getScanFindings` for the ordered list, then
`Promise.all` over `getScanFinding` per row for full detail concurrently. A
deliberate, small N+1 bounded by one scan's finding count (a report is a
one-time page load, not a hot path).

**Print styling, one real technical correction from the original plan**:
the plan initially considered nesting a media condition inside Tailwind's
`@custom-variant dark` declaration to suppress dark-mode colors when
printing — checking `globals.css` directly showed this dark-mode variant
is keyed purely off the `data-theme="dark"` DOM attribute
(`@custom-variant dark (&:where([data-theme="dark"], [data-theme="dark"] *));`),
and `@custom-variant` takes a selector, not an at-rule, so that approach
isn't valid syntax — and even a `@media print` override of the CSS custom
properties alone would leave every literal hardcoded `dark:` utility class
(e.g. `SeverityBadge`'s `dark:bg-red-500/15`) active whenever
`data-theme="dark"` was set. Fixed with a JS toggle instead: the report
page's print handler temporarily flips `document.documentElement.dataset.theme`
to `"light"` right before `window.print()`, and restores it via the
standard `afterprint` DOM event once the print dialog closes — this
correctly forces the entire app into light mode for print output with
zero changes to any component. Also added `print-color-adjust: exact` (+
the `-webkit-` prefix) in `globals.css` (browsers suppress
`background-color` on print by default, which would otherwise silently
drop every severity/status badge's color), and `print:hidden` on the
top nav in `app/(app)/layout.tsx` (previously had zero print handling).

**Link from the scan detail page**: a "View report →" link next to the
scan's overall `StatusBadge`, reachable once all five status tracks are
**terminal** (`TERMINAL_STATUSES` — ready or failed), not only once all are
`"ready"` — a failed track's absence is surfaced inside the report itself
(the incomplete-coverage warning) rather than blocking the report
indefinitely.

## Verification

- **19 unit tests** (`test_scan_summary.py`): empty-findings zero-filling;
  severity/status/framework counts zero-fill every fixed value and count
  correctly when present; `framework=None` groups as its own bucket; a
  finding with zero reviews counts as unreviewed, ≥1 review counts as
  reviewed exactly once regardless of how many while `total_reviews` sums
  all of them; `human_review_required=True` with zero reviews increments
  the unreviewed-flagged counter, the same flag with a review recorded
  does not; a parametrized combination test over all 6 statuses ×
  review-presence confirming the counters never drift out of sync with
  `total_findings`.
- **6 live-infra integration tests** (`test_scan_summary_api.py`): 404 for
  a bogus scan id; summary metadata matches the real scan/findings
  exactly; breakdowns zero-fill and sum to `total_findings`; **a direct
  regression test that the response never contains a
  score/percentage/grade/rating field anywhere** (the standing
  anti-overclaiming constraint, enforced as code, not just convention);
  review coverage before and after submitting a real review (reusing
  Phase 7's endpoint), including that a second review on the same finding
  still counts it as reviewed exactly once.
- Lint (`ruff check`) clean. **Full backend suite: 455 passed** (up from
  430 at the end of Phase 7 — 25 new tests: 19 unit + 6 live-infra),
  confirmed via a clean run (1109.64s, 0:18:29).
- Frontend `pnpm lint`/`pnpm build` clean — new `/scanner/[scanId]/report`
  route registered.
- **Live end-to-end** via the real running stack (only FastAPI needed
  restarting — no Celery worker, no new task): uploaded a real sample
  repo, fetched its real summary (56 findings, correctly zero-filled
  VERIFIED/NOT_APPLICABLE at 0, 28 flagged for human review, 0 reviewed),
  submitted a real review (`VERIFIED`, with justification) on its weak-MD5
  finding, and confirmed the summary updated correctly in the real
  database: `reviewed_findings` 0→1, `total_reviews` 0→1, `VERIFIED` count
  0→1, `POTENTIAL_NON_COMPLIANCE` count decremented accordingly. Confirmed
  both the scan-detail page and the new report page load through the
  running dev server (structural/HTTP check only — no browser-automation
  tool in this environment, same disclosed limitation as every prior
  frontend phase).

## Explicitly out of scope

`RemediationAgent`/generated fix suggestions (Phase 9). Any cross-scan/
multi-scan dashboard or aggregate — this phase stays strictly per-scan.
Any numeric/letter compliance score or percentage anywhere in the schema
or page — only raw counts across fixed, zero-filled vocabularies,
enforced by a direct regression test. Backend PDF generation. Scheduled/
emailed reports. Charting/graphs. A "Validate with AI"/review-submission
action on the report page — those remain scan-detail-page-only
interactive actions; the report is read-only.
