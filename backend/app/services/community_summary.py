import time
from typing import Protocol

from google import genai
from google.genai import errors, types
from pydantic import BaseModel, ValidationError

from app.core.config import get_settings
from app.services.graph_store import RelationEdge
from app.services.ontology import EntityType

_SYSTEM_PROMPT = (
    "You are summarizing one cluster of related entities from a compliance "
    "knowledge graph spanning ISO 27001, ISO 42001, and GDPR. Given the "
    "cluster's entities and the relations between them, write a short title "
    "and a 2-4 sentence summary describing the common theme this cluster "
    "represents. Base the summary only on the given entities and relations "
    "— do not invent facts."
)

_MAX_RETRIES = 3
_RETRY_BASE_DELAY_SECONDS = 2.0


class CommunitySummary(BaseModel):
    """A short natural-language description of one graph community."""

    title: str
    summary: str


class SummaryRateLimited(Exception):
    """Mirrors extraction.py's ExtractionRateLimited — same "the provider
    rate-limited us" abstraction, so the retry loop below doesn't depend on
    which provider is behind SummaryClient.
    """


class SummaryClient(Protocol):
    def summarize(self, community_text: str) -> CommunitySummary: ...


class _GeminiSummaryClient:
    """Same adapter shape as `extraction._GeminiExtractionClient` (forced
    schema, re-validated via `model_validate_json` rather than trusting
    `.parsed`). Deliberately not sharing code with that adapter despite the
    near-identical structure: different system prompt, different response
    schema, no shared call site — factoring out a common base for two
    call sites that only *happen* to look similar today would be premature.
    """

    def __init__(self, api_key: str, model: str) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def summarize(self, community_text: str) -> CommunitySummary:
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=community_text,
                config=types.GenerateContentConfig(
                    system_instruction=_SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_schema=CommunitySummary,
                ),
            )
        except errors.ClientError as exc:
            if exc.code == 429:
                raise SummaryRateLimited(str(exc)) from exc
            raise

        return CommunitySummary.model_validate_json(response.text)


def get_gemini_client() -> SummaryClient:
    settings = get_settings()
    return _GeminiSummaryClient(
        api_key=settings.gemini_api_key, model=settings.gemini_extraction_model
    )


def format_community_text(
    members: list[tuple[EntityType, str]],
    relations: list[RelationEdge],
) -> str:
    """Renders a community's members and intra-community relations as plain
    text for the LLM prompt — same "just format it as readable text"
    approach the rest of the project uses for LLM inputs.
    """
    member_names = {name for _, name in members}
    lines = ["Entities:"]
    lines.extend(f"- {name} ({entity_type.value})" for entity_type, name in members)

    intra_relations = [
        relation
        for relation in relations
        if relation.source_name in member_names and relation.target_name in member_names
    ]
    if intra_relations:
        lines.append("\nRelations:")
        lines.extend(
            f"- {relation.source_name} {relation.relation_type} {relation.target_name}"
            for relation in intra_relations
        )
    return "\n".join(lines)


def summarize_community(
    members: list[tuple[EntityType, str]],
    relations: list[RelationEdge],
    client: SummaryClient | None = None,
) -> CommunitySummary:
    """Summarizes one community. Same retry shape as
    `extraction.extract_chunk_text`: retries rate limits with exponential
    backoff and schema-validation failures (stochastic output, a fresh
    sample can succeed).
    """
    client = client or get_gemini_client()
    community_text = format_community_text(members, relations)

    for attempt in range(_MAX_RETRIES):
        try:
            return client.summarize(community_text)
        except SummaryRateLimited:
            if attempt == _MAX_RETRIES - 1:
                raise
            time.sleep(_RETRY_BASE_DELAY_SECONDS * (2**attempt))
        except ValidationError:
            if attempt == _MAX_RETRIES - 1:
                raise
    raise AssertionError("unreachable")  # loop always returns or raises above
