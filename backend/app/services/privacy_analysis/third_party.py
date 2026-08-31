"""Third-party data flow + cookies/tracking detection.

Third-party imports (AST-based, `ast.Import`/`ast.ImportFrom`) — same shape
as `dependencies.py`'s manifest scanning, but over application-code imports.
The curated list is modeled on this backend's own real third-party deps as
the template (AI/LLM, storage, analytics, payment, email). Every match →
one `REQUIRES_HUMAN_REVIEW`, `category="third_party_processors"`,
`severity="MEDIUM"` finding — international-transfer language is folded into
the same finding's reasoning, not emitted as a second near-duplicate
finding for the same line.

Cookies/tracking is included, not deferred (comparable false-positive risk
to the third-party check, and the spec explicitly lists it):
`response.set_cookie(...)` via AST; `res.cookie(...)` / `document.cookie =`
/ known tracking-script markers (`gtag(`, `mixpanel`, `hotjar`,
`google-analytics`) via regex for JS/TS/HTML. All
`category="consent_mechanisms"`, always `REQUIRES_HUMAN_REVIEW`.
"""

from __future__ import annotations

import ast
import re

from app.services.privacy_analysis.base import FunctionRule, RuleContext, RuleHit
from app.services.security_analysis import ast_utils

# Top-level package name → short human category label. Matched against the
# first dotted component of an import (`google.genai` → `google`), so a
# submodule import still resolves to the same processor.
_THIRD_PARTY_PACKAGES: dict[str, str] = {
    # AI / LLM providers
    "google": "AI/LLM provider",
    "genai": "AI/LLM provider",
    "cohere": "AI/LLM provider",
    "voyageai": "AI/LLM provider",
    "openai": "AI/LLM provider",
    "anthropic": "AI/LLM provider",
    # Storage / infrastructure
    "qdrant_client": "storage/infrastructure provider",
    "neo4j": "storage/infrastructure provider",
    "minio": "storage/infrastructure provider",
    "boto3": "storage/infrastructure provider (AWS)",
    # Analytics
    "mixpanel": "analytics provider",
    "segment": "analytics provider",
    "analytics": "analytics provider",
    "amplitude": "analytics provider",
    # Payment
    "stripe": "payment processor",
    "braintree": "payment processor",
    # Email
    "sendgrid": "email provider",
    "mailgun": "email provider",
}


def _detect_third_party_imports(context: RuleContext) -> list[RuleHit]:
    if context.tree is None:
        return []

    hits: list[RuleHit] = []
    seen: set[str] = set()
    for name, line in ast_utils.imported_top_level_names(context.tree):
        label = _THIRD_PARTY_PACKAGES.get(name)
        if label is None or name in seen:
            continue
        seen.add(name)  # one finding per distinct package per file
        hits.append(
            RuleHit(
                title="Third-party data processor imported",
                status="REQUIRES_HUMAN_REVIEW",
                severity="MEDIUM",
                confidence="medium",
                summary=f"Imports '{name}', a {label}.",
                reasoning=(
                    f"Line {line} imports '{name}', a {label}. Sending personal data to a "
                    "third party makes them a processor (or joint controller) under GDPR, "
                    "which requires a data processing agreement (Art. 28). If the provider "
                    "processes data outside the EEA, an international-transfer safeguard "
                    "(adequacy decision, SCCs, or equivalent under Art. 44-49) is also needed. "
                    "Whether personal data actually flows here cannot be determined "
                    "statically — flagged for human review."
                ),
                recommendation="Confirm a data processing agreement is in place and, if the "
                "provider processes data outside the EEA, that a valid transfer mechanism "
                "covers it.",
                line_start=line,
                line_end=line,
                snippet=None,
            )
        )
    return hits


def _detect_set_cookie_python(context: RuleContext) -> list[RuleHit]:
    if context.tree is None:
        return []

    hits: list[RuleHit] = []
    for node in ast.walk(context.tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "set_cookie":
            line_start, line_end = ast_utils.line_range(node)
            hits.append(
                RuleHit(
                    title="Cookie set on HTTP response",
                    status="REQUIRES_HUMAN_REVIEW",
                    severity="MEDIUM",
                    confidence="medium",
                    summary=f"Line {line_start} calls set_cookie(...).",
                    reasoning=(
                        f"Line {line_start} sets a cookie. Non-essential cookies (analytics, "
                        "advertising, tracking) require prior consent under the ePrivacy "
                        "Directive/GDPR; strictly-necessary cookies do not. Which kind this is "
                        "cannot be determined statically — flagged for human review of the "
                        "consent mechanism."
                    ),
                    recommendation="Confirm whether this cookie is strictly necessary; if not, "
                    "ensure it is only set after the user has given consent.",
                    line_start=line_start,
                    line_end=line_end,
                    snippet=ast_utils.source_segment(context.text, node),
                )
            )
    return hits


# JS/TS/HTML markers — regex only, since this project is Python-first and
# doesn't parse a JS AST (same posture as Phase 2's non-Python fallbacks).
_JS_COOKIE_RE = re.compile(
    r"""(?:\.cookie\s*\(|document\.cookie\s*=|res\.cookie\s*\()""",
    re.IGNORECASE,
)
_TRACKING_MARKER_RE = re.compile(
    r"""(gtag\s*\(|mixpanel|hotjar|google-analytics|googletagmanager)""",
    re.IGNORECASE,
)


def _detect_cookies_tracking_regex(context: RuleContext) -> list[RuleHit]:
    # Only for non-Python web files (JS/TS/HTML). Python cookies are handled
    # by the AST rule above; running this on Python would double-report.
    is_html = context.relative_path.lower().endswith((".html", ".htm"))
    if context.language not in {"javascript", "typescript"} and not is_html:
        return []

    hits: list[RuleHit] = []
    for i, line in enumerate(context.text.splitlines(), start=1):
        cookie = _JS_COOKIE_RE.search(line)
        tracker = _TRACKING_MARKER_RE.search(line)
        if not cookie and not tracker:
            continue
        marker = (cookie or tracker).group(0)
        hits.append(
            RuleHit(
                title="Cookie or tracking script usage",
                status="REQUIRES_HUMAN_REVIEW",
                severity="MEDIUM",
                confidence="low",
                summary=f"Line {i} references '{marker.strip()}', a cookie/tracking mechanism.",
                reasoning=(
                    "A regex match, not an AST check (this file isn't Python) — a cookie write "
                    "or a known tracking/analytics script marker. Non-essential cookies and "
                    "tracking require prior consent under the ePrivacy Directive/GDPR; whether "
                    "consent is obtained first cannot be determined statically."
                ),
                recommendation="Confirm a consent mechanism gates this before any "
                "non-essential cookie or tracker is loaded.",
                line_start=i,
                line_end=i,
                snippet=line.strip()[:300],
            )
        )
    return hits


RULES = [
    FunctionRule(
        "GDPR-THIRD-PARTY-IMPORT-PY",
        "third_party_processors",
        "MEDIUM",
        _detect_third_party_imports,
        evidence_source_type="ast_analysis",
    ),
    FunctionRule(
        "GDPR-COOKIE-SET-PY",
        "consent_mechanisms",
        "MEDIUM",
        _detect_set_cookie_python,
        evidence_source_type="ast_analysis",
    ),
    FunctionRule(
        "GDPR-COOKIE-TRACKING-REGEX",
        "consent_mechanisms",
        "MEDIUM",
        _detect_cookies_tracking_regex,
    ),
]
