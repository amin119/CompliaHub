"""Dependency risk — static-only for Phase 2 (confirmed with the user: no
network calls to a vulnerability database like OSV.dev in this phase).
Flags unpinned versions as a risk factor, not a vulnerability claim —
`REQUIRES_HUMAN_REVIEW`, never `POTENTIAL_NON_COMPLIANCE`, since being
unpinned isn't itself a compliance problem.
"""

from __future__ import annotations

import json
import re

from app.services.security_analysis.base import FunctionRule, RuleContext, RuleHit

_VERSION_SPECIFIER_RE = re.compile(r"(==|>=|<=|~=|!=|>|<)")
_WILDCARD_VERSIONS = {"*", "latest"}


def _check_requirements_txt(context: RuleContext) -> list[RuleHit]:
    hits = []
    for i, raw_line in enumerate(context.text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        if _VERSION_SPECIFIER_RE.search(line):
            continue
        package_name = re.split(r"[\s;\[]", line, maxsplit=1)[0]
        if not package_name:
            continue
        hits.append(
            RuleHit(
                title="Unpinned dependency version",
                status="REQUIRES_HUMAN_REVIEW",
                severity="LOW",
                confidence="medium",
                summary=f"'{package_name}' has no version specifier.",
                reasoning=(
                    f"Line {i} lists '{package_name}' with no version pin — an unpinned "
                    "dependency can silently upgrade to a version with new vulnerabilities or "
                    "breaking changes."
                ),
                recommendation="Pin to a specific version or a bounded range (e.g. "
                "'>=1.2,<2.0').",
                line_start=i,
                line_end=i,
                snippet=line[:300],
            )
        )
    return hits


def _check_package_json(context: RuleContext) -> list[RuleHit]:
    try:
        payload = json.loads(context.text)
    except (json.JSONDecodeError, ValueError):
        return []
    if not isinstance(payload, dict):
        return []

    hits = []
    for section in ("dependencies", "devDependencies"):
        deps = payload.get(section)
        if not isinstance(deps, dict):
            continue
        for name, version in deps.items():
            if isinstance(version, str) and version.strip() in _WILDCARD_VERSIONS:
                hits.append(
                    RuleHit(
                        title="Unpinned dependency version",
                        status="REQUIRES_HUMAN_REVIEW",
                        severity="LOW",
                        confidence="medium",
                        summary=f"'{name}' is pinned to '{version}' in {section}.",
                        reasoning=(
                            f"'{name}' resolves to '{version}', which always installs "
                            "whatever is newest at install time rather than a known version."
                        ),
                        recommendation="Pin to a specific version or a caret/tilde range "
                        "(e.g. '^1.2.3').",
                        line_start=None,
                        line_end=None,
                        snippet=f'"{name}": "{version}"',
                    )
                )
    return hits


def _detect_unpinned(context: RuleContext) -> list[RuleHit]:
    if context.component_type != "dependency_manifest":
        return []
    filename = context.relative_path.rsplit("/", 1)[-1].lower()
    if filename == "requirements.txt":
        return _check_requirements_txt(context)
    if filename == "package.json":
        return _check_package_json(context)
    return []


RULES = [
    FunctionRule("SEC-DEP-UNPINNED", "dependencies", "LOW", _detect_unpinned),
]
