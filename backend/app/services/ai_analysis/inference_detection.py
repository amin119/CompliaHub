"""AI model inference/endpoint call detection — a call to a
common-inference-shaped method (`.generate(`, `.invoke(`, etc.) in a file
that also imports a detected AI/ML library. File-level co-occurrence, not
real dataflow tracing, same posture as `rag_detection.py`.
"""

from __future__ import annotations

import ast

from app.services.ai_analysis import ai_imports
from app.services.ai_analysis.base import FunctionRule, RuleContext, RuleHit
from app.services.security_analysis import ast_utils

# Shared with `prompt_detection.py` (a string passed as the first arg to
# one of these is a stronger prompt-template signal) — defined here as the
# canonical source so the two rules can't silently drift apart.
INFERENCE_METHOD_NAMES = frozenset(
    {"create", "generate", "chat", "complete", "invoke", "predict", "embed"}
)


def _detect_python(context: RuleContext) -> list[RuleHit]:
    if context.tree is None:
        return []
    if not ai_imports.detect_ai_imports(context):
        return []  # No AI/ML import in this file — a same-named method call elsewhere is noise.

    hits: list[RuleHit] = []
    seen_lines: set[int | None] = set()
    for node in ast.walk(context.tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr not in INFERENCE_METHOD_NAMES:
            continue
        line_start, line_end = ast_utils.line_range(node)
        if line_start in seen_lines:
            continue
        seen_lines.add(line_start)
        hits.append(
            RuleHit(
                title="AI model inference call detected",
                status="REQUIRES_HUMAN_REVIEW",
                severity="LOW",
                confidence="medium",
                summary=f"Line {line_start} calls '.{node.func.attr}(...)' in a file that "
                "imports an AI/ML library.",
                reasoning=(
                    f"Line {line_start} calls a method commonly used for model inference "
                    "(generation/completion/prediction), in a file that also imports a "
                    "detected AI/ML library — evidence of an active inference path."
                ),
                recommendation="Ensure model outputs are validated before use, and that "
                "this inference path is covered by the system's monitoring and evaluation "
                "processes.",
                line_start=line_start,
                line_end=line_end,
                snippet=ast_utils.source_segment(context.text, node),
            )
        )
    return hits


RULES = [
    FunctionRule(
        "AI-INFERENCE-PY",
        "inference_call_detection",
        "LOW",
        _detect_python,
        evidence_source_type="ast_analysis",
    ),
]
