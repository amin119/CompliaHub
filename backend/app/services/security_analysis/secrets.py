"""Secret detection — curated regex patterns for well-known credential
shapes, plus a generic entropy-based check for anything assigned to a
suspiciously-named variable. Language-agnostic: operates on raw text, not
AST, since a secret can leak into any file type (config, code, .env).

Deliberately a small, hand-written pattern set, not a full vendored
port of an external secrets-scanning tool's plugin catalog — this covers
the realistic "did someone commit a real key" case; a bigger catalog is a
low-risk addition to bolt on later without restructuring anything.
"""

from __future__ import annotations

import math
import re

from app.services.security_analysis.base import FunctionRule, RuleContext, RuleHit
from app.services.security_analysis.redaction import redact_secret

_AWS_ACCESS_KEY_RE = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
_PEM_PRIVATE_KEY_RE = re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----")
_GITHUB_TOKEN_RE = re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")
_SLACK_TOKEN_RE = re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")

_SENSITIVE_NAME_RE = re.compile(
    r"(password|secret|token|api[_-]?key|apikey|credential|auth)", re.IGNORECASE
)
# `NAME = "value"` / `NAME: "value"` / `NAME="value"` (.env-style) across
# common languages/config formats — a single loose pattern, not a per-
# language parser, deliberately: Phase 2 stays language-agnostic here.
_ASSIGNMENT_RE = re.compile(r"""^\s*([\w.]+)\s*[:=]\s*["']?([^"'\s#]{8,})["']?\s*$""")

_ENTROPY_THRESHOLD = 4.0
_MIN_CANDIDATE_LENGTH = 12
_PLACEHOLDER_VALUES = {"changeme", "xxxxxxxx", "your-secret-here", "placeholder"}


def _shannon_entropy(value: str) -> float:
    if not value:
        return 0.0
    counts: dict[str, int] = {}
    for ch in value:
        counts[ch] = counts.get(ch, 0) + 1
    length = len(value)
    return -sum((n / length) * math.log2(n / length) for n in counts.values())


def _line_hit(
    line_no: int, line: str, matched: str, title: str, rule_id_suffix: str
) -> RuleHit:
    return RuleHit(
        title=title,
        status="POTENTIAL_NON_COMPLIANCE",
        severity="CRITICAL",
        confidence="high",
        summary=f"{title} found in repository content.",
        reasoning=(
            f"Line {line_no} matches a known {rule_id_suffix} pattern. Secrets committed to a "
            "repository are readable by anyone with source access, including in version-control "
            "history even after later removal."
        ),
        recommendation="Revoke this credential immediately and load it from a secret manager "
        "or environment variable instead of committing it.",
        line_start=line_no,
        line_end=line_no,
        snippet=redact_secret(matched),
    )


def _detect_pattern(
    context: RuleContext, pattern: re.Pattern, title: str, suffix: str
) -> list[RuleHit]:
    hits = []
    for i, line in enumerate(context.text.splitlines(), start=1):
        match = pattern.search(line)
        if match:
            hits.append(_line_hit(i, line, match.group(0), title, suffix))
    return hits


def _detect_aws_key(context: RuleContext) -> list[RuleHit]:
    return _detect_pattern(
        context, _AWS_ACCESS_KEY_RE, "Hardcoded AWS access key", "AWS access key"
    )


def _detect_pem_key(context: RuleContext) -> list[RuleHit]:
    return _detect_pattern(context, _PEM_PRIVATE_KEY_RE, "Embedded private key", "PEM private key")


def _detect_github_token(context: RuleContext) -> list[RuleHit]:
    return _detect_pattern(context, _GITHUB_TOKEN_RE, "Hardcoded GitHub token", "GitHub token")


def _detect_slack_token(context: RuleContext) -> list[RuleHit]:
    return _detect_pattern(context, _SLACK_TOKEN_RE, "Hardcoded Slack token", "Slack token")


def _detect_generic_high_entropy_secret(context: RuleContext) -> list[RuleHit]:
    hits = []
    for i, line in enumerate(context.text.splitlines(), start=1):
        match = _ASSIGNMENT_RE.match(line)
        if not match:
            continue
        name, value = match.group(1), match.group(2)
        if not _SENSITIVE_NAME_RE.search(name):
            continue
        if value.lower() in _PLACEHOLDER_VALUES or len(value) < _MIN_CANDIDATE_LENGTH:
            continue
        if _shannon_entropy(value) < _ENTROPY_THRESHOLD:
            continue
        hits.append(
            RuleHit(
                title="Possible hardcoded secret (high-entropy value)",
                status="POTENTIAL_NON_COMPLIANCE",
                severity="HIGH",
                confidence="medium",
                summary=(
                    f"A high-entropy value is assigned to '{name}', a name suggesting "
                    "sensitive content."
                ),
                reasoning=(
                    f"Line {i} assigns a {len(value)}-character value with "
                    f"{_shannon_entropy(value):.1f} bits/char entropy to a variable named "
                    f"'{name}' — a pattern consistent with a real credential rather than a "
                    "placeholder, but not certain without knowing where the value came from."
                ),
                recommendation="Confirm this value isn't a real credential; if it is, revoke "
                "it and load it from a secret manager or environment variable.",
                line_start=i,
                line_end=i,
                snippet=redact_secret(value),
            )
        )
    return hits


RULES = [
    FunctionRule("SEC-SECRET-AWS-KEY", "secrets", "CRITICAL", _detect_aws_key),
    FunctionRule("SEC-SECRET-PEM-KEY", "secrets", "CRITICAL", _detect_pem_key),
    FunctionRule("SEC-SECRET-GH-TOKEN", "secrets", "CRITICAL", _detect_github_token),
    FunctionRule("SEC-SECRET-SLACK-TOKEN", "secrets", "CRITICAL", _detect_slack_token),
    FunctionRule(
        "SEC-SECRET-GENERIC-ENTROPY", "secrets", "HIGH", _detect_generic_high_entropy_secret
    ),
]
