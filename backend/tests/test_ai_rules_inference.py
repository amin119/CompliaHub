from app.services.ai_analysis.inference_detection import _detect_python
from app.services.security_analysis.ast_utils import safe_parse
from app.services.security_analysis.base import RuleContext


def _python_context(source: str) -> RuleContext:
    return RuleContext(
        relative_path="app/inference.py",
        language="python",
        component_type="application_code",
        text=source,
        tree=safe_parse(source),
    )


def test_flags_inference_call_with_ai_import():
    source = "import openai\n\ndef ask(question):\n    return client.chat(question)\n"
    hits = _detect_python(_python_context(source))
    assert len(hits) == 1
    assert hits[0].confidence == "medium"


def test_does_not_flag_inference_shaped_call_without_ai_import():
    # 'generate' is a common word — without a corroborating AI import in
    # this file, it must not fire (avoids flagging e.g. a report generator).
    source = "def generate(self):\n    return self.build_report()\n"
    assert _detect_python(_python_context(source)) == []


def test_does_not_flag_unrelated_method_with_ai_import():
    source = "import openai\n\ndef close(self):\n    return self.connection.close()\n"
    assert _detect_python(_python_context(source)) == []


def test_dedupes_multiple_calls_same_line():
    source = "import openai\n\ndef f():\n    return a.generate(client.chat(1))\n"
    hits = _detect_python(_python_context(source))
    # Both calls are on the same line — only one hit per line.
    assert len({(h.line_start, h.line_end) for h in hits}) == len(hits)
