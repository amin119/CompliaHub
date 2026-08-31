"""Shared types for the GDPR/privacy rule engine.

This is a deliberately thin module: `RuleContext`/`RuleHit`/`FunctionRule`
are imported straight from `app.services.security_analysis.base` (zero
duplication) — a rule is the same shape regardless of which framework it
serves. What makes this a *separate* package is the category vocabulary
(`data_minimisation`, `special_category_data`, `third_party_processors`,
`consent_mechanisms`, `data_subject_rights`, `lawful_basis`, ...), which is
a different taxonomy from Phase 2's security categories — keeping the two
registries separate makes "which rules belong to which framework" a
structural fact rather than an implicit `rule_id`-prefix convention.

There is deliberately no `framework` field on the rule objects.
`Finding.framework` is set at the call site in the Celery task, hardcoded
per which registry's loop is running (`ALL_RULES` → `framework=None`,
`PRIVACY_RULES` → `framework="GDPR"`) — the fact is a property of *which
loop runs*, not something every rule construction needs to repeat.
"""

from __future__ import annotations

from app.services.security_analysis.base import (
    FunctionRule,
    RuleContext,
    RuleHit,
    SecurityRule,
)

# A privacy rule is structurally identical to a security rule — same
# `detect(context) -> list[RuleHit]` protocol. The alias exists only so
# this package's type annotations read in its own vocabulary rather than
# reaching across to the security package's name at every use site.
PrivacyRule = SecurityRule

__all__ = ["FunctionRule", "RuleContext", "RuleHit", "PrivacyRule"]
