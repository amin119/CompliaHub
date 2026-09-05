"""Phase 9 (final): Auto Remediation — `RemediationAgent`, suggesting a
concrete code fix for one Finding's flagged location, grounded in the real
source it points at (unlike Phase 6's `FindingValidationAgent`, which never
touches MinIO — a code *suggestion* needs real surrounding code, not just
`Evidence.snippet`'s short excerpt).

Deliberately narrow, same restraint as Phase 6: this agent never touches
`Finding.status` or `Finding.recommendation`. It only ever adds a new
`Evidence` row. No git access, no PR, no auto-apply — the generated diff is
always a copy-paste artifact for a human to review and apply themselves
(see docs/scanner-phase-9-auto-remediation.md's "explicitly out of scope"
for why real git write-back is not this phase's job).
"""

from __future__ import annotations

import difflib
import re
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

from google import genai
from google.genai import errors, types
from minio import Minio
from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.scan import Evidence, Finding, RepositoryFile
from app.services import scan_storage

_CONTEXT_MARGIN_LINES = 15
_MAX_RETRIES = 3
_RETRY_BASE_DELAY_SECONDS = 2.0

_SYSTEM_PROMPT = (
    "You are suggesting a concrete code fix for one automated compliance/"
    "security finding produced by a deterministic code-pattern scanner. "
    "You will be given the finding's own description and a window of real "
    "source code surrounding the flagged lines.\n\n"
    "Your suggested_code must be a full replacement for the ENTIRE code "
    "window you were given — not just the flagged line(s) — preserving "
    "every line outside the fix unchanged, so it can be diffed cleanly "
    "against the original window. Keep the same indentation style and "
    "line-ending convention as the input.\n\n"
    "problem_explanation: 1-3 sentences on why the ORIGINAL code is a "
    "genuine concern (not a restatement of the finding's summary).\n\n"
    "fix_explanation: 1-3 sentences on what your suggested_code changes "
    "and why that resolves the concern.\n\n"
    "confidence: 'high' only when the fix is unambiguous and mechanical "
    "(e.g. swap a weak hash function for a strong one); 'low' whenever the "
    "real fix depends on context you don't have (business logic, "
    "surrounding architecture, secrets-management infra you can't see) — "
    "state that limitation in fix_explanation rather than guessing.\n\n"
    "You are not certifying compliance and must never claim the fix makes "
    "the code 'compliant' or 'secure' — only that it addresses this "
    "specific flagged pattern."
)


class NoLocatableEvidenceError(Exception):
    """Raised when a Finding has no Evidence row with a concrete file_path
    to generate a code suggestion against — the common, expected case for
    GDPR organizational findings, ISO27001 control-assessment findings, and
    any finding whose only evidence is `source_type` in
    ("repo_aggregate", "llm_reasoning", "control_mapping") with
    `file_path=None`. Callers must surface this as an explicit "nothing to
    suggest a fix for" state, never call the remediation LLM with no real
    code to anchor on — same discipline `NoStandardsContextError` enforces
    for the validation agent.
    """


@dataclass
class FixTarget:
    evidence: Evidence
    repository_file: RepositoryFile
    window_start_line: int
    window_end_line: int
    window_text: str


def locate_fix_target(db: Session, client: Minio, finding: Finding) -> FixTarget:
    """Picks the FIRST Evidence row with `file_path`/`line_start` set — one
    finding maps to one flagged location in the overwhelming common case
    (Phase 2's rules each emit one Evidence row per match), so a single,
    unambiguous target keeps the suggested fix meaningful; a multi-location
    "fix" spanning several files/snippets is exactly the "multi-file
    refactor" this phase is scoped out of. Resolves it to the matching
    `RepositoryFile` for this scan, downloads real content from MinIO (same
    `scan_storage.download_object` pattern the analyzer tasks use), and
    slices a `±_CONTEXT_MARGIN_LINES` window around the flagged lines.
    """
    locatable = next(
        (e for e in finding.evidence if e.file_path is not None and e.line_start is not None),
        None,
    )
    if locatable is None:
        raise NoLocatableEvidenceError(
            "This finding has no evidence pointing at a specific file/line — there is no "
            "concrete code location to generate a fix suggestion against. This is expected "
            "for organizational/governance findings (e.g. GDPR policy-presence checks, "
            "ISO 27001 control assessments) that aren't tied to a single code location."
        )

    repository_file = db.scalar(
        select(RepositoryFile).where(
            RepositoryFile.scan_id == finding.scan_id,
            RepositoryFile.relative_path == locatable.file_path,
        )
    )
    if repository_file is None or not repository_file.content_stored:
        raise NoLocatableEvidenceError(
            f"'{locatable.file_path}' is no longer available in storage for this scan "
            "(binary, oversized, or otherwise not content-stored) — no source to generate "
            "a fix suggestion against."
        )

    raw = scan_storage.download_object(client, repository_file.minio_object_key)
    file_content = raw.decode("utf-8", errors="replace")
    lines = file_content.splitlines()

    line_start = locatable.line_start
    line_end = locatable.line_end or locatable.line_start
    window_start = max(1, line_start - _CONTEXT_MARGIN_LINES)
    window_end = min(len(lines), line_end + _CONTEXT_MARGIN_LINES)
    window_text = "\n".join(lines[window_start - 1 : window_end])

    return FixTarget(
        evidence=locatable,
        repository_file=repository_file,
        window_start_line=window_start,
        window_end_line=window_end,
        window_text=window_text,
    )


def build_unified_diff(
    file_path: str,
    window_start_line: int,
    original_window_text: str,
    suggested_code: str,
    context_lines: int = 3,
) -> str:
    """Turns an original code window + its suggested replacement into a
    real unified diff string, using stdlib `difflib` for the actual diff
    computation (every `+`/`-` line is 100% difflib's own output — never
    hand-rolled). `difflib.unified_diff` has no "starting line number"
    parameter, so its hunk headers (`@@ -1,N +1,M @@`) are always
    window-relative; this rewrites just the two numeric header offsets by
    adding `window_start_line - 1`, producing real file-relative line
    numbers. Verified against real difflib output (a no-op case producing
    an empty diff, and a non-trivial window offset producing correctly-
    shifted headers) before this function was written.

    Both inputs are normalized to end with a trailing newline first: real
    file content windows (from `locate_fix_target`, which joins
    `str.splitlines()` output with "\n") and LLM-generated code commonly
    lack one on their last line, and without this, difflib's line for a
    replaced *final* line carries no line terminator — its text then runs
    directly into the following line with no separating newline once the
    diff lines are joined, corrupting the diff.
    """
    if original_window_text and not original_window_text.endswith("\n"):
        original_window_text += "\n"
    if suggested_code and not suggested_code.endswith("\n"):
        suggested_code += "\n"

    original_lines = original_window_text.splitlines(keepends=True)
    suggested_lines = suggested_code.splitlines(keepends=True)

    diff_lines = list(
        difflib.unified_diff(
            original_lines,
            suggested_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            n=context_lines,
            lineterm="\n",
        )
    )

    offset = window_start_line - 1
    hunk_header_re = re.compile(r"^@@ -(\d+)(,(\d+))? \+(\d+)(,(\d+))? @@")
    rewritten = []
    for line in diff_lines:
        match = hunk_header_re.match(line)
        if match:
            old_start = int(match.group(1)) + offset
            old_len = match.group(3)
            new_start = int(match.group(4)) + offset
            new_len = match.group(6)
            old_part = f"{old_start}" + (f",{old_len}" if old_len else "")
            new_part = f"{new_start}" + (f",{new_len}" if new_len else "")
            rewritten.append(f"@@ -{old_part} +{new_part} @@\n")
        else:
            rewritten.append(line)
    return "".join(rewritten)


class RemediationSuggestion(BaseModel):
    """An LLM's suggested code-level fix for one Finding's flagged
    location — NOT an applied change, NOT a compliance-status
    determination. Only ever backs a new Evidence row; never touches
    `Finding.status` or `Finding.recommendation`.
    """

    problem_explanation: str
    suggested_code: str
    fix_explanation: str
    confidence: str  # "high" | "medium" | "low"


class RemediationRateLimited(Exception):
    """Mirrors finding_validation.ValidationRateLimited — covers both
    actual rate limiting and transient server-side unavailability."""


class RemediationClient(Protocol):
    def remediate(self, prompt: str) -> RemediationSuggestion: ...


@lru_cache
def _sdk_client(api_key: str) -> genai.Client:
    # Deliberately duplicated (not imported) from finding_validation.py's
    # identical helper — this project's own established precedent is that
    # phase modules with the same adapter shape don't share code with each
    # other (different prompt/schema, no shared call site).
    return genai.Client(api_key=api_key)


class _GeminiRemediationClient:
    def __init__(self, api_key: str, model: str) -> None:
        self._client = _sdk_client(api_key)
        self._model = model

    def remediate(self, prompt: str) -> RemediationSuggestion:
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=_SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_schema=RemediationSuggestion,
                ),
            )
        except errors.ClientError as exc:
            if exc.code == 429:
                raise RemediationRateLimited(str(exc)) from exc
            raise
        except errors.ServerError as exc:
            raise RemediationRateLimited(str(exc)) from exc

        return RemediationSuggestion.model_validate_json(response.text)


def get_gemini_remediation_client() -> RemediationClient:
    settings = get_settings()
    return _GeminiRemediationClient(
        api_key=settings.gemini_api_key, model=settings.gemini_remediation_model
    )


def _build_prompt(finding: Finding, fix_target: FixTarget) -> str:
    evidence = fix_target.evidence
    flagged_end = evidence.line_end or evidence.line_start
    return (
        f"Finding: {finding.title}\n"
        f"Framework: {finding.framework or 'security (general)'}\n"
        f"Category: {finding.category}\n"
        f"Rule: {finding.rule_id}\n"
        f"Severity: {finding.severity}\n"
        f"Summary: {finding.summary}\n"
        f"Reasoning: {finding.reasoning}\n\n"
        f"File: {evidence.file_path} (showing lines "
        f"{fix_target.window_start_line}-{fix_target.window_end_line}, "
        f"flagged lines {evidence.line_start}-{flagged_end})\n\n"
        f"```\n{fix_target.window_text}\n```"
    )


def generate_remediation(
    finding: Finding, fix_target: FixTarget, client: RemediationClient | None = None
) -> RemediationSuggestion:
    """Generates a suggested fix for `finding`'s flagged location, grounded
    in `fix_target` (from `locate_fix_target`). `client` defaults to the
    real Gemini-backed adapter; pass a fake `RemediationClient` in tests.
    Retries on rate limits/transient server errors and on schema-
    validation failure, same shape as `finding_validation.validate_finding`.
    """
    client = client or get_gemini_remediation_client()
    prompt = _build_prompt(finding, fix_target)

    for attempt in range(_MAX_RETRIES):
        try:
            return client.remediate(prompt)
        except RemediationRateLimited:
            if attempt == _MAX_RETRIES - 1:
                raise
            time.sleep(_RETRY_BASE_DELAY_SECONDS * (2**attempt))
        except ValidationError:
            if attempt == _MAX_RETRIES - 1:
                raise
    raise AssertionError("unreachable")  # loop always returns or raises above


def persist_remediation(
    db: Session,
    finding: Finding,
    suggestion: RemediationSuggestion,
    fix_target: FixTarget,
    diff_text: str,
    model: str,
) -> Evidence:
    """Writes the suggestion as a new Evidence row using the already-
    reserved-in-spirit "llm_remediation" source_type (parallel to Phase 6's
    "llm_reasoning") — no schema change. Every re-suggest writes a new row
    (matching the codebase-wide clear-and-rebuild-with-new-UUIDs
    convention); `finding.status`/`finding.recommendation` are never
    touched here.
    """
    evidence = Evidence(
        scan_id=finding.scan_id,
        repository_file_id=fix_target.repository_file.id,
        finding_id=finding.id,
        source_type="llm_remediation",
        rule_id="llm_finding_remediation",
        file_path=fix_target.evidence.file_path,
        line_start=fix_target.evidence.line_start,
        line_end=fix_target.evidence.line_end,
        snippet=diff_text,
        description=f"{suggestion.problem_explanation}\n\n{suggestion.fix_explanation}",
        confidence=suggestion.confidence,
        evidence_metadata={
            "model": model,
            "target_file_path": fix_target.evidence.file_path,
            "target_line_start": fix_target.evidence.line_start,
            "target_line_end": fix_target.evidence.line_end,
            "window_start_line": fix_target.window_start_line,
            "window_end_line": fix_target.window_end_line,
            "confidence": suggestion.confidence,
        },
    )
    db.add(evidence)
    db.commit()
    db.refresh(evidence)
    return evidence
