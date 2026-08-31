"""Shared types for the AI/ISO 42001 rule engine.

Same deliberately-thin shape as `privacy_analysis/base.py`: `RuleContext`/
`RuleHit`/`FunctionRule` are imported straight from
`app.services.security_analysis.base` (zero duplication) — a rule is the
same shape regardless of which framework it serves. What makes this a
*separate* package is the category vocabulary (`ai_system_detection`,
`rag_detection`, `prompt_detection`, `agentic_pattern_detection`,
`inference_call_detection`, `ai_system_inventory`, plus the nine fixed
governance categories), a different taxonomy from both Phase 2's security
categories and Phase 3's GDPR categories.

No `framework` field on the rule objects, same reasoning as Phase 3:
`Finding.framework` is set at the call site in the Celery task
(`framework="ISO42001"` for everything this registry's loop produces),
not something every rule construction needs to repeat.
"""

from __future__ import annotations

from app.services.security_analysis.base import (
    FunctionRule,
    RuleContext,
    RuleHit,
    SecurityRule,
)

AIRule = SecurityRule

__all__ = ["FunctionRule", "RuleContext", "RuleHit", "AIRule"]
