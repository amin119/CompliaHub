"""Agentic/tool-calling pattern detection — generic library-level shapes
(a `@tool` decorator, a call to `bind_tools`/`add_node`/`add_edge`/
`create_react_agent`/`initialize_agent`, or a `StateGraph(...)`
construction), not keyed to this project's own agent's node names. This
project's own `app/services/agent.py` uses none of these patterns (a
plain `StateGraph` with `condense_question`/`plan`/`retrieve` node names,
no `@tool`/`bind_tools`) — confirming genericizing here is necessary, not
just good practice, since a rule keyed to this codebase's own shape would
detect nothing in *other* repositories.
"""

from __future__ import annotations

import ast

from app.services.ai_analysis.base import FunctionRule, RuleContext, RuleHit
from app.services.security_analysis import ast_utils

_AGENTIC_CALL_NAMES = {
    "bind_tools",
    "add_node",
    "add_edge",
    "create_react_agent",
    "initialize_agent",
}


def _decorator_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    names: set[str] = set()
    for dec in node.decorator_list:
        target = dec.func if isinstance(dec, ast.Call) else dec
        if isinstance(target, ast.Name):
            names.add(target.id)
        elif isinstance(target, ast.Attribute):
            names.add(target.attr)
    return names


def _detect_python(context: RuleContext) -> list[RuleHit]:
    if context.tree is None:
        return []

    hits: list[RuleHit] = []
    for node in ast.walk(context.tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and "tool" in _decorator_names(
            node
        ):
            line_start, line_end = ast_utils.line_range(node)
            hits.append(
                RuleHit(
                    title="Agentic/tool-calling pattern detected",
                    status="REQUIRES_HUMAN_REVIEW",
                    severity="LOW",
                    confidence="medium",
                    summary=f"Function '{node.name}' is decorated as an agent tool.",
                    reasoning=(
                        f"Line {line_start} defines '{node.name}' with a `@tool`-shaped "
                        "decorator — a function exposed for an LLM agent to call."
                    ),
                    recommendation="Ensure tool-calling behavior has appropriate guardrails "
                    "(input validation, scope limits) and is covered by human oversight.",
                    line_start=line_start,
                    line_end=line_end,
                )
            )
        elif isinstance(node, ast.Call):
            name = None
            if isinstance(node.func, ast.Attribute) and node.func.attr in _AGENTIC_CALL_NAMES:
                name = node.func.attr
            elif isinstance(node.func, ast.Name) and node.func.id in (
                _AGENTIC_CALL_NAMES | {"StateGraph"}
            ):
                name = node.func.id
            if name is None:
                continue
            line_start, line_end = ast_utils.line_range(node)
            hits.append(
                RuleHit(
                    title="Agentic/tool-calling pattern detected",
                    status="REQUIRES_HUMAN_REVIEW",
                    severity="LOW",
                    confidence="medium",
                    summary=f"Line {line_start} calls '{name}(...)', an agent-framework "
                    "pattern.",
                    reasoning=(
                        f"Line {line_start} calls '{name}(...)', a pattern used to build "
                        "autonomous/tool-calling agents (LangGraph/LangChain-shaped)."
                    ),
                    recommendation="Ensure autonomous agent behavior has human oversight "
                    "and that tool access is scoped to what the system's intended purpose "
                    "requires.",
                    line_start=line_start,
                    line_end=line_end,
                )
            )
    return hits


RULES = [
    FunctionRule(
        "AI-AGENTIC-PY",
        "agentic_pattern_detection",
        "LOW",
        _detect_python,
        evidence_source_type="ast_analysis",
    ),
]
