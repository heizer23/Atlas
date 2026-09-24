"""
The single canonical paragraph-split/render function, shared verbatim by
ingestion (backend/ingest.py) and the version-content read endpoint
(backend/routers/stories.py::get_version_content), and by POST /annotations'
bounds validation. Pure function, no I/O, no DB access.

Algorithm (10_architecture.json §contracts.invariants — implement exactly,
do not re-derive):
  1. Normalize line endings to \\n and strip leading/trailing whitespace from
     the whole text.
  2. Split on any run of one-or-more blank (whitespace-only) lines into
     ordered raw blocks. A document with no blank line anywhere is exactly
     one block.
  3. For each block, strip a single matching prefix from the start of each of
     its lines, checked in this fixed order: heading marker (^#{1,6}\\s+),
     blockquote marker (^>\\s?, applied repeatedly per line for nested
     quotes), unordered list marker (^[-*+]\\s+), ordered list marker
     (^\\d+\\.\\s+), or a fenced-code delimiter line (^```.*$ — the delimiter
     line itself is dropped entirely; its content lines pass through
     unchanged).
  4. Strip inline emphasis markers **, *, _, `, ~~ (removing the marker
     characters, keeping the enclosed text) and rewrite [text](url) to text.
  5. Join the block's processed lines with a single space to produce one
     paragraph string.

A multi-line list or blockquote block renders as exactly ONE paragraph, not
one per line/item. A code block is likewise one paragraph, its fence markers
dropped and its content lines space-joined as literal text. paragraph_index
is the 0-based position of a block in this final ordered list.
"""

from __future__ import annotations

import re

_HEADING_RE     = re.compile(r"^#{1,6}\s+")
_BLOCKQUOTE_RE  = re.compile(r"^>\s?")
_ULIST_RE       = re.compile(r"^[-*+]\s+")
_OLIST_RE       = re.compile(r"^\d+\.\s+")
_FENCE_RE       = re.compile(r"^```.*$")

_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")


def _strip_line_prefix(line: str) -> tuple[str | None, bool]:
    """Returns (processed_line, drop_entirely).

    drop_entirely is True only for a fenced-code delimiter line, which is
    removed from the block's output altogether rather than kept as an empty
    string.
    """
    m = _HEADING_RE.match(line)
    if m:
        return line[m.end():], False

    if _BLOCKQUOTE_RE.match(line):
        stripped = line
        while True:
            m2 = _BLOCKQUOTE_RE.match(stripped)
            if not m2:
                break
            stripped = stripped[m2.end():]
        return stripped, False

    m = _ULIST_RE.match(line)
    if m:
        return line[m.end():], False

    m = _OLIST_RE.match(line)
    if m:
        return line[m.end():], False

    if _FENCE_RE.match(line):
        return None, True

    return line, False


def _strip_inline_markup(text: str) -> str:
    """Removes **, ~~, *, _, ` marker characters (keeping enclosed text) and
    rewrites [text](url) to text.
    """
    text = _LINK_RE.sub(r"\1", text)
    text = text.replace("**", "")
    text = text.replace("~~", "")
    text = text.replace("*", "")
    text = text.replace("_", "")
    text = text.replace("`", "")
    return text


def split_paragraphs(body_markdown: str) -> list[str]:
    """Renders body_markdown into an ordered list of plain-text paragraph
    strings per the algorithm documented in this module's docstring.
    """
    text = body_markdown.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return []

    # Step 2: split into blank-line-separated blocks.
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in text.split("\n"):
        if line.strip() == "":
            if current:
                blocks.append(current)
                current = []
        else:
            current.append(line)
    if current:
        blocks.append(current)

    paragraphs: list[str] = []
    for block in blocks:
        processed_lines: list[str] = []
        for line in block:
            stripped, drop = _strip_line_prefix(line)
            if drop:
                continue
            processed_lines.append(stripped)
        joined = " ".join(processed_lines)
        paragraphs.append(_strip_inline_markup(joined))

    return paragraphs
