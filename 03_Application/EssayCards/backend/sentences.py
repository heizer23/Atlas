"""
split_sentences — the single canonical sentence splitter for essay section
body_markdown (Sprint13_ReviewStatsSentenceFeedback).

Pure function, no I/O. Used by backend/routers/sentence_feedback.py for BOTH
the GET /essays/{id}/sentences list and PATCH write-time validation, so there
is exactly one implementation (the frontend never re-splits).

A sentence is identified by its 0-based position in the returned list
(sentence_index). Algorithm:
  1. Normalize line endings to \\n and strip the whole text.
  2. Drop fenced-code delimiter lines (^```.*$) and their content lines.
  3. Join the remaining lines with a single space.
  4. Split on (?<=[.!?])\\s+(?=[A-Z0-9"'(\\[]) — sentence-ending punctuation,
     whitespace, then an uppercase letter, digit, quote or open bracket/paren.
     Markdown link/image/nugget-ref syntax contains no whitespace after a
     '.'/'!'/'?', so it is never split.
  5. Strip each fragment, drop empties.
Markdown formatting is preserved VERBATIM in each fragment (not stripped);
the frontend re-renders each fragment through ReactMarkdown.
Best-effort, English-only.
"""

import re

_FENCE_RE = re.compile(r"^```.*$")
_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])")


def split_sentences(body_markdown: str) -> list[str]:
    text = (body_markdown or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    kept: list[str] = []
    in_fence = False
    for line in text.split("\n"):
        if _FENCE_RE.match(line.strip()):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        kept.append(line.strip())
    joined = " ".join(l for l in kept if l)
    return [s.strip() for s in _SENTENCE_BOUNDARY_RE.split(joined) if s.strip()]
