"""Prompt template detection — a string/f-string assigned to a
prompt-shaped variable name, or passed as the first argument to a
detected inference call. Confidence is boosted when the file also
imports a detected AI/ML library (corroborating signal), same
two-tier-confidence posture `cryptography_rules.py` established.
"""

from __future__ import annotations

import ast
import re

from app.services.ai_analysis import ai_imports
from app.services.ai_analysis.base import FunctionRule, RuleContext, RuleHit
from app.services.ai_analysis.inference_detection import INFERENCE_METHOD_NAMES
from app.services.security_analysis import ast_utils

_PROMPT_NAME_RE = re.compile(r"(prompt|template|system_prompt|instructions)", re.IGNORECASE)


def _is_string_or_fstring(node: ast.AST) -> bool:
    return (isinstance(node, ast.Constant) and isinstance(node.value, str)) or isinstance(
        node, ast.JoinedStr
    )


def _detect_assigned_prompt_variables(context: RuleContext, has_ai_import: bool) -> list[RuleHit]:
    hits = []
    for node in ast.walk(context.tree):
        if isinstance(node, ast.Assign):
            targets = node.targets
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
            value = node.value
        else:
            continue

        if value is None or not _is_string_or_fstring(value):
            continue
        for target in targets:
            if not (isinstance(target, ast.Name) and _PROMPT_NAME_RE.search(target.id)):
                continue
            line_start, line_end = ast_utils.line_range(node)
            hits.append(
                RuleHit(
                    title="Prompt template detected",
                    status="REQUIRES_HUMAN_REVIEW",
                    severity="LOW",
                    confidence="medium" if has_ai_import else "low",
                    summary=f"'{target.id}' looks like an LLM prompt/instruction template.",
                    reasoning=(
                        f"Line {line_start} assigns a string to '{target.id}', a name "
                        "suggesting an LLM prompt or system-instruction template."
                    ),
                    recommendation="Ensure prompts are reviewed for injection risks and "
                    "that embedded instructions are documented as part of the AI system's "
                    "intended purpose.",
                    line_start=line_start,
                    line_end=line_end,
                )
            )
    return hits


def _detect_inline_prompt_args(context: RuleContext, has_ai_import: bool) -> list[RuleHit]:
    hits = []
    for node in ast.walk(context.tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr not in INFERENCE_METHOD_NAMES:
            continue
        if not node.args or not _is_string_or_fstring(node.args[0]):
            continue
        line_start, line_end = ast_utils.line_range(node)
        hits.append(
            RuleHit(
                title="Prompt template detected",
                status="REQUIRES_HUMAN_REVIEW",
                severity="LOW",
                confidence="medium" if has_ai_import else "low",
                summary=f"Line {line_start} passes a string literal directly to "
                f"'.{node.func.attr}(...)'.",
                reasoning=(
                    f"Line {line_start} passes a string/f-string as the first argument to "
                    "a call shaped like a model-inference method — a likely inline prompt."
                ),
                recommendation="Ensure prompts are reviewed for injection risks and that "
                "embedded instructions are documented as part of the AI system's intended "
                "purpose.",
                line_start=line_start,
                line_end=line_end,
            )
        )
    return hits


def _detect_python(context: RuleContext) -> list[RuleHit]:
    if context.tree is None:
        return []
    has_ai_import = bool(ai_imports.detect_ai_imports(context))
    return _detect_assigned_prompt_variables(context, has_ai_import) + _detect_inline_prompt_args(
        context, has_ai_import
    )


RULES = [
    FunctionRule(
        "AI-PROMPT-PY",
        "prompt_detection",
        "LOW",
        _detect_python,
        evidence_source_type="ast_analysis",
    ),
]
