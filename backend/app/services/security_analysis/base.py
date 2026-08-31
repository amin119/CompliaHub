"""Shared types for the security rule engine. A rule is just an object
with a `detect(context) -> list[RuleHit]` method — a flat, in-code
registry (`registry.py`) drives which rules run, not a YAML config layer:
this project scopes a spec's suggested design down to what's actually
needed (see the flat Leiden partition instead of hierarchical communities
in Phase 3's community detection, for the same kind of precedent). A YAML
loader can be added later as a second way to populate the registry,
additive, not a rewrite.
"""

from __future__ import annotations

import ast
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class RuleContext:
    """Everything a rule needs about one already-classified repository
    file. `tree` is `None` whenever the file isn't Python or failed to
    parse (a syntax error in a scanned file must never fail the whole
    scan — see `ast_utils.safe_parse`) — every Python-only rule checks for
    `None` and skips, so the same rule list runs safely over every file.
    """

    relative_path: str
    language: str | None
    component_type: str
    text: str
    tree: ast.AST | None


@dataclass(frozen=True)
class RuleHit:
    """One occurrence a rule wants recorded as a Finding + Evidence pair.
    `snippet` must already be redacted by the rule itself if it could
    contain a raw secret (see `redaction.redact_secret`) — the pipeline
    that turns this into DB rows does not re-check that.

    `category` defaults to `None`, meaning "use the rule's own `category`"
    — every rule whose hits are all one logical category (the overwhelming
    majority) never needs to set this. It exists for the rare rule whose
    hits vary by category at runtime (e.g. `pii_fields.py`'s single
    AST walk produces both `data_minimisation` and `special_category_data`
    hits depending on which field matched) — a real bug was caught live
    where such a rule's special-category hits were silently written with
    the rule's generic default category instead, because nothing let a hit
    override it. Same per-hit-overrides-a-rule-level-default shape
    `severity`/`confidence`/`status` already use.
    """

    title: str
    status: str  # "POTENTIAL_NON_COMPLIANCE" | "REQUIRES_HUMAN_REVIEW"
    severity: str  # "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "INFORMATIONAL"
    confidence: str  # "high" | "medium" | "low"
    summary: str
    reasoning: str
    recommendation: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    snippet: str | None = None
    category: str | None = None
    # Structured payload for the rare hit that needs to carry more than
    # prose — currently only Phase 4's AI-system-inventory finding
    # (spec section 11's JSON shape: models/uses_rag/uses_tools/etc.),
    # written straight through to `Evidence.evidence_metadata` (a JSONB
    # column that's existed, unused, since Phase 1). `None` for every
    # ordinary hit.
    evidence_metadata: dict | None = None


class SecurityRule(Protocol):
    rule_id: str
    category: str
    default_severity: str
    # What kind of analysis this specific rule performs — used to fill
    # `Evidence.source_type`. Deliberately a property of the *rule*, not
    # inferred from whether the file being scanned happened to parse as
    # Python: a regex-based rule (e.g. `secrets.py`'s patterns) run against
    # a Python file must not be mislabeled "ast_analysis" just because that
    # file's AST was available for other rules to use.
    evidence_source_type: str

    def detect(self, context: RuleContext) -> list[RuleHit]: ...


@dataclass(frozen=True)
class FunctionRule:
    """Concrete `SecurityRule` implementation wrapping a plain detect
    function — every rule module in this package builds one of these
    rather than a full class, since none of them carry extra state beyond
    their own constants.
    """

    rule_id: str
    category: str
    default_severity: str
    detect_fn: Callable[[RuleContext], list[RuleHit]] = field(repr=False)
    evidence_source_type: str = "static_pattern"

    def detect(self, context: RuleContext) -> list[RuleHit]:
        return self.detect_fn(context)
