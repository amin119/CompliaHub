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

_LOGGER_NAME_RE = re.compile(r"^(logger|log|logging)$", re.IGNORECASE)
_LOG_METHODS = {"debug", "info", "warning", "error", "critical", "exception"}
_HIGH_SENSITIVITY_ATTRS = {"password", "token", "secret", "ssn"}
_SENSITIVE_ATTR_RE = re.compile(
    r"^(email|password|token|secret|ssn|credit_card|phone)$", re.IGNORECASE
)


def _is_logger_call(node: ast.Call) -> str | None:
    """Returns the log method name (`"info"`, etc.) if `node` calls a
    logger-shaped object, else `None`.
    """
    if not isinstance(node.func, ast.Attribute) or node.func.attr not in _LOG_METHODS:
        return None
    receiver = node.func.value
    if isinstance(receiver, ast.Name) and _LOGGER_NAME_RE.match(receiver.id):
        return node.func.attr
    if isinstance(receiver, ast.Attribute) and _LOGGER_NAME_RE.match(receiver.attr):
        return node.func.attr
    return None


def _sensitive_attrs_in(node: ast.AST) -> list[str]:
    found = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.Attribute) and _SENSITIVE_ATTR_RE.match(sub.attr):
            found.append(sub.attr)
    return found


def _detect_python(context: RuleContext) -> list[RuleHit]:
    if context.tree is None:
        return []

    hits = []
    for node in ast.walk(context.tree):
        if not isinstance(node, ast.Call):
            continue
        method = _is_logger_call(node)
        if method is None:
            continue

        sensitive_attrs: list[str] = []
        for arg in list(node.args) + [kw.value for kw in node.keywords]:
            sensitive_attrs.extend(_sensitive_attrs_in(arg))
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
