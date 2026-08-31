"""GDPR-framed sensitive-logging detection — the privacy-side overlay on
Phase 2's `security_analysis.logging_rules`.

This reuses the now-public `ast_utils.is_logger_call` /
`ast_utils.attribute_names_matching` mechanics with its own, deliberately
*disjoint* PII-only regex (`email|phone|address|ip_address|dob|ssn|
location`) — it excludes `password|token|secret`, which stay Phase 2's
concern.

The two-rows-not-a-duplicate behaviour is intentional and central to the
whole framework-column design:

  * `logger.info(user.email)` → Phase 2's rule still fires unchanged
    (`framework=None`, `category="logging"`) AND this rule also fires
    (`framework="GDPR"`, `category="security_of_processing"`). Two distinct
    `Finding` rows at the same evidence line, each independently filterable
    once the frontend framework column exists.
  * `logger.info(user.password)` → only Phase 2's rule fires (password is
    not in this rule's PII regex).
"""

from __future__ import annotations

import ast
import re

from app.services.privacy_analysis.base import FunctionRule, RuleContext, RuleHit
from app.services.security_analysis import ast_utils

# Disjoint from `logging_rules._SENSITIVE_ATTR_RE`: PII fields only. No
# password/token/secret — those are Phase 2's security concern, not a GDPR
# personal-data concern.
_PII_ATTR_RE = re.compile(
    r"^(email|phone|address|ip_address|dob|date_of_birth|ssn|location)$",
    re.IGNORECASE,
)


def _detect_python(context: RuleContext) -> list[RuleHit]:
    if context.tree is None:
        return []

    hits: list[RuleHit] = []
    for node in ast.walk(context.tree):
        if not isinstance(node, ast.Call):
            continue
        method = ast_utils.is_logger_call(node)
        if method is None:
            continue

        pii_attrs: list[str] = []
        for arg in list(node.args) + [kw.value for kw in node.keywords]:
            pii_attrs.extend(ast_utils.attribute_names_matching(arg, _PII_ATTR_RE))
        if not pii_attrs:
            continue

        line_start, line_end = ast_utils.line_range(node)
        attrs_label = ", ".join(sorted(set(pii_attrs)))
        hits.append(
            RuleHit(
                title="Personal data written to logs",
                status="POTENTIAL_NON_COMPLIANCE",
                severity="MEDIUM",
                confidence="medium",
                summary=f"logger.{method}(...) call logs personal data: {attrs_label}.",
                reasoning=(
                    f"Line {line_start} passes personal data ('{attrs_label}') to a logging "
                    "call. Under GDPR, logs are a form of processing: they are frequently "
                    "retained beyond the data's original purpose, shipped to third-party "
                    "aggregators, and accessible to more people than intended — which bears on "
                    "the security-of-processing and data-minimisation principles (Art. 5/32). "
                    "This is recorded separately from, and in addition to, the framework-"
                    "agnostic security finding for the same line."
                ),
                recommendation="Avoid logging personal data directly; log a "
                "redacted/pseudonymised identifier instead, and confirm log retention is "
                "bounded.",
                line_start=line_start,
                line_end=line_end,
                snippet=ast_utils.source_segment(context.text, node),
            )
        )
    return hits


RULES = [
    FunctionRule(
        "GDPR-LOG-PII-PY",
        "security_of_processing",
        "MEDIUM",
        _detect_python,
        evidence_source_type="ast_analysis",
    ),
]
