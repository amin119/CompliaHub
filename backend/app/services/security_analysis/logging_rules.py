"""Sensitive-data-in-logs detection — the `logger.info(user.email)` shape
called out directly in the compliance-scanner spec. Python AST only:
finds a call to a logger-shaped object whose arguments reference an
attribute (`user.email`) or reference one inside an f-string, where the
attribute name looks sensitive.
"""

from __future__ import annotations

import ast
import re

from app.services.security_analysis import ast_utils
from app.services.security_analysis.base import FunctionRule, RuleContext, RuleHit

_HIGH_SENSITIVITY_ATTRS = {"password", "token", "secret", "ssn"}
_SENSITIVE_ATTR_RE = re.compile(
    r"^(email|password|token|secret|ssn|credit_card|phone)$", re.IGNORECASE
)


def _detect_python(context: RuleContext) -> list[RuleHit]:
    if context.tree is None:
        return []

    hits = []
    for node in ast.walk(context.tree):
        if not isinstance(node, ast.Call):
            continue
        method = ast_utils.is_logger_call(node)
        if method is None:
            continue

        sensitive_attrs: list[str] = []
        for arg in list(node.args) + [kw.value for kw in node.keywords]:
            sensitive_attrs.extend(ast_utils.attribute_names_matching(arg, _SENSITIVE_ATTR_RE))
        if not sensitive_attrs:
            continue

        confidence = (
            "high"
            if any(attr.lower() in _HIGH_SENSITIVITY_ATTRS for attr in sensitive_attrs)
            else "medium"
        )
        severity = "HIGH" if confidence == "high" else "MEDIUM"
        line_start, line_end = ast_utils.line_range(node)
        attrs_label = ", ".join(sorted(set(sensitive_attrs)))
        hits.append(
            RuleHit(
                title="Sensitive data passed to a logging call",
                status="POTENTIAL_NON_COMPLIANCE",
                severity=severity,
                confidence=confidence,
                summary=f"logger.{method}(...) call includes a sensitive attribute: {attrs_label}.",
                reasoning=(
                    f"Line {line_start} calls a logging method with an argument accessing "
                    f"'{attrs_label}' — logs are frequently retained, shipped to third-party "
                    "aggregators, or accessible to more people than the data's original "
                    "purpose intended."
                ),
                recommendation="Remove the sensitive field from the log line, or log a "
                "redacted/hashed identifier instead of the raw value.",
                line_start=line_start,
                line_end=line_end,
                snippet=ast_utils.source_segment(context.text, node),
            )
        )
    return hits


RULES = [
    FunctionRule(
        "SEC-LOG-SENSITIVE-PY",
        "logging",
        "MEDIUM",
        _detect_python,
        evidence_source_type="ast_analysis",
    ),
]
