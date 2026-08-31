from app.services.security_analysis.base import RuleContext
from app.services.security_analysis.insecure_config import (
    _detect_cors_wildcard,
    _detect_debug_true,
    _detect_dockerfile_root,
    _detect_privileged_compose,
)


def _context(path: str, text: str) -> RuleContext:
    return RuleContext(
        relative_path=path, language=None, component_type="infrastructure_as_code",
        text=text, tree=None,
    )


def test_dockerfile_with_no_user_is_flagged():
    hits = _detect_dockerfile_root(_context("Dockerfile", "FROM python:3.12\nCMD [\"app\"]\n"))
    assert len(hits) == 1


def test_dockerfile_with_root_user_is_flagged():
    text = "FROM python:3.12\nUSER root\nCMD [\"app\"]\n"
    hits = _detect_dockerfile_root(_context("Dockerfile", text))
    assert len(hits) == 1


def test_dockerfile_with_non_root_user_is_not_flagged():
    text = "FROM python:3.12\nUSER appuser\nCMD [\"app\"]\n"
    assert _detect_dockerfile_root(_context("Dockerfile", text)) == []


def test_ignores_non_dockerfile():
    assert _detect_dockerfile_root(_context("Dockerfile.md", "USER root\n")) == []


def test_flags_privileged_compose():
    text = "services:\n  app:\n    privileged: true\n"
    hits = _detect_privileged_compose(_context("docker-compose.yml", text))
    assert len(hits) == 1
    assert hits[0].severity == "HIGH"


def test_ignores_non_privileged_compose():
    text = "services:\n  app:\n    image: python:3.12\n"
    assert _detect_privileged_compose(_context("docker-compose.yml", text)) == []


def test_flags_debug_true():
    hits = _detect_debug_true(_context("settings.py", "DEBUG = True\n"))
    assert len(hits) == 1


def test_flags_cors_wildcard_python():
    text = 'app.add_middleware(CORSMiddleware, allow_origins=["*"])\n'
    hits = _detect_cors_wildcard(_context("main.py", text))
    assert len(hits) == 1


def test_does_not_flag_scoped_cors():
    text = 'app.add_middleware(CORSMiddleware, allow_origins=["https://example.com"])\n'
    assert _detect_cors_wildcard(_context("main.py", text)) == []
