"""Hardcoded-credential detection. Python gets a real AST check —
distinguishing an actual string-literal assignment from a call/lookup
(`os.environ.get(...)`, `settings.secret_key`) is the single biggest
false-positive source a bare keyword grep would hit, and it falls out for
free by only matching `ast.Constant` string values, never `ast.Call`
values. Every other language falls back to a conservative regex with a
lower confidence ceiling, since there's no AST to rule out an env-lookup
shape there.
"""

from __future__ import annotations

import ast
import re

from app.services.security_analysis import ast_utils
from app.services.security_analysis.base import FunctionRule, RuleContext, RuleHit
from app.services.security_analysis.redaction import redact_secret

_SENSITIVE_NAME_RE = re.compile(
    r"(password|secret|token|api[_-]?key|apikey|credential|passwd|pwd)", re.IGNORECASE
)
_PLACEHOLDER_VALUES = {"changeme", "xxxxxxxx", "your-secret-here", "placeholder", "todo", "fixme"}
_MIN_VALUE_LENGTH = 4

_GENERIC_ASSIGNMENT_RE = re.compile(
    r"""(password|secret|token|api[_-]?key)\s*[:=]\s*["']([^"']{4,})["']""", re.IGNORECASE
)


def _is_placeholder(value: str) -> bool:
    stripped = value.strip("<>{} ").lower()
    return stripped in _PLACEHOLDER_VALUES or len(value) < _MIN_VALUE_LENGTH


def _detect_python(context: RuleContext) -> list[RuleHit]:
    if context.tree is None:
        return []

    hits = []
    for node in ast.walk(context.tree):
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign) and node.target is not None:
            targets = [node.target]
        else:
            continue

        for target in targets:
            if not isinstance(target, ast.Name) or not _SENSITIVE_NAME_RE.search(target.id):
                continue
            value_node = node.value
            # Only a literal string constant counts — a `Call` (env lookup,
            # settings access, function call) is excluded by construction,
            # not by a separate check.
            if not (isinstance(value_node, ast.Constant) and isinstance(value_node.value, str)):
                continue
            value = value_node.value
            if _is_placeholder(value):
                continue

            line_start, line_end = ast_utils.line_range(node)
            snippet = ast_utils.source_segment(context.text, node)
            hits.append(
                RuleHit(
                    title="Hardcoded credential literal",
                    status="POTENTIAL_NON_COMPLIANCE",
                    severity="HIGH",
                    confidence="high",
                    summary=f"'{target.id}' is assigned a literal string value.",
                    reasoning=(
                        f"Line {line_start} assigns a string literal (not an environment "
                        f"lookup or function call) to '{target.id}', a name suggesting "
                        "credential material."
                    ),
                    recommendation="Load this value from an environment variable or secret "
                    "manager instead of a literal in source code.",
                    line_start=line_start,
                    line_end=line_end,
                    snippet=redact_secret(snippet),
                )
            )
    return hits


def _detect_generic_regex(context: RuleContext) -> list[RuleHit]:
    if context.tree is not None:
        return []  # Python already covered by the AST rule above.

    hits = []
    for i, line in enumerate(context.text.splitlines(), start=1):
        match = _GENERIC_ASSIGNMENT_RE.search(line)
        if not match or _is_placeholder(match.group(2)):
            continue
        hits.append(
            RuleHit(
                title="Possible hardcoded credential",
                status="REQUIRES_HUMAN_REVIEW",
                severity="MEDIUM",
                confidence="medium",
                summary=f"Line {i} looks like a credential assigned as a literal value.",
                reasoning=(
                    "A regex match, not an AST check (this file isn't Python) — cannot "
                    "distinguish a literal value from an environment-variable lookup with "
                    "the same textual shape, so this is lower confidence than the Python "
                    "equivalent."
                ),
                recommendation="Confirm whether this is a literal credential; if so, load it "
                "from an environment variable or secret manager instead.",
                line_start=i,
                line_end=i,
                snippet=redact_secret(match.group(2)),
            )
        )
    return hits


RULES = [
    FunctionRule(
        "SEC-CRED-PY-HARDCODED",
        "authentication",
        "HIGH",
        _detect_python,
        evidence_source_type="ast_analysis",
    ),
    FunctionRule("SEC-CRED-GENERIC-REGEX", "authentication", "MEDIUM", _detect_generic_regex),
]
