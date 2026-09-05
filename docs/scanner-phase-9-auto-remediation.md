# Compliance Scanner — Phase 9: Auto Remediation (final phase)

## Goal

Give a human reviewing a code-level finding a concrete, AI-suggested fix —
not just "here's what's wrong" (Phase 2's rule engine) or "here's whether
it's a real concern" (Phase 6's `FindingValidationAgent`) but "here's a
diff you could apply." `Finding.recommendation`'s own model comment was
the only breadcrumb for this phase since Phase 1: "not generated
remediation (that's a later phase's `RemediationAgent`)."

Research confirmed a hard constraint going in: 8 phases in, scanning is
still zip-upload-only (`Scan.source_type` defaults `"zip"`, no git-clone/
write-back path, no GitHub/GitLab API client, no `GitPython`/`pygit2`
anywhere). Real git automation (clone, branch, commit, PR) was ruled out as
an entirely different, much bigger subsystem — not this phase's job.

## What was built

**The user resolved the remediation-depth decision, via `AskUserQuestion`**
(same pattern as Phases 5-8): a **suggested code diff**, not plain-text-only
guidance and explicitly not git automation. A `RemediationAgent`
(`backend/app/services/finding_remediation.py`) mirroring Phase 6's
`FindingValidationAgent` shape — Protocol + adapter + `@lru_cache`d SDK
client + retry loop, deliberately duplicating (not importing) the small
`_sdk_client` helper, per this project's own established "different
prompt/schema, no shared call site" precedent.

**Locating real code to fix**: unlike Phase 6 (which never touches MinIO),
a code suggestion needs real surrounding code, not `Evidence.snippet`'s
short excerpt. `locate_fix_target` picks the first Evidence row on a
Finding with a concrete `file_path`/`line_start` (the common case — one
finding, one flagged location), resolves the matching `RepositoryFile`,
downloads real content via `scan_storage.download_object`, and slices a
±15-line window around the flagged lines, clamped to file bounds. Raises
`NoLocatableEvidenceError` — surfaced as 422 — for findings with no
concrete code location (GDPR organizational findings, ISO27001
control-assessment findings), same "this is expected, not a bug" framing
as Phase 6's `NoStandardsContextError`.

**`RemediationSuggestion`** (structured Gemini output): `problem_explanation`,
`suggested_code` (a full replacement for the *entire* window, not a diff
itself — the prompt requires this so it diffs cleanly), `fix_explanation`,
`confidence`. The system prompt explicitly forbids claiming the fix makes
code "compliant" or "secure" — only that it addresses the specific flagged
pattern, matching this project's evidence-first, never-overclaim
constraint (`docs/scanner-phase-5-iso27001-mapping.md`).

**Diff generation is pure and deterministic** — `build_unified_diff` uses
stdlib `difflib.unified_diff` for the actual diff computation (never
hand-rolled), then rewrites just the two numeric `@@ -a,b +c,d @@` header
offsets by adding `window_start_line - 1`, since `difflib` has no
"starting line number" parameter and its headers are always
window-relative.

**Persistence reuses `Evidence`, no migration**: `source_type=
"llm_remediation"` (parallel to Phase 6's `"llm_reasoning"`),
`rule_id="llm_finding_remediation"`, real `repository_file_id` populated
(unlike Phase 6, always `None`), `snippet` holds the diff text itself,
`description` holds `f"{problem_explanation}\n\n{fix_explanation}"`,
`evidence_metadata` holds the model name and target/window line ranges.

**API**: `POST /scans/{scan_id}/findings/{finding_id}/remediate` — 404 for
wrong scan/finding, 422 for `NoLocatableEvidenceError`, 503 for exhausted
retries. Synchronous, in-request, no Celery — same order of magnitude
Phases 6-8 each independently confirmed stays in-request. **Deliberately
no bulk-remediate endpoint** (a disclosed scope cut, not an oversight):
unlike Phase 6's bulk validate (cheap, read-only-in-effect, makes sense to
batch), remediation is fundamentally single-finding-at-a-time — a human
reads one issue, requests a fix, then manually reviews/adapts it. No
"generate 10 diffs and copy-paste all of them" workflow exists to optimize
for.

**Frontend**: a "Suggest a fix" button beside "Validate with AI" on each
finding (`handleRemediate` structurally mirrors `handleValidate`), a purple-
tinted card reusing Phase 6's `isAiReview` styling (extended to
`isAiReview || isAiRemediation`), the diff rendered as a `<pre>` block with
client-side line-by-line `+`/`-`/`@@` coloring (no diff-rendering library
in this stack), and the explanation text below it.

## A real bug found and fixed via live end-to-end verification

Live verification is this project's standing discipline precisely because
mocked tests can pass while real infrastructure/data breaks something —
this phase reconfirmed it. All 7 `test_diff_generation.py` unit tests used
fixture text ending in `\n`, so none exercised the case where the flagged
line is the **last line of the file** — which is exactly what the live
end-to-end sample repo hit (a 4-line file, finding on line 4).

`locate_fix_target`'s real window text is built via
`"\n".join(lines[window_start-1:window_end])` (from `str.splitlines()`
output) — which never has a trailing newline. When that untrimmed text hit
`build_unified_diff`'s `.splitlines(keepends=True)`, the final line came
back with no `"\n"` terminator. `difflib` faithfully emitted that as the
diff's last `"-"` line with no line terminator, and joining all diff lines
via `"".join(...)` ran it directly into the following `"+"` line with zero
separator — producing a genuinely corrupted diff:

```
-    return hashlib.md5(password.encode()).hexdigest()+    return hashlib.pbkdf2_hmac(...)
```

Caught by inspecting the raw JSON response from a real call against the
live stack (not just checking the HTTP status code) — the test suite alone
would never have surfaced this. Fixed by normalizing both
`original_window_text` and `suggested_code` to guarantee a trailing
newline before splitting, with the reasoning documented directly in
`build_unified_diff`'s docstring. Added a regression test
(`test_replaced_final_line_without_trailing_newline_stays_on_its_own_line`)
reproducing the exact failure shape. Re-verified live against the real
Gemini API after the fix: a correctly-formed diff came back with the
`-`/`+` lines properly separated.

## Verification

- **11 unit tests** (`test_finding_remediation.py`): 3 retry tests
  (success-after-failures, exhausted-retries, retries-on-validation-error);
  prompt includes the finding's title and window text; `locate_fix_target`
  picks the first locatable Evidence row when multiple exist, raises
  `NoLocatableEvidenceError` when none do and when the file isn't
  content-stored; the ±15-line window is correctly clamped to file bounds;
  `persist_remediation`'s exact Evidence shape and a direct regression
  test that it never touches `Finding.status`/`recommendation`.
- **8 diff-generation unit tests** (`test_diff_generation.py`, pure, no
  LLM/DB/MinIO): correct `a/`/`b/` headers; hunk header reflects the real
  file-relative `window_start_line`; identical text produces an empty
  diff; a known multi-line change produces exact expected `+`/`-` lines;
  output matches standard unified-diff grammar; `context_lines` respected;
  the trailing-newline regression test above.
- **4 live-infra integration tests** (`test_finding_remediation_api.py`,
  Gemini client mocked, real Postgres/MinIO): real `llm_remediation`
  Evidence row with real unified-diff markers and correct `file_path`; 404
  for wrong scan/finding id; 422 when a finding's only evidence has no
  `file_path` (an ISO27001 control-assessment finding);
  `Finding.status`/`recommendation` unchanged after the call.
- Lint (`ruff check`) clean. **Full backend suite: 478 passed, 0 failed, 0
  skipped** (up from 455 at the end of Phase 8 — 23 new tests: 8 + 11 + 4
  = 23, one more than the 22 originally planned, from the trailing-newline
  regression test added after the live-verification bug), confirmed via a
  clean run (1117.27s, 0:18:37).
- Frontend `pnpm lint`/`pnpm build` clean.
- **Live end-to-end** via the real running stack (no Celery worker
  restart needed — no new task, same as Phases 6-8): uploaded a real
  4-line Python file with a weak-MD5 password hash through the live API,
  waited for the scan pipeline to reach `iso27001_status: "ready"`,
  located the resulting `SEC-CRYPTO-WEAK-PY` finding, and called
  `POST /scans/{scan_id}/findings/{finding_id}/remediate` for real against
  the actual Gemini API (not mocked). First call surfaced the
  trailing-newline diff-corruption bug above; after the fix and a backend
  restart, a second real call against the same finding returned a
  correctly-formed diff (`--- a/app/auth.py`, `+++ b/app/auth.py`, a
  well-separated `-`/`+` pair replacing the MD5 line with salted
  PBKDF2-HMAC-SHA256) with a sensible explanation, and a follow-up `GET`
  confirmed the finding's `status` (`POTENTIAL_NON_COMPLIANCE`) and
  `recommendation` were completely unchanged.

## Explicitly out of scope

Any git write-back, branch creation, commit, or PR — `Scan.source_type`
stays zip-only. Any change to `Finding.status` or `Finding.recommendation`
— this agent only ever adds an `Evidence` row. Multi-file or cross-cutting
fixes — one flagged location only. Auto-applying the suggested fix to
anything — always a copy-paste artifact for a human. A bulk-remediate
endpoint (disclosed cut, see above). Any new Celery task or migration.

---

## Closing summary: the full 9-phase scanner roadmap

1. **Ingestion & parsing** — zip-upload-only repository scanning, language/
   framework detection, per-file storage in MinIO.
2. **Deterministic rule engine** — `RuleContext`/`RuleHit`/`FunctionRule`
   pattern-matching for security/cryptography findings, zero LLM calls.
3. **Privacy findings** — GDPR-oriented repo-level checks (data-subject
   rights, retention, lawful basis) layered on the same rule-engine shape.
4. **AI/ML-specific findings** — model-card/dataset-provenance-style checks
   for AI-adjacent repositories.
5. **ISO 27001 control mapping** — maps findings to ISO 27001:2022 Annex A
   controls; establishes the standing "technical evidence coverage, not
   certification" constraint and the 6-value `Finding.status` vocabulary
   (only automation-producible values used through this phase).
6. **Agentic RAG validation** — `FindingValidationAgent` grounds each
   finding against real ingested compliance-standard text via the
   project's existing retrieval pipeline (dense+lexical+RRF+rerank),
   producing an LLM-reasoned relevance/true-positive verdict as `Evidence`
   — never touches `Finding.status` itself.
7. **Human review** — the *only* mechanism that can assert
   `VERIFIED`/`PARTIALLY_VERIFIED`/`NOT_APPLICABLE`; free-text reviewer
   identity (no auth system exists anywhere in this project); full audit
   trail via `FindingReview`.
8. **Reports** — a printable, per-scan HTML report aggregating findings by
   severity/status/framework plus review coverage; enforces the
   no-score/no-percentage constraint as a direct regression test, not just
   convention.
9. **Auto remediation** (this phase) — `RemediationAgent` suggests a
   concrete unified-diff code fix for one finding's flagged location,
   grounded in real downloaded file content; always a copy-paste artifact,
   never applied automatically.

Across all 9 phases: zero new Celery tasks were added after Phase 5 (a
deliberate architectural choice, avoiding the Windows-specific dual-restart
requirement `task_routes` changes would otherwise force), the automation
layer never once asserts positive compliance on its own, and every phase
was verified against the real running Docker+FastAPI+Celery stack — not
just mocked tests — with at least one genuine, previously-unknown bug
found and fixed via that live verification in Phases 6 and 9.
