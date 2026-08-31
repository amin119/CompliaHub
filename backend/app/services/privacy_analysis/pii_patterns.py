"""Regex vocabularies for PII field-name detection, kept separate from the
detection logic (`pii_fields.py`) so the two disjoint category sets read as
data, not control flow.

Two *disjoint* regexes, deliberately non-overlapping:

- `_PERSONAL_DATA_FIELD_RE` — ordinary personal data under GDPR
  (name/email/phone/address/IP/date-of-birth/location/cookies/tracking id).
  Maps to `category="data_minimisation"`.
- `_SPECIAL_CATEGORY_FIELD_RE` — Article 9 "special category" data
  (health/biometric/genetic/ssn/credit-card/gender/ethnicity/religion/
  sexual-orientation/political-opinion/trade-union). Maps to
  `category="special_category_data"` and is *always* `severity="HIGH"`,
  since Article 9 data carries the strictest processing conditions.

These match a *field name*, never a value. This phase is a field-name/
structural detector only — never a content classifier (finding a
real-looking email inside a string literal or comment is explicitly out of
scope, per the spec's own prohibition on inferring processing from a bare
name match taken to its logical boundary).
"""

from __future__ import annotations

import re

# Ordinary personal data. Word-boundary-ish anchoring against a normalized
# (lower-cased) attribute name — these run against an identifier, not free
# text, so a full match against the whole name is the right shape.
_PERSONAL_DATA_FIELD_RE = re.compile(
    r"^(?:"
    r"first_?name|last_?name|full_?name|user_?name|name"
    r"|email|email_?address"
    r"|phone|phone_?number|mobile|telephone"
    r"|address|street|city|postal_?code|zip_?code|zipcode"
    r"|ip|ip_?address"
    r"|date_?of_?birth|dob|birth_?date|birthday"
    r"|location|latitude|longitude|geolocation|geo_?location"
    r"|cookie|cookies|tracking_?id"
    r")$",
    re.IGNORECASE,
)

# Article 9 special-category data — always HIGH severity at the call site.
_SPECIAL_CATEGORY_FIELD_RE = re.compile(
    r"^(?:"
    r"health|health_?data|medical|medical_?record|diagnosis|disability"
    r"|biometric|fingerprint|face_?id|facial_?recognition|retina|iris_?scan"
    r"|genetic|genome|dna"
    r"|ssn|social_?security_?number|national_?id"
    r"|credit_?card|card_?number|cvv|iban"
    r"|gender|sex"
    r"|ethnicity|ethnic_?origin|race"
    r"|religion|religious_?belief"
    r"|sexual_?orientation|sexuality"
    r"|political_?opinion|political_?affiliation"
    r"|trade_?union|union_?membership"
    r")$",
    re.IGNORECASE,
)


def classify_field_name(name: str) -> str | None:
    """Returns `"special_category_data"` if `name` is Article 9 data,
    `"data_minimisation"` if it's ordinary personal data, else `None`.
    Special-category is checked first: a name that could plausibly hit both
    sets should be treated as the more sensitive one.
    """
    if _SPECIAL_CATEGORY_FIELD_RE.match(name):
        return "special_category_data"
    if _PERSONAL_DATA_FIELD_RE.match(name):
        return "data_minimisation"
    return None
