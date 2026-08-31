"""The flat, in-code privacy rule registry — the GDPR counterpart to
`security_analysis.registry.ALL_RULES`, same flat-list-at-import-time
pattern. See `base.py`'s module docstring for why this is a separate
registry rather than a shared one with a per-rule `framework` field.

Note: the repo-level checks in `repo_level_checks.py` are deliberately
*not* here — they are aggregate, whole-file-set facts that don't fit the
per-file `detect(context)` protocol, and the Celery task calls them
directly.
"""

from app.services.privacy_analysis import (
    logging_pii,
    pii_fields,
    third_party,
)
from app.services.privacy_analysis.base import PrivacyRule

PRIVACY_RULES: list[PrivacyRule] = [
    *pii_fields.RULES,
    *logging_pii.RULES,
    *third_party.RULES,
]
