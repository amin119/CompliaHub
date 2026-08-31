from app.services.ai_analysis.agentic_detection import _detect_python
from app.services.security_analysis.ast_utils import safe_parse
from app.services.security_analysis.base import RuleContext


def _python_context(source: str) -> RuleContext:
    return RuleContext(
        relative_path="app/agent.py",
        language="python",
        component_type="application_code",
        text=source,
        tree=safe_parse(source),
    )


def test_flags_tool_decorator():
    source = "@tool\ndef search_web(query):\n    ...\n"
    hits = _detect_python(_python_context(source))
    assert len(hits) == 1


def test_flags_bind_tools_call():
    hits = _detect_python(_python_context("model.bind_tools([search_web])\n"))
    assert len(hits) == 1


def test_flags_stategraph_construction():
    hits = _detect_python(_python_context("graph = StateGraph(AgentState)\n"))
    assert len(hits) == 1


def test_flags_add_node_call():
    hits = _detect_python(_python_context("graph.add_node('plan', plan_node)\n"))
    assert len(hits) == 1


def test_does_not_flag_unrelated_decorator():
    source = "@property\ndef name(self):\n    return self._name\n"
    assert _detect_python(_python_context(source)) == []


def test_does_not_flag_unrelated_call():
    assert _detect_python(_python_context("result = some_function(1, 2)\n")) == []
