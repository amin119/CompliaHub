"""Platform Phase 7: one-off authoring aid that drafts initial `eval_questions`
rows against this project's REAL ingested corpus (ISO 27001/42001/GDPR
standards) — NOT idempotent or meant to be re-run routinely, same "tune
against real use, don't over-engineer" spirit this codebase applies to
other empirical/one-time constants.

Every row is written with `source="llm_drafted"`, `human_reviewed=False` —
this script drafts CANDIDATES, not trustworthy ground truth. A person must
review and edit each one via `PATCH /eval/questions/{id}` before an eval run
against them means anything (see docs/phase-7-evaluation.md).

Usage (from `backend/`):
    uv run python scripts/generate_eval_questions.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import truststore  # noqa: E402

# Must run before any other import creates an SSL context — same fix
# app/main.py applies for the same reason: outbound HTTPS from Python
# running natively on this Windows host fails TLS cert verification against
# Gemini otherwise (caught live on this script's second run — main.py's own
# fix never applies here since this is a standalone script, not the FastAPI
# app). See app/main.py's own comment for the full explanation.
truststore.inject_into_ssl()

from google import genai  # noqa: E402
from google.genai import types  # noqa: E402
from pydantic import BaseModel  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.db import SessionLocal  # noqa: E402
from app.models.document import Chunk, Document  # noqa: E402
from app.models.evaluation import EvalQuestion  # noqa: E402

# The roadmap's own 5 use-case categories (docs/phase-7-evaluation.md) — one
# drafting pass per category, ~6-10 questions each, targeting the 30-50
# total the roadmap asks for.
_USE_CASE_CATEGORIES = {
    "cross_standard_mapping": (
        "Questions comparing or relating requirements ACROSS two different "
        "standards (e.g. what one standard requires that another doesn't, "
        "or how a requirement in one maps to a control in another)."
    ),
    "gap_analysis": (
        "Questions asking whether the corpus's standards impose a specific "
        "obligation, framed so a real gap (a requirement genuinely present "
        "or absent) would matter."
    ),
    "multi_hop_traversal": (
        "Questions whose answer depends on connecting two or more related "
        "requirements/controls/roles together, not answerable from a "
        "single isolated clause."
    ),
    "audit_evidence_lookup": (
        "Direct factual questions answerable from one or a few specific "
        "clauses (e.g. what does clause X require)."
    ),
    "impact_analysis": (
        "Questions about what changes/consequences follow if a specific "
        "requirement isn't met, or what a given control is meant to "
        "mitigate."
    ),
}

_QUESTIONS_PER_CATEGORY = 8
_CHUNKS_PER_PROMPT = 25


class DraftedCitation(BaseModel):
    """A named-fields model, not a bare `dict` — Gemini's structured-output
    schema (Developer API mode) rejects `additionalProperties`, which
    Pydantic's JSON-schema generation implicitly emits for a bare `dict`
    field. Caught live on this script's first real run.
    """

    document_filename: str
    clause_number: str | None = None


class DraftedQuestion(BaseModel):
    question: str
    ground_truth_answer: str
    ground_truth_citations: list[DraftedCitation]


class DraftedQuestionSet(BaseModel):
    questions: list[DraftedQuestion]


def _sample_chunks(db) -> list[Chunk]:
    """A flat sample across every ingested document, not exhaustive — real
    excerpts are only meant to ground the drafted questions in genuine
    content, not to be an exhaustive corpus dump into one prompt.
    """
    return list(
        db.scalars(
            select(Chunk).where(Chunk.clause_number.is_not(None)).limit(_CHUNKS_PER_PROMPT)
        )
    )


def _format_excerpts(chunks: list[Chunk], documents_by_id: dict) -> str:
    parts = []
    for chunk in chunks:
        filename = documents_by_id[chunk.document_id].filename
        label = chunk.clause_number or chunk.title or "excerpt"
        parts.append(f"[{filename} — {label}] {chunk.text}")
    return "\n\n".join(parts)


def _draft_questions_for_category(
    client: genai.Client, model: str, category: str, description: str, excerpts_text: str
) -> DraftedQuestionSet:
    system_prompt = (
        "You are drafting candidate evaluation questions for a compliance "
        "Q&A system, GROUNDED ONLY in the real excerpts given below — never "
        "invent a clause, control, or fact not present in them. Category: "
        f"{category} — {description}\n\n"
        f"Draft exactly {_QUESTIONS_PER_CATEGORY} distinct questions of this "
        "category. For each, write a real ground_truth_answer answerable "
        "from the given excerpts, and ground_truth_citations listing every "
        "excerpt's [document_filename, clause_number] you drew the answer "
        "from. These are DRAFT candidates a human will review before use — "
        "prefer being conservative/accurate over creative."
    )
    response = client.models.generate_content(
        model=model,
        contents=f"EXCERPTS:\n\n{excerpts_text}",
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            response_schema=DraftedQuestionSet,
        ),
    )
    return DraftedQuestionSet.model_validate_json(response.text)


def main() -> None:
    settings = get_settings()
    client = genai.Client(api_key=settings.gemini_api_key)
    db = SessionLocal()

    try:
        chunks = _sample_chunks(db)
        if not chunks:
            print("No ingested chunks with a clause_number found — ingest a standard first.")
            return

        documents_by_id = {
            document.id: document
            for document in db.scalars(
                select(Document).where(
                    Document.id.in_({chunk.document_id for chunk in chunks})
                )
            )
        }
        excerpts_text = _format_excerpts(chunks, documents_by_id)

        total_written = 0
        for category, description in _USE_CASE_CATEGORIES.items():
            print(f"Drafting {_QUESTIONS_PER_CATEGORY} questions for '{category}'...")
            drafted = _draft_questions_for_category(
                client, settings.gemini_eval_model, category, description, excerpts_text
            )
            for item in drafted.questions:
                db.add(
                    EvalQuestion(
                        question=item.question,
                        use_case_category=category,
                        ground_truth_answer=item.ground_truth_answer,
                        ground_truth_citations=[
                            citation.model_dump() for citation in item.ground_truth_citations
                        ],
                        source="llm_drafted",
                        human_reviewed=False,
                    )
                )
                total_written += 1
            db.commit()

        print(
            f"Wrote {total_written} draft eval_questions rows (human_reviewed=False). "
            "Review each via GET/PATCH /eval/questions before running an eval against them."
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
