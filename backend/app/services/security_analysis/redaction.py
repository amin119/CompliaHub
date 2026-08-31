"""A detected secret's raw value must never reach `Evidence.snippet`,
`Finding.summary`, or a log line unredacted (compliance-scanner spec
section 7). One small, pure, testable function used everywhere a rule
captures a matched secret/credential substring.
"""

MASK = "*" * 8


def redact_secret(value: str, keep: int = 4) -> str:
    """Keeps the first/last `keep` characters, masks the rest. Short
    values (where keeping `keep` chars from each end would reveal most or
    all of the value) get a fixed-length mask instead — deliberately not
    proportional to the input's length, so the mask itself doesn't leak
    how long the real secret was.
    """
    if len(value) <= keep * 2:
        return MASK
    return f"{value[:keep]}…{value[-keep:]}"
