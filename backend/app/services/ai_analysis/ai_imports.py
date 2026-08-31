"""AI/ML library import detection — the base signal every other Phase 4
rule and the repo-level aggregator build on.

`detect_ai_imports` is the structural building block, kept separate from
the `RuleHit`-producing wrapper below so structured `(name, label, kind)`
data never has to be re-derived by parsing a hit's title/summary text
later — that exact anti-pattern (deriving structured data from title text
instead of carrying it explicitly) caused a real bug in Phase 3's
repo-level findings (see docs/scanner-phase-3-gdpr-analyzer.md bug #3).

A single import alone is only weak evidence (per the spec's own warning
against classifying a project as AI from one dependency) — this rule
fires its own low-confidence per-file finding, but promoting a repository
to "AI system detected" for the inventory/governance findings requires
corroborating signals from the other rule modules (see
`repo_level_checks.build_ai_repo_level_findings`).
"""

from __future__ import annotations

from app.services.ai_analysis.base import FunctionRule, RuleContext, RuleHit
from app.services.security_analysis import ast_utils

# name -> (human label, kind). `kind` distinguishes what *sort* of AI/ML
# signal this is — only "llm_provider" entries populate the inventory's
# `models` list; vector DBs/ML frameworks/agent frameworks are still
# signals but aren't "models" in the spec's own sense.
_AI_ML_PACKAGES: dict[str, tuple[str, str]] = {
    # LLM / embedding providers
    "openai": ("OpenAI", "llm_provider"),
    "anthropic": ("Anthropic", "llm_provider"),
    "cohere": ("Cohere", "llm_provider"),
    "genai": ("Google Gemini", "llm_provider"),
    "google": ("Google AI", "llm_provider"),
    "voyageai": ("Voyage AI", "llm_provider"),
    "ollama": ("Ollama", "llm_provider"),
    "vllm": ("vLLM", "llm_provider"),
    # ML frameworks
    "transformers": ("Hugging Face Transformers", "ml_framework"),
    "huggingface_hub": ("Hugging Face Hub", "ml_framework"),
    "torch": ("PyTorch", "ml_framework"),
    "tensorflow": ("TensorFlow", "ml_framework"),
    "keras": ("Keras", "ml_framework"),
    "sklearn": ("scikit-learn", "ml_framework"),
    "xgboost": ("XGBoost", "ml_framework"),
    # Vector databases
    "pymilvus": ("Milvus", "vector_db"),
    "pinecone": ("Pinecone", "vector_db"),
    "weaviate": ("Weaviate", "vector_db"),
    "chromadb": ("Chroma", "vector_db"),
    "faiss": ("FAISS", "vector_db"),
    "qdrant_client": ("Qdrant", "vector_db"),
    # Agent frameworks
    "langchain": ("LangChain", "agent_framework"),
    "langgraph": ("LangGraph", "agent_framework"),
    "langchain_core": ("LangChain Core", "agent_framework"),
    "llama_index": ("LlamaIndex", "agent_framework"),
}


def detect_ai_imports(context: RuleContext) -> list[tuple[str, str, str, int]]:
    """Returns `(package_name, label, kind, line)` for every distinct
    AI/ML package imported in this file.
    """
    if context.tree is None:
        return []
    seen: set[str] = set()
    results: list[tuple[str, str, str, int]] = []
    for name, line in ast_utils.imported_top_level_names(context.tree):
        entry = _AI_ML_PACKAGES.get(name)
        if entry is None or name in seen:
            continue
        seen.add(name)
        label, kind = entry
        results.append((name, label, kind, line))
    return results


def _detect_python(context: RuleContext) -> list[RuleHit]:
    hits = []
    for name, label, kind, line in detect_ai_imports(context):
        hits.append(
            RuleHit(
                title="AI/ML library imported",
                status="REQUIRES_HUMAN_REVIEW",
                severity="LOW",
                confidence="low",
                summary=f"Imports '{name}' ({label}), a {kind.replace('_', ' ')}.",
                reasoning=(
                    f"Line {line} imports '{name}'. A single AI/ML library import is only "
                    "weak evidence that this repository is an AI system — it does not, on "
                    "its own, establish ISO 42001 applicability. Combined with other "
                    "signals elsewhere in the repository (prompts, inference calls, RAG "
                    "usage, agentic patterns), it contributes to that determination."
                ),
                recommendation="If this is genuinely an AI system, ensure it has a "
                "documented intended purpose, risk management process, and human "
                "oversight mechanism.",
                line_start=line,
                line_end=line,
            )
        )
    return hits


RULES = [
    FunctionRule(
        "AI-IMPORT-PY",
        "ai_system_detection",
        "LOW",
        _detect_python,
        evidence_source_type="ast_analysis",
    ),
]
