from app.services.privacy_analysis.pii_fields import _detect_generic_regex, _detect_python
from app.services.security_analysis.ast_utils import safe_parse
from app.services.security_analysis.base import RuleContext


def _python_context(source: str) -> RuleContext:
    return RuleContext(
        relative_path="app/models/user.py",
        language="python",
        component_type="application_code",
        text=source,
        tree=safe_parse(source),
    )


def test_flags_personal_data_field_on_sqlalchemy_model():
    source = (
        "class User(Base):\n"
        "    email = mapped_column(String)\n"
        "    date_of_birth = mapped_column(Date)\n"
    )
    hits = _detect_python(_python_context(source))
    categories = {h.summary.split("'")[1]: h for h in hits}
    assert "email" in categories
    assert "date_of_birth" in categories
    # The spec's worked example: date_of_birth -> data_minimisation, review.
    dob_hit = categories["date_of_birth"]
    assert dob_hit.status == "REQUIRES_HUMAN_REVIEW"
    assert dob_hit.severity == "MEDIUM"


def test_special_category_field_is_always_high():
    source = "class Patient(Base):\n    ssn = mapped_column(String)\n"
    hits = _detect_python(_python_context(source))
    assert len(hits) == 1
    assert hits[0].severity == "HIGH"


def test_special_category_field_hit_carries_its_own_category():
    # Real bug caught live: a single rule can produce hits of two logical
    # categories (data_minimisation vs. special_category_data) depending on
    # which field matched — the hit itself must carry the right category,
    # since the registry only has one fixed `category` for the whole rule.
    # Without `RuleHit.category`, every hit from this rule silently landed
    # in the DB as "data_minimisation", even the special-category ones.
    source = (
        "class Patient(Base):\n"
        "    email = mapped_column(String)\n"
        "    ssn = mapped_column(String)\n"
    )
    hits = _detect_python(_python_context(source))
    by_field = {h.summary.split("'")[1]: h for h in hits}
    assert by_field["email"].category == "data_minimisation"
    assert by_field["ssn"].category == "special_category_data"


def test_flags_field_on_pydantic_model():
    source = "class UserIn(BaseModel):\n    email: str\n    phone: str\n"
    hits = _detect_python(_python_context(source))
    names = {h.summary.split("'")[1] for h in hits}
    assert names == {"email", "phone"}


def test_does_not_flag_email_on_plain_non_model_class():
    # A class with no model base, no mapped_column/Column, no @dataclass —
    # its `email` attribute must NOT fire (structural signal is the point).
    source = "class Mailer:\n    email = 'noreply@example.com'\n"
    assert _detect_python(_python_context(source)) == []


def test_does_not_flag_bare_module_level_variable():
    # A bare module-level variable named `email` must NOT fire — only an
    # attribute inside a qualifying class body is evidence.
    assert _detect_python(_python_context("email = get_email()\n")) == []


def test_does_not_flag_function_parameter():
    source = "def send(email, phone):\n    return email\n"
    assert _detect_python(_python_context(source)) == []


def test_dataclass_model_fires_at_low_confidence():
    source = "@dataclass\nclass Profile:\n    email: str\n"
    hits = _detect_python(_python_context(source))
    assert len(hits) == 1
    assert hits[0].confidence == "low"


def test_reasoning_states_name_alone_is_insufficient():
    source = "class User(Base):\n    email = mapped_column(String)\n"
    hits = _detect_python(_python_context(source))
    assert "does not establish GDPR processing" in hits[0].reasoning


def _nonpython_context(path: str, source: str, language: str | None) -> RuleContext:
    return RuleContext(
        relative_path=path,
        language=language,
        component_type="application_code",
        text=source,
        tree=None,
    )


def test_non_python_regex_fallback_is_low_confidence():
    hits = _detect_generic_regex(
        _nonpython_context("models/user.rb", "  email: string\n", "ruby")
    )
    assert len(hits) == 1
    assert hits[0].confidence == "low"


def test_regex_fallback_skips_python_files():
    # Guard against double-reporting: the regex path must no-op when a tree
    # is present (Python is covered by the AST path).
    ctx = _python_context("class User(Base):\n    email = mapped_column(String)\n")
    assert _detect_generic_regex(ctx) == []
