from app.services.ai_analysis.prompt_detection import _detect_python
from app.services.security_analysis.ast_utils import safe_parse
from app.services.security_analysis.base import RuleContext


def _python_context(source: str) -> RuleContext:
    return RuleContext(
        relative_path="app/prompts.py",
        language="python",
        component_type="application_code",
        text=source,
        tree=safe_parse(source),
    )


def test_flags_prompt_named_variable():
    hits = _detect_python(_python_context('SYSTEM_PROMPT = "You are a helpful assistant."\n'))
    assert len(hits) == 1
    assert hits[0].confidence == "low"  # no corroborating AI import in this file


def test_confidence_boosted_with_ai_import():
    source = 'import openai\n\nPROMPT_TEMPLATE = "Answer: {question}"\n'
    hits = _detect_python(_python_context(source))
    assert len(hits) == 1
    assert hits[0].confidence == "medium"


def test_flags_fstring_prompt():
    hits = _detect_python(_python_context('instructions = f"Summarize: {text}"\n'))
    assert len(hits) == 1


def test_flags_inline_string_passed_to_inference_call():
    hits = _detect_python(_python_context('client.generate("Hello there")\n'))
    assert len(hits) == 1


def test_does_not_flag_non_prompt_string():
    assert _detect_python(_python_context('greeting = "hello world"\n')) == []


def test_does_not_flag_non_string_prompt_assignment():
    assert _detect_python(_python_context("prompt_count = 3\n")) == []
