"""The flat, in-code rule registry — see `base.py`'s module docstring for
why this is a plain Python list rather than a YAML-configurable layer.
"""

from app.services.security_analysis import (
    cryptography_rules,
    dependencies,
    hardcoded_credentials,
    insecure_config,
    logging_rules,
    secrets,
)
from app.services.security_analysis.base import SecurityRule

ALL_RULES: list[SecurityRule] = [
    *secrets.RULES,
    *hardcoded_credentials.RULES,
    *cryptography_rules.RULES,
    *logging_rules.RULES,
    *dependencies.RULES,
    *insecure_config.RULES,
]
