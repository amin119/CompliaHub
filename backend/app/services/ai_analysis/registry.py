"""The flat, in-code AI/ISO 42001 rule registry — same pattern as
`security_analysis.registry.ALL_RULES` and `privacy_analysis.registry.
PRIVACY_RULES`.

Note: `repo_level_checks.py`'s aggregate findings are deliberately *not*
here — they're whole-file-set facts gated on the signal-type threshold,
not per-file rules; the Celery task calls them directly after the loop.
"""

from app.services.ai_analysis import (
    agentic_detection,
    ai_imports,
    inference_detection,
    prompt_detection,
    rag_detection,
)
from app.services.ai_analysis.base import AIRule

AI_RULES: list[AIRule] = [
    *ai_imports.RULES,
    *rag_detection.RULES,
    *prompt_detection.RULES,
    *agentic_detection.RULES,
    *inference_detection.RULES,
]
