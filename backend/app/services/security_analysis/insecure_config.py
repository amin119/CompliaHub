"""Insecure-configuration checks — a small, honest starting set (not
exhaustive; deferred checks like TLS config or k8s `securityContext` are
called out in the as-built docs, not silently dropped).
"""

from __future__ import annotations

import re

from app.services.security_analysis.base import FunctionRule, RuleContext, RuleHit

_DEBUG_TRUE_RE = re.compile(r"\b(DEBUG)\s*[:=]\s*(true|True)\b")
_CORS_WILDCARD_RE = re.compile(
    r"""allow_origins\s*=\s*\[\s*["']\*["']\s*\]"""
    r"""|Access-Control-Allow-Origin:\s*\*"""
    r"""|cors_origins\s*[:=]\s*\[\s*["']\*["']\s*\]""",
    re.IGNORECASE,
)
_PRIVILEGED_RE = re.compile(r"privileged:\s*true", re.IGNORECASE)


def _detect_dockerfile_root(context: RuleContext) -> list[RuleHit]:
    if context.relative_path.rsplit("/", 1)[-1].lower() != "dockerfile":
        return []

    has_user = False
    last_user_is_root = False
    for line in context.text.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("USER "):
            has_user = True
            user_value = stripped.split(None, 1)[1].strip().lower()
            last_user_is_root = user_value == "root"

    if has_user and not last_user_is_root:
        return []

    return [
        RuleHit(
            title="Container may run as root",
            status="REQUIRES_HUMAN_REVIEW",
            severity="MEDIUM",
            confidence="medium",
            summary=(
                "Dockerfile has no USER instruction."
                if not has_user
                else "Dockerfile's last USER instruction is 'root'."
            ),
            reasoning="Running a container as root increases the impact of a container "
            "breakout or a misconfigured volume mount.",
            recommendation="Add a USER instruction switching to a non-root user before the "
            "final CMD/ENTRYPOINT.",
        )
    ]


def _detect_privileged_compose(context: RuleContext) -> list[RuleHit]:
    if context.relative_path.rsplit("/", 1)[-1].lower() not in {
        "docker-compose.yml",
        "docker-compose.yaml",
    }:
        return []

    hits = []
    for i, line in enumerate(context.text.splitlines(), start=1):
        if _PRIVILEGED_RE.search(line):
            hits.append(
                RuleHit(
                    title="Privileged container",
                    status="POTENTIAL_NON_COMPLIANCE",
                    severity="HIGH",
                    confidence="high",
                    summary=f"Line {i} sets 'privileged: true'.",
                    reasoning="A privileged container has near-full access to the host, "
                    "defeating most container isolation.",
                    recommendation="Remove 'privileged: true' unless the specific device/"
                    "capability access it grants is genuinely required; prefer explicit "
                    "'cap_add' instead.",
                    line_start=i,
                    line_end=i,
                    snippet=line.strip()[:300],
                )
            )
    return hits


def _detect_debug_true(context: RuleContext) -> list[RuleHit]:
    hits = []
    for i, line in enumerate(context.text.splitlines(), start=1):
        if _DEBUG_TRUE_RE.search(line):
            hits.append(
                RuleHit(
                    title="Debug mode enabled",
                    status="REQUIRES_HUMAN_REVIEW",
                    severity="MEDIUM",
                    confidence="medium",
                    summary=f"Line {i} sets a debug flag to true.",
                    reasoning="Debug mode often exposes stack traces or relaxes security "
                    "checks — fine in development, risky if left enabled in production.",
                    recommendation="Ensure this defaults to false and is only enabled via an "
                    "explicit, environment-scoped override.",
                    line_start=i,
                    line_end=i,
                    snippet=line.strip()[:300],
                )
            )
    return hits


def _detect_cors_wildcard(context: RuleContext) -> list[RuleHit]:
    hits = []
    for i, line in enumerate(context.text.splitlines(), start=1):
        if _CORS_WILDCARD_RE.search(line):
            hits.append(
                RuleHit(
                    title="Permissive CORS configuration",
                    status="POTENTIAL_NON_COMPLIANCE",
                    severity="MEDIUM",
                    confidence="medium",
                    summary=f"Line {i} allows any origin ('*').",
                    reasoning="A wildcard CORS origin lets any website make cross-origin "
                    "requests against this API from a user's browser, widening the attack "
                    "surface for data leakage.",
                    recommendation="List explicit allowed origins instead of '*', especially "
                    "if credentials/cookies are involved.",
                    line_start=i,
                    line_end=i,
                    snippet=line.strip()[:300],
                )
            )
    return hits


RULES = [
    FunctionRule(
        "SEC-CONFIG-DOCKER-ROOT", "insecure_configuration", "MEDIUM", _detect_dockerfile_root
    ),
    FunctionRule(
        "SEC-CONFIG-PRIVILEGED", "insecure_configuration", "HIGH", _detect_privileged_compose
    ),
    FunctionRule("SEC-CONFIG-DEBUG-TRUE", "insecure_configuration", "MEDIUM", _detect_debug_true),
    FunctionRule(
        "SEC-CONFIG-CORS-WILDCARD", "insecure_configuration", "MEDIUM", _detect_cors_wildcard
    ),
]
