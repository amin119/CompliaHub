"""Shared AST helpers for the Python-based rules (`hardcoded_credentials`,
`cryptography_rules`, `logging_rules`). Repository content is untrusted
input — a syntax error in a scanned file must skip that file's AST rules,
never fail the whole scan (the same posture `repo_extraction.py` already
takes toward malformed zip entries).
"""

from __future__ import annotations

import ast

ParentMap = dict[ast.AST, ast.AST]


def safe_parse(text: str) -> ast.AST | None:
    try:
        return ast.parse(text)
    except (SyntaxError, ValueError, RecursionError):
        return None


def build_parent_map(tree: ast.AST) -> ParentMap:
    parents: ParentMap = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    return parents


def enclosing_function_name(node: ast.AST, parents: ParentMap) -> str | None:
    """Walks up from `node` to the nearest enclosing function definition,
    used as a cheap proxy for "what is this code trying to do" — e.g.
    a hash call inside `hash_password(...)` vs. inside `cache_key(...)`.
    """
    current = parents.get(node)
    while current is not None:
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return current.name
        current = parents.get(current)
    return None


def assigned_variable_name(node: ast.AST, parents: ParentMap) -> str | None:
    """Walks up from `node` to the nearest enclosing simple assignment and
    returns the target's name — e.g. for `digest = hashlib.md5(data)`,
    called with the `Call` node, returns `"digest"`. Only handles the
    common single-target-Name case; anything more complex (tuple unpacking,
    attribute targets) returns `None` rather than guessing.
    """
    current: ast.AST | None = node
    while current is not None:
        if isinstance(current, ast.Assign) and len(current.targets) == 1:
            target = current.targets[0]
            if isinstance(target, ast.Name):
                return target.id
            return None
        if isinstance(current, ast.AnnAssign) and isinstance(current.target, ast.Name):
            return current.target.id
        current = parents.get(current)
    return None


def line_range(node: ast.AST) -> tuple[int | None, int | None]:
    start = getattr(node, "lineno", None)
    end = getattr(node, "end_lineno", start)
    return start, end


def source_segment(text: str, node: ast.AST) -> str:
    """Best-effort single-line-or-short excerpt for a snippet — never the
    whole file. Falls back to an empty string if `ast.get_source_segment`
    can't resolve it (e.g. a synthesized node).
    """
    segment = ast.get_source_segment(text, node)
    if segment is None:
        return ""
    # Cap length defensively — a pathological one-line statement shouldn't
    # blow up Evidence.snippet.
    return segment if len(segment) <= 300 else segment[:300] + "…"
