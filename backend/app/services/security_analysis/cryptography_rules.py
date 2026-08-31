"""Weak-cryptography detection. Per the compliance-scanner spec's own
warning ("do NOT automatically declare a vulnerability merely because an
algorithm appears... consider context"), every hit is classified using
the nearest enclosing function/variable name as a cheap, deterministic
proxy for intent: `hashlib.md5(...)` inside `hash_password(...)` is a real
concern; the same call inside `cache_key(...)` is not, but is still
recorded as evidence at low confidence rather than silently dropped.
"""

from __future__ import annotations

import ast
import re

from app.services.security_analysis import ast_utils
from app.services.security_analysis.base import FunctionRule, RuleContext, RuleHit

_WEAK_HASH_NAMES = {"md5", "sha1"}
_WEAK_CIPHER_NAMES = {"DES", "DES3", "TripleDES", "ARC4", "RC4", "Blowfish"}

_SENSITIVE_CONTEXT_RE = re.compile(
    r"(hash_password|verify_password|check_password|auth|login|credential|passwd|pwd)",
    re.IGNORECASE,
)
_BENIGN_CONTEXT_RE = re.compile(
    r"(cache_key|cache|etag|checksum|dedup|fingerprint|hash_id)", re.IGNORECASE
)


def _classify(context_name: str | None) -> tuple[str, str, str]:
    """Returns (severity, confidence, status)."""
    if context_name and _SENSITIVE_CONTEXT_RE.search(context_name):
        return "HIGH", "high", "POTENTIAL_NON_COMPLIANCE"
    if context_name and _BENIGN_CONTEXT_RE.search(context_name):
        return "LOW", "low", "REQUIRES_HUMAN_REVIEW"
    return "MEDIUM", "medium", "REQUIRES_HUMAN_REVIEW"


def _context_name(node: ast.AST, parents: ast_utils.ParentMap) -> str | None:
    return ast_utils.assigned_variable_name(node, parents) or ast_utils.enclosing_function_name(
        node, parents
    )


def _make_hit(
    node: ast.AST,
    context: RuleContext,
    parents: ast_utils.ParentMap,
    title: str,
    algorithm: str,
) -> RuleHit:
    name = _context_name(node, parents)
    severity, confidence, status = _classify(name)
    line_start, line_end = ast_utils.line_range(node)
    where = f" (near '{name}')" if name else ""
    return RuleHit(
        title=title,
        status=status,
        severity=severity,
        confidence=confidence,
        summary=f"{algorithm} usage found{where}.",
        reasoning=(
            f"Line {line_start} uses {algorithm}, considered weak for security-sensitive "
            f"purposes. Surrounding context{(' (' + name + ')') if name else ''} "
            f"{'suggests' if confidence != 'medium' else 'does not clearly indicate'} "
            "whether this is used for security purposes vs. a non-sensitive purpose like "
            "caching or checksums."
        ),
        recommendation="If used for password hashing, use a dedicated KDF (bcrypt/argon2/"
        "scrypt). If used for integrity/signing, use SHA-256 or stronger.",
        line_start=line_start,
        line_end=line_end,
        snippet=ast_utils.source_segment(context.text, node),
    )


def _detect_python(context: RuleContext) -> list[RuleHit]:
    if context.tree is None:
        return []

    parents = ast_utils.build_parent_map(context.tree)
    hits = []
    for node in ast.walk(context.tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr.lower() in _WEAK_HASH_NAMES:
                hits.append(
                    _make_hit(node, context, parents, "Weak hash algorithm", node.func.attr)
                )
        elif isinstance(node, ast.Attribute) and node.attr in _WEAK_CIPHER_NAMES:
            hits.append(_make_hit(node, context, parents, "Weak cipher algorithm", node.attr))
        elif isinstance(node, ast.Name) and node.id in _WEAK_CIPHER_NAMES:
            hits.append(_make_hit(node, context, parents, "Weak cipher algorithm", node.id))
        elif isinstance(node, ast.Attribute) and node.attr == "MODE_ECB":
            hits.append(_make_hit(node, context, parents, "ECB cipher mode", "ECB mode"))
    return hits


_WEAK_CRYPTO_REGEX = re.compile(
    r"\b(MD5|SHA1|DES3?|RC4|MODE_ECB)\b|[\"']ECB[\"']"
)


def _detect_generic_regex(context: RuleContext) -> list[RuleHit]:
    if context.tree is not None:
        return []  # Python already covered by the AST rule above.

    hits = []
    for i, line in enumerate(context.text.splitlines(), start=1):
        match = _WEAK_CRYPTO_REGEX.search(line)
        if not match:
            continue
        hits.append(
            RuleHit(
                title="Weak cryptographic primitive",
                status="REQUIRES_HUMAN_REVIEW",
                severity="MEDIUM",
                confidence="medium",
                summary=f"Line {i} references '{match.group(0)}', a weak cryptographic primitive.",
                reasoning=(
                    "A regex match, not an AST check (this file isn't Python) — no context "
                    "signal available to judge whether this usage is security-sensitive."
                ),
                recommendation="Confirm the purpose; if security-sensitive, replace with a "
                "modern algorithm (SHA-256+ for hashing, AES-GCM for encryption).",
                line_start=i,
                line_end=i,
                snippet=line.strip()[:300],
            )
        )
    return hits


RULES = [
    FunctionRule(
        "SEC-CRYPTO-WEAK-PY",
        "cryptography",
        "MEDIUM",
        _detect_python,
        evidence_source_type="ast_analysis",
    ),
    FunctionRule("SEC-CRYPTO-WEAK-REGEX", "cryptography", "MEDIUM", _detect_generic_regex),
]
