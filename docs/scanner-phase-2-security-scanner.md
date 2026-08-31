# Compliance Scanner — Phase 2: Deterministic Security Scanner

## Goal

Produce real, evidence-based findings from a scanned repository — secrets,
hardcoded credentials, weak cryptography, sensitive-data logging,
dependency risk, insecure configuration — with zero LLM calls. Every
finding traces back to concrete `Evidence` (file, line range, redacted
snippet). Never a binary compliant/non-compliant verdict: every rule
writes either `POTENTIAL_NON_COMPLIANCE` or `REQUIRES_HUMAN_REVIEW`, per
the compliance-scanner spec's own status vocabulary.

## What was built

**Models** (`app/models/scan.py`): `Finding` (scan_id FK, `framework`
nullable — stays `NULL` throughout this phase, category/rule_id/title/
status/severity/confidence/summary/reasoning/recommendation,
`human_review_required` computed as `status == REQUIRES_HUMAN_REVIEW or
severity == CRITICAL`). `Evidence` gained a nullable `finding_id` FK
(`ondelete="SET NULL"`) — a plain one-to-many from `Finding`'s side, not a
join table, matching `Evidence.repository_file_id`'s existing shape.
`Scan` gained `findings_status`/`findings_error_message`, a second,
independent status track mirroring `Document.graph_status`. Migration
`0005_security_findings.py`.

**Rule engine** (`app/services/security_analysis/`): a flat in-code
registry (`registry.py`'s `ALL_RULES`), not YAML-configurable — the same
scope-down pattern this project used for Phase 3's flat Leiden partition.
`base.py` defines `RuleContext`/`RuleHit`/`SecurityRule`/`FunctionRule`;
`ast_utils.py` has a safe `ast.parse` wrapper plus nearest-enclosing-
function/variable-name helpers; `redaction.py`'s `redact_secret` is used
everywhere a rule captures a matched secret substring.

**Six rule modules, all stdlib-only** (`ast`, `re`, `math` — zero new
dependencies):
- `secrets.py` — AWS key/PEM header/GitHub token/Slack token regexes +
  Shannon-entropy check on sensitively-named assignments.
- `hardcoded_credentials.py` — real Python AST (excludes `Call`-valued
  assignments like `os.environ.get(...)`, the biggest false-positive
  source) + a lower-confidence regex fallback for other languages.
- `cryptography_rules.py` — MD5/SHA1/DES/ECB detection via AST, severity
  scaled by nearest enclosing function/variable name (`hash_password` →
  HIGH, `cache_key` → LOW, not suppressed either way).
- `logging_rules.py` — AST detection of `logger.*(user.email)`-shaped
  calls.
- `dependencies.py` — static-only (confirmed with the user: no OSV.dev or
  any network call this phase) unpinned-version detection in
  `requirements.txt`/`package.json`.
- `insecure_config.py` — Dockerfile-no-USER, `privileged: true`,
  `DEBUG=true`, wildcard CORS.

**Pipeline**: a third chained task, `run_security_analyzers_task`, tracked
via `scan_stage`'s new `status_field`/`error_field` override
(`findings_status`/`findings_error_message`) instead of `status`/
`error_message` — same independent-track rationale `pipeline_stage`
already documents for `Document.graph_status`.

**API**: `GET /scans/{id}/findings` (severity/status/category filters),
`GET /scans/{id}/findings/{finding_id}` (with full evidence).

**Frontend**: `Finding`/`FindingDetail` types + `getScanFindings`/
`getScanFinding` in `api.ts`; a `SeverityBadge` component (sibling to
`StatusBadge`, different semantics); a Files/Findings tab toggle on the
scan detail page with a severity-count summary row.

## Real bugs found and fixed — live verification, not assumed correct

Every one of these was caught by actually running the pipeline against a
real repository, not by code review:

1. **Missing chain-thread on the second stage.** `detect_frameworks_task`
   returned `None`; adding a third chained stage after it meant the third
   stage would have received two positional args (the `None` plus its own
   explicit arg) — the exact `TypeError` class Phase 1 already hit once.
   Fixed before it ever ran, by returning `scan_id` from
   `detect_frameworks_task` and removing the explicit arg from its own
   `.s()` call in the chain — this was caught in code review this time,
   already knowing to look for it.

2. **The real one: a missing `celery_app.py` `task_routes` entry.**
   `run_security_analyzers_task` was never added to `task_routes`, so
   Celery silently routed it to the default `"celery"` queue — which
   nothing in this project's docker-compose setup consumes. Every scan's
   third stage sat forever at `findings_status: "not_started"`, with
   `POST /scans` returning 201 and the first two stages completing
   normally, so nothing *looked* broken until specifically checking
   whether findings ever appeared. Diagnosed by inspecting Redis directly
   (`LLEN celery` showed 3 stuck messages; `LLEN scanner` showed 0).
   **A second, sharper gotcha inside this same bug**: fixing the
   `task_routes` dict in `celery_app.py` and restarting the FastAPI
   process was *not* sufficient — Celery's `chain()` dispatches each
   callback stage's `apply_async()` from *inside the worker process* that
   just finished the prior stage, using that worker's own in-memory
   config, not the original producer's. The already-running worker had to
   be restarted too, separately, after the fix. Both processes needed a
   fresh start; restarting only one silently continued misrouting.
   Documented as a standing gotcha: **any change to `task_routes` requires
   restarting every long-running process that either calls
   `.apply_async()` or dispatches a chain callback — the FastAPI host
   process and every Celery worker, not just whichever one "obviously"
   owns the change.**

3. **`Evidence.source_type` mislabeled by file, not by rule.** The task
   set `source_type="ast_analysis" if tree is not None else
   "static_pattern"` — based on whether the *file* happened to parse as
   Python, not whether the *specific rule* that produced the hit actually
   used the AST. A regex-based rule (e.g. the AWS-key pattern in
   `secrets.py`) running against a Python file was mislabeled
   `"ast_analysis"`. Caught by inspecting a real finding's evidence
   payload during live verification, not by a unit test (the unit tests
   don't assert on `source_type` at all — a real gap this call-out is
   itself documenting). Fixed by moving `evidence_source_type` onto each
   `SecurityRule`/`FunctionRule` itself (defaulting to `"static_pattern"`,
   explicitly `"ast_analysis"` on the three AST-based rules) instead of
   inferring it from the file.

## Explicitly out of scope for this phase

GDPR/ISO27001/ISO42001 framework mapping (`Finding.framework` stays
`NULL`). LLM-based finding validation (`FindingValidationAgent`) — a later
phase. A real risk-scoring formula beyond severity+confidence as
independent fields. Remediation beyond a static one-line `recommendation`
per rule. Full multi-language AST (Python only; every other language is
regex-only, deliberately lower confidence). YAML-based rule
configuration. Any dependency-vulnerability database integration
(OSV.dev or otherwise) — confirmed deferred by the user.

## Verification

- **60 new unit tests, all passing**: 52 across the six rule modules +
  `test_redaction.py` (secrets/hardcoded-credentials/cryptography/
  logging/dependencies/insecure-config, each with true-positive and
  false-positive-exclusion cases), 2 new `scan_stage` status/error-field
  override cases, 6 `test_findings_api.py` real-infra integration cases
  (end-to-end generation, redacted evidence snippet, category/severity
  filtering, cross-scan 404, idempotent rerun).
- **Full backend suite: 211 passed** (up from 151 at the end of Phase 1).
- **Live end-to-end, confirmed working after a complete stack restart**
  (not just a warm dev process): a real sample repository (a hardcoded
  AWS example key, an MD5 call inside a `hash_password`-named function, a
  `logger.info(user.email)` call, an unpinned `requests` line) uploaded
  through the real running API produced exactly the 4 expected findings —
  `secrets`/CRITICAL, `cryptography`/HIGH (context-aware, correctly
  elevated by the `hash_password` name), `logging`/MEDIUM,
  `dependencies`/LOW. The secrets finding's evidence `snippet` was
  confirmed redacted (`AKIA…MPLE`, never the full key) in the actual API
  response, and `source_type` confirmed correct per rule
  (`static_pattern` for the regex-based secrets hit, `ast_analysis` for
  the AST-based crypto hit) after bug #3's fix.
- Frontend `pnpm lint`/`pnpm build` clean; `/scanner/[scanId]` compiles
  with the new Files/Findings tab toggle. Not yet screenshot-verified in
  a real browser for this phase (a screenshot pass was in progress but
  interrupted) — flagged honestly rather than claimed done; the API layer
  it renders has been verified for real, but the rendered UI itself has
  only been confirmed via a clean build, not an actual browser screenshot.
