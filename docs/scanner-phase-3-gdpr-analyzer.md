# Compliance Scanner — Phase 3: GDPR Analyzer

## Goal

Add GDPR-specific detection on top of Phase 2's security scanner: PII
field detection, GDPR-framed sensitive logging, third-party data flow,
cookies/tracking, and the spec's own required set of "cannot be verified
technically" organizational findings (lawful basis, DPIA, DPO, ROPA,
contracts, retention policy). Still deterministic — zero LLM calls,
matching Phase 6's reserved role for reasoning. `Finding.framework`
(defined since Phase 2, always `NULL` until now) starts being populated
with `"GDPR"`.

## What was built

**New package** `app/services/privacy_analysis/` — reuses `RuleContext`/
`RuleHit`/`FunctionRule` from `security_analysis/base.py` directly (zero
duplication); a separate `PRIVACY_RULES` registry rather than a shared one
with a per-rule `framework` field, since `framework` is a property of
*which registry's loop runs* in the Celery task, not something every rule
needs to repeat.

- `pii_patterns.py`/`pii_fields.py` — PII field-name detection via Python
  AST. The concrete "not a random variable" signal: only an attribute
  inside a *qualifying class body* is evidence (subclasses `Base`/
  `BaseModel`/`SQLModel`, calls `mapped_column`/`Column`, or — lower
  confidence — is `@dataclass`-decorated). A bare module-level variable or
  function parameter never fires. Two disjoint category sets:
  `data_minimisation` (ordinary PII) and `special_category_data` (Article
  9 data — health, biometric, SSN, etc. — always `severity="HIGH"`).
- `logging_pii.py` — a GDPR-framed overlay on Phase 2's `logging_rules.py`,
  reusing newly-public `ast_utils.is_logger_call`/`attribute_names_matching`
  helpers (moved out of `logging_rules.py`, which was refactored to use
  them too) with its own disjoint PII-only regex (excludes `password`/
  `token`/`secret`, which stay Phase 2's concern). `logger.info(user.email)`
  fires *two* Finding rows — Phase 2's unchanged security finding
  (`framework=None`) and this new GDPR one (`framework="GDPR"`) — by
  design, not a duplicate.
- `third_party.py` — third-party import detection (AI/LLM, storage,
  analytics, payment, email providers) via AST, plus cookie/tracking
  detection (`response.set_cookie(...)` via AST for Python,
  regex-fallback for JS/TS/HTML).
- `repo_level_checks.py` — plain functions, not `FunctionRule`s, since
  these are aggregate facts across the whole file set (does a deletion
  route exist anywhere? does a privacy-policy doc exist anywhere?), not
  per-file. Emits the six fixed organizational findings every scan
  (confidence softened `low → medium` when a privacy-shaped doc is found,
  never suppressed — this phase never parses the doc's prose), plus one
  absence-only `data_subject_rights` finding when no deletion route is
  found anywhere (presence is never reported, only absence).
- `repo_discovery.py` gained `privacy.md`/`privacy-policy.md`/
  `privacy_policy.md`/`data-protection.md` in its filename→component-type
  map — without this, a repo's own `PRIVACY.md` fell through to
  `"unknown"`, so the spec's "unless documentary evidence exists" carve-out
  could never trigger for the single most common real case.

**Pipeline**: a fourth chained Celery task, `run_privacy_analyzers_task`,
tracked on a third independent status track, `Scan.privacy_status`/
`privacy_error_message` (migration `0006_gdpr_findings.py`) — a genuinely
separate failure domain from `findings_status`, for a concrete reason:
the two tasks have different idempotent-clear scopes (see the bug below).

**API/frontend**: `GET /scans/{id}/findings` gained a `framework` filter;
`ScanResponse` gained `privacy_status`/`privacy_error_message`; the scan
detail page's Findings tab gained a Framework column and a framework
filter-chip row (computed client-side from whichever values are present,
the same pattern the Files tab already uses for component types — scales
to a third framework later with no rework).

## Real bugs found and fixed — by review and by live testing, not assumed correct

This phase was substantially built, then reviewed end-to-end (the user
asked for a review before calling it done) — three real bugs were caught
this way, none of them by the unit tests that already existed at review
time:

1. **The bidirectional delete-scoping bug, caught in design review before
   any code ran.** Phase 2's `run_security_analyzers_task` cleared *every*
   `Finding` row for a scan before rebuilding, filtered only by `scan_id`.
   The moment Phase 3 writes a second framework's findings to the same
   table, that becomes a real data-loss bug in both directions: rerunning
   Phase 2's task would wipe every GDPR finding, and rerunning Phase 3's
   task must not wipe Phase 2's. Fixed symmetrically: Phase 2's clear is
   now scoped to `Finding.framework.is_(None)`, Phase 3's to
   `Finding.framework == "GDPR"` — each with its `Evidence` rows cleared
   via a `finding_id IN (...)` scalar subquery rather than a bare
   `scan_id` match, to avoid orphaning the other framework's evidence.
   Live-verified with a dedicated regression test
   (`test_privacy_findings_api.py`'s two rerun tests) confirming each
   task's rerun leaves the other framework's finding count untouched.

2. **A category-assignment bug, caught by the first live upload during
   review — not by any unit test.** `pii_fields.py`'s single AST-walking
   rule produces hits of two different logical categories
   (`data_minimisation` vs. `special_category_data`) depending on which
   field matched, but `Finding.category` was always taken from the rule's
   one fixed registry-level `category` string. Every special-category hit
   (health, biometric, SSN, etc.) was silently written to the database as
   `"data_minimisation"` — the wrong category, though the correct elevated
   `severity="HIGH"` (which *does* flow per-hit) partially masked it.
   Caught by uploading a real repo with an `ssn` field and inspecting the
   actual finding's `category` in the API response, not by reading the
   code. Fixed by adding an optional `category: str | None` field to
   `RuleHit` (the same per-hit-overrides-a-rule-default shape `severity`/
   `confidence`/`status` already use), set explicitly by `pii_fields.py`'s
   two detection paths, and read at both Celery task call sites via
   `hit.category or rule.category`. A dedicated regression test
   (`test_special_category_field_hit_carries_its_own_category`) locks
   this in.

3. **A fragile title-substring category lookup, caught by code review.**
   The repo-level fixed findings (which bypass the `FunctionRule` wrapper
   entirely, since they're aggregate, not per-file) had their `category`
   re-derived in `tasks/scan.py` by matching substrings of each finding's
   *title* against a hardcoded dictionary — a silent-breakage risk the
   moment a title's wording changed, with a defensive fallback that would
   have silently mis-categorized every repo-level finding as
   `"lawful_basis"` if a title ever stopped matching. Fixed by having
   `build_repo_level_findings` return `(category, RuleHit)` pairs
   directly — the category was already known at construction time in
   `repo_level_checks.py`'s own `_FIXED_FINDINGS` list; it just wasn't
   being threaded through.

A fourth, minor issue was also cleaned up during review: two SQLAlchemy
`SAWarning`s about coercing a `Subquery` into an `IN()` clause (both
delete-scoping queries used `.subquery()` where `.scalar_subquery()` is
the correct 2.0-style construct for a single-column `IN()` filter).

## Explicitly out of scope for Phase 3

ISO 27001/ISO 42001 mapping (later phase). Any LLM-based reasoning about
lawful basis, DPIA necessity, or a privacy policy's actual prose content —
Phase 6. Actual DPIA/ROPA generation. Full non-Python AST (Python-first,
regex fallback elsewhere, same as Phase 2). NLP-based PII detection
(finding PII *values* in free text, as opposed to PII-shaped *field
names* in structured code) — this phase is a field-name/structural
detector only, never a content classifier. `data_export` weak-signal
detection (no route-shape heuristic as clean as the `DELETE` verb check —
folded into the fixed findings' text instead). Parsing whether a cookie
banner actually works, or whether a privacy policy actually covers what
it needs to.

## Verification

- **39 unit/integration tests** across the privacy-analysis rule modules
  (PII fields, logging overlay, third-party/cookies, repo-level checks)
  plus the live-infra `test_privacy_findings_api.py`, all passing,
  including the regression tests written specifically for bugs #1 and #2
  above.
- **Full backend suite: 250 passed** (up from 211 at the end of Phase 2).
- **Live end-to-end, via the real queue-backed pipeline** (not eager
  mode): uploaded a real repository with both security-relevant content
  (AWS key, MD5-in-`hash_password`, `logger.info(user.email)`, unpinned
  dependency) and GDPR-relevant content (a SQLAlchemy-shaped model with
  `email`/`ssn` fields, a `cohere` import, a `set_cookie` call) through
  `POST /scans` on a freshly-restarted FastAPI process and Celery worker.
  Confirmed via Redis (`LLEN scanner` / `LLEN celery` both `0` after
  completion — no misrouting) and via `GET /scans/{id}/findings`: all
  four pipeline stages reached `"ready"`
  (`status`/`findings_status`/`privacy_status`), the `ssn` field's
  finding correctly shows `category: "special_category_data"` in the real
  database (not just in a test), and every expected GDPR category fired
  (`data_minimisation`, `special_category_data`, `third_party_processors`,
  `consent_mechanisms`, `security_of_processing`, plus the six
  organizational findings and the deletion-route absence finding).
- Frontend `pnpm lint`/`pnpm build` clean. The Findings tab's rendering
  itself has not been screenshot-verified in a real browser this
  phase — the API layer it renders on has been verified for real, the
  rendered UI has only been confirmed via a clean build.
