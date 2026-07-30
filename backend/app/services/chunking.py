import re
from dataclasses import dataclass

from app.services.parsing import ParsedSection

# ltree labels may only contain letters, digits, and underscores.
_LTREE_LABEL_INVALID = re.compile(r"[^a-zA-Z0-9_]+")


def _sanitize_label(text: str) -> str:
    cleaned = _LTREE_LABEL_INVALID.sub("_", text.strip()).strip("_")
    return cleaned.lower() or "section"


@dataclass
class ChunkRecord:
    """Plain data — no DB/ORM coupling, so chunking logic is testable without
    a database. `parent_path` is the ltree path of the nearest *persisted*
    ancestor chunk (not necessarily the immediate parent heading, which may
    itself have no body text of its own — common for a grouping heading like
    "A.8 Asset Management" whose actual content lives in its numbered
    sub-clauses). The caller resolves `parent_path` to a real `parent_chunk_id`
    once rows exist.
    """

    clause_number: str | None
    title: str
    text: str
    path: str
    order_in_parent: int
    parent_path: str | None


def build_chunks(root: ParsedSection, document_slug: str) -> list[ChunkRecord]:
    """Walk the heading tree, emitting one ChunkRecord per section that has
    its own body text — this is the clause-boundary chunking rule: a chunk
    is exactly one clause/sub-clause's content, never more, never split
    mid-clause.
    """
    records: list[ChunkRecord] = []
    root_path = _sanitize_label(document_slug)

    def walk(
        section: ParsedSection,
        ancestor_path_parts: list[str],
        nearest_chunk_path: str | None,
        order_in_parent: int,
    ) -> None:
        label = _sanitize_label(section.clause_number or section.title)
        path = ".".join([*ancestor_path_parts, label])

        child_nearest_chunk_path = nearest_chunk_path
        if section.text:
            records.append(
                ChunkRecord(
                    clause_number=section.clause_number,
                    title=section.title,
                    text=section.text,
                    path=path,
                    order_in_parent=order_in_parent,
                    parent_path=nearest_chunk_path,
                )
            )
            child_nearest_chunk_path = path

        for index, child in enumerate(section.children):
            walk(child, [*ancestor_path_parts, label], child_nearest_chunk_path, index)

    for index, child in enumerate(root.children):
        walk(child, [root_path], None, index)

    return records
