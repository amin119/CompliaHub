from app.services.chunking import build_chunks
from app.services.parsing import ParsedSection


def _section(title, clause_number=None, text="", children=None, level=1):
    return ParsedSection(
        title=title, level=level, clause_number=clause_number, text=text, children=children or []
    )


def test_chunks_only_created_for_sections_with_text():
    """A grouping heading like 'A.8 Asset Management' often has no body text
    of its own — only its numbered sub-clauses do. It shouldn't become a
    chunk, but its sub-clauses' ltree paths should still nest under it.
    """
    root = _section("root", level=0)
    grouping = _section("A.8 Asset Management", clause_number="A.8", level=1, text="")
    leaf = _section(
        "A.8.1 Inventory of assets",
        clause_number="A.8.1",
        level=2,
        text="Assets shall be identified.",
    )
    grouping.children.append(leaf)
    root.children.append(grouping)

    chunks = build_chunks(root, "iso27001")

    assert len(chunks) == 1
    assert chunks[0].path == "iso27001.a_8.a_8_1"
    assert chunks[0].parent_path is None


def test_parent_path_points_to_nearest_persisted_ancestor():
    root = _section("root", level=0)
    parent = _section(
        "Article 32", clause_number="Article 32", level=1, text="Security of processing."
    )
    child = _section(
        "Article 32(1)", clause_number="Article 32(1)", level=2, text="Appropriate measures."
    )
    parent.children.append(child)
    root.children.append(parent)

    chunks = build_chunks(root, "gdpr")

    assert len(chunks) == 2
    parent_chunk = next(c for c in chunks if c.title == "Article 32")
    child_chunk = next(c for c in chunks if c.title == "Article 32(1)")
    assert child_chunk.parent_path == parent_chunk.path


def test_order_in_parent_reflects_sibling_position():
    root = _section("root", level=0)
    first = _section("A.1", clause_number="A.1", level=1, text="first")
    second = _section("A.2", clause_number="A.2", level=1, text="second")
    root.children.extend([first, second])

    chunks = build_chunks(root, "standard")

    assert [c.order_in_parent for c in chunks] == [0, 1]
