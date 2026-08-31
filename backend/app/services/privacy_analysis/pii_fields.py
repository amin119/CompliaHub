"""PII field detection — the concrete "not a random variable" signal that
directly answers the spec's own warning against inferring GDPR processing
from a bare name match.

Only an attribute *inside a qualifying class body* is treated as evidence —
never a bare module-level variable, and never a function parameter. A
`ClassDef` qualifies if any of:

  * it subclasses one of `{Base, BaseModel, SQLModel}` by name (an ORM/
    schema model — its attributes are persisted/serialized fields), or
  * its body calls `mapped_column(...)` / `Column(...)` anywhere (a
    SQLAlchemy-mapped model even if the base class was aliased), or
  * (lower confidence) it's `@dataclass`-decorated.

Every hit's `reasoning` explicitly states that a field name alone doesn't
establish GDPR processing — matching the spec's own worked example
(`date_of_birth` → `category="data_minimisation"`,
`status="REQUIRES_HUMAN_REVIEW"`).

Non-Python files get the same conservative regex-fallback posture as
`cryptography_rules._detect_generic_regex`: only fires when
`context.tree is None`, confidence capped at `"low"`.
"""

from __future__ import annotations

import ast
import re

from app.services.privacy_analysis.pii_patterns import classify_field_name
from app.services.security_analysis.base import FunctionRule, RuleContext, RuleHit

_MODEL_BASE_NAMES = {"Base", "BaseModel", "SQLModel"}
_COLUMN_CALL_NAMES = {"mapped_column", "Column"}

_PII_ALWAYS_REVIEW_STATUS = "REQUIRES_HUMAN_REVIEW"

# The one sentence the spec insists must accompany every field-name hit —
# factored out so every code path (AST + regex fallback) says it identically.
_NAME_ALONE_CAVEAT = (
    "A field name alone does not establish GDPR processing — this is flagged "
    "for human review, not asserted as non-compliance."
)


def _decorator_names(node: ast.ClassDef) -> set[str]:
    names: set[str] = set()
    for dec in node.decorator_list:
        target = dec.func if isinstance(dec, ast.Call) else dec
        if isinstance(target, ast.Name):
            names.add(target.id)
        elif isinstance(target, ast.Attribute):
            names.add(target.attr)
    return names


def _base_names(node: ast.ClassDef) -> set[str]:
    names: set[str] = set()
    for base in node.bases:
        if isinstance(base, ast.Name):
            names.add(base.id)
        elif isinstance(base, ast.Attribute):
            names.add(base.attr)
    return names


def _body_calls_column(node: ast.ClassDef) -> bool:
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            func = sub.func
            if isinstance(func, ast.Name) and func.id in _COLUMN_CALL_NAMES:
                return True
            if isinstance(func, ast.Attribute) and func.attr in _COLUMN_CALL_NAMES:
                return True
    return False


def _class_qualification(node: ast.ClassDef) -> tuple[bool, str]:
    """Returns `(qualifies, confidence)`. A model base or a `mapped_column`/
    `Column` call is a high-confidence signal that the class's attributes
    are real persisted/serialized fields; a bare `@dataclass` is a
    lower-confidence signal (it could be a plain value object).
    """
    if _base_names(node) & _MODEL_BASE_NAMES or _body_calls_column(node):
        return True, "medium"
    if "dataclass" in _decorator_names(node):
        return True, "low"
    return False, "low"


def _field_names_in_class(node: ast.ClassDef) -> list[tuple[str, int]]:
    """Class-body attribute names paired with their line number. Only
    direct assignments/annotations in the class body count — nested
    function locals inside methods are not model fields.
    """
    results: list[tuple[str, int]] = []
    for stmt in node.body:
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            results.append((stmt.target.id, stmt.lineno))
        elif isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name):
                    results.append((target.id, stmt.lineno))
    return results


def _make_hit(
    field_name: str,
    category: str,
    line: int,
    class_name: str,
    confidence: str,
) -> RuleHit:
    is_special = category == "special_category_data"
    severity = "HIGH" if is_special else "MEDIUM"
    kind = (
        "an Article 9 special-category personal data field"
        if is_special
        else "a personal data field"
    )
    return RuleHit(
        title=(
            "Special-category personal data field"
            if is_special
            else "Personal data field"
        ),
        status=_PII_ALWAYS_REVIEW_STATUS,
        severity=severity,
        confidence=confidence,
        category=category,
        summary=f"'{field_name}' on model class '{class_name}' looks like {kind}.",
        reasoning=(
            f"Line {line} declares '{field_name}' as an attribute of class "
            f"'{class_name}', which is structured as a persisted/serialized data "
            f"model (an ORM/schema base or a mapped_column/Column call in its body). "
            f"That structural context — not the name in isolation — is why this is "
            f"treated as evidence of {kind}. " + _NAME_ALONE_CAVEAT
        ),
        recommendation=(
            "Confirm a lawful basis and retention period apply to this field, and that "
            "it's covered by the project's records of processing activities."
            if not is_special
            else "Special-category data needs an Article 9 condition in addition to a "
            "lawful basis; confirm one applies and that access is tightly scoped."
        ),
        line_start=line,
        line_end=line,
    )


def _detect_python(context: RuleContext) -> list[RuleHit]:
    if context.tree is None:
        return []

    hits: list[RuleHit] = []
    for node in ast.walk(context.tree):
        if not isinstance(node, ast.ClassDef):
            continue
        qualifies, confidence = _class_qualification(node)
        if not qualifies:
            continue
        for field_name, line in _field_names_in_class(node):
            category = classify_field_name(field_name)
            if category is None:
                continue
            hits.append(_make_hit(field_name, category, line, node.name, confidence))
    return hits


# Non-Python fallback: no class-body structural signal is available, so this
# is a much weaker check — it only looks at lines that syntactically *look*
# like a field/column declaration (a `:` or `=` after the name), and caps
# confidence at "low". Fires only when the AST path didn't run.
_FIELD_DECL_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*[:=]")


def _detect_generic_regex(context: RuleContext) -> list[RuleHit]:
    if context.tree is not None:
        return []  # Python already covered by the AST rule above.

    hits: list[RuleHit] = []
    for i, line in enumerate(context.text.splitlines(), start=1):
        match = _FIELD_DECL_RE.match(line)
        if not match:
            continue
        name = match.group(1)
        category = classify_field_name(name)
        if category is None:
            continue
        is_special = category == "special_category_data"
        hits.append(
            RuleHit(
                title=(
                    "Possible special-category personal data field"
                    if is_special
                    else "Possible personal data field"
                ),
                status=_PII_ALWAYS_REVIEW_STATUS,
                severity="HIGH" if is_special else "MEDIUM",
                confidence="low",
                summary=f"Line {i} declares a field named '{name}' resembling personal data.",
                reasoning=(
                    "A regex match, not an AST check (this file isn't Python) — no class-body "
                    "structural signal is available to confirm this is a real persisted field "
                    "rather than an unrelated variable. " + _NAME_ALONE_CAVEAT
                ),
                recommendation="Confirm whether this holds personal data and, if so, that a "
                "lawful basis and retention period apply.",
                line_start=i,
                line_end=i,
                category=category,
            )
        )
    return hits


RULES = [
    FunctionRule(
        "GDPR-PII-FIELD-PY",
        "data_minimisation",
        "MEDIUM",
        _detect_python,
        evidence_source_type="ast_analysis",
    ),
    FunctionRule("GDPR-PII-FIELD-REGEX", "data_minimisation", "MEDIUM", _detect_generic_regex),
]
