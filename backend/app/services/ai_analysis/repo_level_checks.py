"""Repo-level AI/ISO 42001 checks — the aggregate "is this repository an
AI system, and what does it consist of" question, plus the governance
findings the spec explicitly says cannot be verified from code alone.

Unlike Phase 3's GDPR organizational findings (which fire on every scan,
since near-any backend can plausibly process some personal data), these
governance findings only fire when the repo-level AI-detection threshold
below is met: most scanned repositories are not AI systems at all, and
nine unconditional "AI risk management undocumented" findings against a
plain CRUD backend would be noise, not a genuine gap — a deliberate,
documented departure from Phase 3's own precedent, not an inconsistency.

This phase never parses a model card's *prose* — presence of a
model-card-shaped doc only softens confidence, exactly like Phase 3's
privacy-doc check.
"""

from __future__ import annotations

from app.services.ai_analysis.base import RuleHit

# The spec's own "cannot be verified technically" AI-governance list.
_FIXED_GOVERNANCE_FINDINGS: list[tuple[str, str, str]] = [
    (
        "ai_system_documentation",
        "AI system documentation not verifiable",
        "Whether this AI system has documentation describing its purpose, scope, and "
        "operation cannot be determined from source code alone.",
    ),
    (
        "intended_purpose",
        "Documented intended purpose not verifiable",
        "Whether this AI system's intended purpose has been formally documented cannot be "
        "determined from source code alone.",
    ),
    (
        "risk_management",
        "AI risk management process not verifiable",
        "Whether an AI-specific risk management process has been applied to this system "
        "cannot be determined from source code alone.",
    ),
    (
        "human_oversight",
        "Human oversight mechanism not verifiable",
        "Whether a human oversight mechanism governs this AI system's decisions or outputs "
        "cannot be determined from source code alone.",
    ),
    (
        "model_evaluation",
        "Model evaluation methodology not verifiable",
        "Whether the models used by this system have a documented evaluation methodology "
        "cannot be determined from source code alone.",
    ),
    (
        "monitoring_logging",
        "AI monitoring/logging coverage not verifiable",
        "Whether this AI system's behavior is monitored in production, beyond what generic "
        "application logging captures, cannot be determined from source code alone.",
    ),
    (
        "incident_handling",
        "AI incident handling process not verifiable",
        "Whether a process exists for handling AI-specific incidents (e.g. harmful or "
        "incorrect outputs) cannot be determined from source code alone.",
    ),
    (
        "lifecycle_management",
        "AI system lifecycle management not verifiable",
        "Whether this AI system's models/prompts are version-controlled and reviewed "
        "through a defined lifecycle process cannot be determined from source code alone.",
    ),
    (
        "third_party_ai_providers",
        "Third-party AI provider risk not verifiable",
        "Whether the risk of relying on third-party AI providers detected in this "
        "repository (model deprecation, behavior changes, availability) has been assessed "
        "cannot be determined from source code alone. This is the AI-specific angle on the "
        "same underlying fact GDPR's 'third_party_contracts' finding covers from a data-"
        "processing-agreement perspective — related, not duplicated.",
    ),
]

_MODEL_CARD_FILENAMES = {
    "model_card.md",
    "model-card.md",
    "ai_governance.md",
    "ai-governance.md",
    "model_cards.md",
}

# The minimum number of *distinct* independent signal categories required
# before the repo-level inventory/governance findings fire at all — the
# spec's own "do not classify a project as AI because one dependency
# exists" instruction, applied at the repo level.
MINIMUM_SIGNAL_TYPES_FOR_AI_SYSTEM = 2


def model_card_doc_present(repository_files) -> bool:
    """`repository_files` is an iterable of objects with `.component_type`
    and `.relative_path` — true if any is a documentation file with a
    model-card/AI-governance-shaped filename.
    """
    for repository_file in repository_files:
        if repository_file.component_type != "documentation":
            continue
        filename = repository_file.relative_path.replace("\\", "/").rsplit("/", 1)[-1].lower()
        if filename in _MODEL_CARD_FILENAMES:
            return True
    return False


def build_ai_repo_level_findings(
    signal_categories: set[str],
    ai_provider_labels: set[str],
    model_card_present: bool,
) -> list[tuple[str, RuleHit]]:
    """`signal_categories` is the set of `AI_RULES` categories that
    produced at least one hit anywhere in the scan (the per-file rules'
    own results *are* the signal — no separate detection pass). Below the
    threshold, this returns an empty list: no inventory, no governance
    findings — a single stray AI import must not turn a plain CRUD repo
    into nine "AI governance missing" findings.
    """
    if len(signal_categories) < MINIMUM_SIGNAL_TYPES_FOR_AI_SYSTEM:
        return []

    hits: list[tuple[str, RuleHit]] = []

    uses_rag = "rag_detection" in signal_categories
    uses_tools = "agentic_pattern_detection" in signal_categories
    inventory_metadata = {
        "models": [
            {"provider": label, "model": "detected_from_code"}
            for label in sorted(ai_provider_labels)
        ],
        "uses_rag": uses_rag,
        "uses_tools": uses_tools,
        "external_data": bool(ai_provider_labels),
        # Never inferred from code, per the spec's own explicit instruction
        # and worked example — a hardcoded string, not a placeholder.
        "human_oversight": "unknown",
    }
    signal_categories_label = ", ".join(sorted(signal_categories))
    hits.append((
        "ai_system_inventory",
        RuleHit(
            title="AI system inventory",
            status="REQUIRES_HUMAN_REVIEW",
            severity="MEDIUM",
            confidence="medium",
            summary=(
                f"{len(signal_categories)} independent AI-usage signal types detected "
                f"({signal_categories_label}) — this repository appears to contain an "
                "AI system."
            ),
            reasoning=(
                "Multiple independent signals (not a single dependency) indicate this "
                "repository implements an AI/ML system. The structured inventory below is "
                "derived from code-level patterns only — it is not a substitute for the "
                "system's own documented inventory, and 'human_oversight' is always "
                "'unknown' since that cannot be established from source code."
            ),
            recommendation="Confirm this inventory against the system's actual "
            "documentation, and ensure its intended purpose, risk classification, and "
            "human oversight mechanism are formally recorded.",
            evidence_metadata=inventory_metadata,
        ),
    ))

    confidence = "medium" if model_card_present else "low"
    doc_note = (
        " A model-card/AI-governance-shaped document was found in the repository; its "
        "existence is noted but its content has not been verified by this scan."
        if model_card_present
        else ""
    )
    for category, title, gap in _FIXED_GOVERNANCE_FINDINGS:
        hits.append((
            category,
            RuleHit(
                title=title,
                status="REQUIRES_HUMAN_REVIEW",
                severity="MEDIUM",
                confidence=confidence,
                summary=title + ".",
                reasoning=gap + doc_note,
                recommendation="Confirm this organizational/governance control exists and "
                "is documented for this AI system; a code scan can surface the obligation "
                "but cannot verify it.",
            ),
        ))

    return hits
