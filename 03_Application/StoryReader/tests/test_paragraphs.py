"""
Unit tests of backend.paragraphs.split_paragraphs — the single canonical
paragraph-split function shared by ingestion and the version-content read
endpoint. No DB, no HTTP. Traceability: 10_test_spec.md "Paragraph split — *"
scenarios, plus the additional coverage named in
Sprint01_Core/10_architecture.json §deferrals.test_writer.
"""

from backend.paragraphs import split_paragraphs


def test_blank_line_separated_paragraphs():
    text = "First plain block of text.\n\nSecond plain block of text."
    result = split_paragraphs(text)
    assert result == ["First plain block of text.", "Second plain block of text."]


def test_multiline_unordered_list_is_one_paragraph():
    text = "- item one\n- item two\n- item three"
    result = split_paragraphs(text)
    assert len(result) == 1
    assert result[0] == "item one item two item three"


def test_multiline_blockquote_is_one_paragraph():
    text = "> first quoted line\n> second quoted line"
    result = split_paragraphs(text)
    assert len(result) == 1
    assert result[0] == "first quoted line second quoted line"


def test_nested_blockquote_strips_repeated_markers():
    text = "> > deeply quoted line"
    result = split_paragraphs(text)
    assert result == ["deeply quoted line"]


def test_fenced_code_block_is_one_paragraph_with_fences_dropped():
    text = "```python\nprint('hi')\nreturn 1\n```"
    result = split_paragraphs(text)
    assert len(result) == 1
    assert "```" not in result[0]
    assert result[0] == "print('hi') return 1"


def test_no_blank_line_document_is_exactly_one_paragraph():
    text = "Line one of a document\nwith no blank line\nanywhere in it."
    result = split_paragraphs(text)
    assert len(result) == 1
    assert result[0] == "Line one of a document with no blank line anywhere in it."


def test_ordered_list_is_one_paragraph():
    text = "1. first step\n2. second step"
    result = split_paragraphs(text)
    assert result == ["first step second step"]


def test_heading_marker_stripped():
    text = "## A Heading"
    result = split_paragraphs(text)
    assert result == ["A Heading"]


def test_inline_emphasis_and_link_markup_stripped():
    text = "This is **bold**, _italic_, `code`, and a [link](https://example.com)."
    result = split_paragraphs(text)
    assert result == ["This is bold, italic, code, and a link."]


def test_empty_document_returns_no_paragraphs():
    assert split_paragraphs("") == []
    assert split_paragraphs("   \n\n  ") == []
