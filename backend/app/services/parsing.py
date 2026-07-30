import re
from dataclasses import dataclass, field
from io import BytesIO

from docling.document_converter import DocumentConverter
from docling_core.types.doc import SectionHeaderItem, TextItem
from docling_core.types.io import DocumentStream

# Ordered so the more specific patterns (Article/Annex) are tried before the
# generic numeric ones — "Article 32" would otherwise partially match the
# bare-number pattern's word boundary check and lose the "Article" label.
_CLAUSE_PATTERNS = [
    re.compile(r"^(Article\s+\d+[a-z]?)\b", re.IGNORECASE),
    re.compile(r"^(Annex\s+[A-Z](?:\.\d+)*)\b", re.IGNORECASE),
    re.compile(r"^([A-Z]\.\d+(?:\.\d+)*)\b"),  # e.g. A.8.1
    re.compile(r"^(\d+(?:\.\d+)+)\b"),  # e.g. 4.2.3
]


def extract_clause_number(heading_text: str) -> str | None:
    """Docling knows this is a heading; it has no idea our domain numbers
    clauses like "A.8.1" or "Article 32". This is where that domain knowledge
    gets bolted on, purely from the heading text itself.
    """
    stripped = heading_text.strip()
    for pattern in _CLAUSE_PATTERNS:
        match = pattern.match(stripped)
        if match:
            return match.group(1)
    return None


@dataclass
class ParsedSection:
    """One node in the document's heading tree. `text` accumulates any body
    paragraphs that appear directly under this heading (before the next one).
    """

    title: str
    level: int
    clause_number: str | None
    text: str = ""
    children: list["ParsedSection"] = field(default_factory=list)


def parse_document(data: bytes, filename: str) -> ParsedSection:
    """Convert raw file bytes into a heading tree, preserving the
    Standard -> Part -> Clause -> Sub-clause -> Control hierarchy instead of
    flattening the document into one blob of text.
    """
    converter = DocumentConverter()
    stream = DocumentStream(name=filename, stream=BytesIO(data))
    result = converter.convert(stream)
    doc = result.document

    root = ParsedSection(title=filename, level=0, clause_number=None)
    # Stack of ancestors currently "open" — each new item attaches under the
    # deepest ancestor whose level is still less than the item's own level.
    stack: list[ParsedSection] = [root]

    for item, level in doc.iterate_items():
        if isinstance(item, SectionHeaderItem):
            section = ParsedSection(
                title=item.text,
                level=level,
                clause_number=extract_clause_number(item.text),
            )
            while len(stack) > 1 and stack[-1].level >= level:
                stack.pop()
            stack[-1].children.append(section)
            stack.append(section)
        elif isinstance(item, TextItem):
            target = stack[-1]
            target.text = f"{target.text}\n{item.text}".strip() if target.text else item.text

    return root
