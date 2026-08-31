"""Shared AST helpers for the Python-based rules (`hardcoded_credentials`,
`cryptography_rules`, `logging_rules`, and Phase 3's `privacy_analysis`
rules, which import these unchanged — the helpers are already framework-
agnostic). Repository content is untrusted input — a syntax error in a
scanned file must skip that file's AST rules, never fail the whole scan
(the same posture `repo_extraction.py` already takes toward malformed zip
entries).
"""

from __future__ import annotations

import ast
import re

ParentMap = dict[ast.AST, ast.AST]

# Shared by both frameworks' logging rules (`security_analysis.logging_rules`
# and `privacy_analysis.logging_pii`): the mechanics of "is this call a
# logger call" and "which attribute names in this subtree match a regex" are
# framework-agnostic — only the sensitivity regex passed in is flavored. This
# lives here rather than being duplicated so a second framework's logging
# rule reuses the exact same call/attribute-walk logic (see Phase 3's
# extract-don't-duplicate note).
_LOGGER_NAME_RE = re.compile(r"^(logger|log|logging)$", re.IGNORECASE)
_LOG_METHODS = frozenset(
    {"debug", "info", "warning", "error", "critical", "exception"}
)


def is_logger_call(node: ast.Call) -> str | None:
    """Returns the log method name (`"info"`, etc.) if `node` calls a
    logger-shaped object (`logger.info(...)`, `self.logger.error(...)`),
    else `None`. Moved verbatim out of `logging_rules._is_logger_call` so
    the privacy-analysis logging rule can reuse it without duplicating the
    receiver/attribute-walk logic — confirmed safe since
    `test_security_rules_logging.py` only imports `_detect_python`, not the
    helper being moved.
    """
    if not isinstance(node.func, ast.Attribute) or node.func.attr not in _LOG_METHODS:
        return None
    receiver = node.func.value
    if isinstance(receiver, ast.Name) and _LOGGER_NAME_RE.match(receiver.id):
        return node.func.attr
    if isinstance(receiver, ast.Attribute) and _LOGGER_NAME_RE.match(receiver.attr):
        return node.func.attr
    return None


def attribute_names_matching(node: ast.AST, pattern: re.Pattern[str]) -> list[str]:
    """Walks `node`'s subtree and returns every `ast.Attribute` attribute
    name matching `pattern` — e.g. for `user.email`, called with an
    email-matching regex, returns `["email"]`. The generic mechanic behind
    both frameworks' "does this logged argument reference a sensitive
    attribute" check; only the regex differs (security-flavored vs.
    PII-only).
    """
    found: list[str] = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.Attribute) and pattern.match(sub.attr):
            found.append(sub.attr)
    return found


def imported_top_level_names(tree: ast.AST) -> list[tuple[str, int]]:
    """Every imported top-level package name paired with its line number,
    from both `import x.y` and `from x.y import z` forms (`import x.y` and
    `from x.y import z` both resolve to `"x"`). Moved out of
    `privacy_analysis.third_party._imported_top_level_names` (Phase 3) so
    Phase 4's AI/ML import detection reuses the same mechanic with its own
    independent curated package list, rather than duplicating this walk a
    second time — only the *list* differs between the two frameworks, not
    the mechanic.
    """
    results: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".", 1)[0]
                results.append((top, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                top = node.module.split(".", 1)[0]
                results.append((top, node.lineno))
    return results


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
