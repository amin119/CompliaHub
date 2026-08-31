from app.services.security_analysis.ast_utils import safe_parse
from app.services.security_analysis.base import RuleContext
from app.services.security_analysis.cryptography_rules import _detect_generic_regex, _detect_python


def _python_context(source: str) -> RuleContext:
    return RuleContext(
        relative_path="app/auth.py",
        language="python",
        component_type="application_code",
        text=source,
        tree=safe_parse(source),
    )


def test_md5_in_hash_password_function_is_high_confidence():
    source = "def hash_password(pw):\n    return hashlib.md5(pw).hexdigest()\n"
    hits = _detect_python(_python_context(source))
    assert len(hits) == 1
    assert hits[0].severity == "HIGH"
    assert hits[0].confidence == "high"
    assert hits[0].status == "POTENTIAL_NON_COMPLIANCE"


def test_md5_in_cache_key_function_is_low_confidence_not_suppressed():
    source = "def cache_key(data):\n    return hashlib.md5(data).hexdigest()\n"
    hits = _detect_python(_python_context(source))
    assert len(hits) == 1
    assert hits[0].severity == "LOW"
    assert hits[0].confidence == "low"
    assert hits[0].status == "REQUIRES_HUMAN_REVIEW"


def test_md5_with_ambiguous_context_is_medium():
    source = "def process(data):\n    return hashlib.md5(data).hexdigest()\n"
    hits = _detect_python(_python_context(source))
    assert len(hits) == 1
    assert hits[0].severity == "MEDIUM"
    assert hits[0].confidence == "medium"


def test_detects_sha1():
    source = "digest = hashlib.sha1(data).hexdigest()\n"
    hits = _detect_python(_python_context(source))
    assert len(hits) == 1


def test_detects_ecb_mode():
    source = "cipher = AES.new(key, AES.MODE_ECB)\n"
    hits = _detect_python(_python_context(source))
    assert any("ECB" in h.title for h in hits)


def test_no_hits_for_strong_hash():
    source = "digest = hashlib.sha256(data).hexdigest()\n"
    assert _detect_python(_python_context(source)) == []


def test_generic_regex_for_non_python():
    context = RuleContext(
        relative_path="Auth.java",
        language="java",
        component_type="application_code",
        text="MessageDigest.getInstance(\"MD5\");\n",
        tree=None,
    )
    hits = _detect_generic_regex(context)
    assert len(hits) == 1
    assert hits[0].confidence == "medium"
