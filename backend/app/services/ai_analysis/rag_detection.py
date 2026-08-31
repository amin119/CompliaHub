"""RAG (retrieval-augmented generation) pipeline detection — a conservative,
same-file co-occurrence heuristic: a vector-database import alongside an
embedding-shaped call or a retrieval-shaped function name. Deliberately
file-level, not a real dataflow tracer (no prior phase built real
dataflow tracking either — e.g. `hardcoded_credentials.py` excludes
`Call`-valued assignments rather than tracing them).
"""

from __future__ import annotations

import ast
import re

from app.services.ai_analysis import ai_imports
from app.services.ai_analysis.base import FunctionRule, RuleContext, RuleHit

_EMBEDDING_CALL_RE = re.compile(r"\.(embed|encode|embed_documents|embed_query)\(")
_RETRIEVAL_NAME_RE = re.compile(r"(retrieve|search|similarity|query_index)", re.IGNORECASE)


def _has_vector_db_import(context: RuleContext) -> bool:
    return any(
        kind == "vector_db" for _name, _label, kind, _line in ai_imports.detect_ai_imports(context)
    )


def _has_embedding_or_retrieval_signal(context: RuleContext) -> bool:
    if _EMBEDDING_CALL_RE.search(context.text):
        return True
    if context.tree is None:
        return False
    for node in ast.walk(context.tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _RETRIEVAL_NAME_RE.search(
            node.name
        ):
            return True
    return False


def _detect_python(context: RuleContext) -> list[RuleHit]:
    if context.tree is None:
        return []
    if not _has_vector_db_import(context) or not _has_embedding_or_retrieval_signal(context):
        return []

    return [
        RuleHit(
            title="RAG (retrieval-augmented generation) pattern detected",
            status="REQUIRES_HUMAN_REVIEW",
            severity="MEDIUM",
            confidence="medium",
            summary=(
                f"'{context.relative_path}' imports a vector database alongside an "
                "embedding/retrieval-shaped call."
            ),
            reasoning=(
                "This file imports a vector database and also contains an embedding call "
                "or a retrieval-shaped function name — a same-file co-occurrence "
                "consistent with a RAG pipeline. This is a structural signal, not proof: "
                "it cannot determine what data the retrieved context actually contains."
            ),
            recommendation="If this is a RAG pipeline, ensure the underlying knowledge "
            "base's data governance is documented and retrieved context sources are "
            "traceable.",
        )
    ]


RULES = [
    FunctionRule(
        "AI-RAG-PY", "rag_detection", "MEDIUM", _detect_python, evidence_source_type="ast_analysis"
    ),
]
