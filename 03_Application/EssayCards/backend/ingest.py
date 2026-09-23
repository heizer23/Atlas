"""
One-shot markdown ingestion — CLI entrypoint plus a directly-callable function
for tests.

Grammar (Sprint01_Core/10_architecture.json §internal_flow steps 2-3):
  - YAML front matter delimited by a leading '---' line and the next '---'
    line; requires non-empty 'title' and 'slug'. Optional 'category' (non-empty
    string, defaults to null) and 'sort_index' (integer, defaults to 0) place
    the essay in the overview page's category groups and order it within its
    group. Optional 'status' ('planned' | 'complete', defaults to 'complete').
  - Each '## Heading {#anchor}' line starts a new section, in order of
    appearance. Any '##' heading line missing the '{#anchor}' suffix aborts
    ingestion. Content before the first matched section heading is discarded
    (no essay-level intro field exists in this schema).
  - A section may contain at most one fenced ```flashcards block at its end.
    Zero fences: the whole trimmed section content is body_markdown, no cards.
    One fence: content before it is body_markdown; content after the closing
    fence must be blank, else ingestion aborts. More than one fence aborts.
  - The fenced content is parsed as YAML, expecting a top-level 'cards' list
    of mappings, each requiring non-empty string keys id, q, a.
  - Duplicate anchor_slug across sections, or duplicate card id (card_key)
    across the whole file, aborts ingestion before any database write.

Ingestion is fully transactional: all parsing/validation happens before any
database write. Re-ingestion upserts by stable author-assigned keys (slug /
(essay_id, anchor_slug) / (essay_id, card_key)) and never touches an existing
flashcard's review state — only newly-inserted flashcards get a fresh
flashcard_review_state row (last_reviewed_at=null, next_due_at=created_at).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import yaml

from backend.scheduling import EXPERIMENT_VERSION, decide_scheduler_assignment

# ── Public API ──────────────────────────────────────────────────────────────

# Essay lifecycle (schema.sql ck_essays_status). Shared with the JSON ingest
# path (backend/routers/essays.py). DEFAULT applies when the key is absent from
# a payload — a normal ingest is a finished essay.
VALID_ESSAY_STATUSES = ("planned", "complete")
DEFAULT_ESSAY_STATUS = "complete"

# Author-assigned slug-like identity convention shared by essays.slug,
# essay_sections.anchor_slug, flashcards.card_key, and (Sprint09_Nuggets)
# nuggets.nugget_key. Promoted here (R-CON-BP-07 — one canonical definition)
# from what was previously a private copy in backend/routers/essays.py;
# flashcards.py's separate _CARD_ID_RE (same pattern, different name) is NOT
# part of this promotion.
SLUG_LIKE_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


class IngestionError(Exception):
    """Raised for any parse/validation failure before a database write is attempted."""


@dataclass
class IngestSummary:
    essay_created:       bool = False
    essay_id:            str = ""
    nuggets_created:     int = 0
    nuggets_updated:     int = 0
    sections_created:    int = 0
    sections_updated:    int = 0
    flashcards_created:  int = 0
    flashcards_updated:  int = 0


def ingest(path: str, conn: Any) -> "IngestSummary":
    """
    Read and parse the markdown file at `path`, validate it fully, then
    perform the transactional upsert against `conn` via upsert_document().

    Raises IngestionError on any validation failure — no DB write is attempted
    in that case. On a database error during the upsert phase, rolls back and
    re-raises.
    """
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    doc = _parse_document(text)  # raises IngestionError; no DB touched
    return upsert_document(conn, doc)


def upsert_document(conn: Any, doc: dict[str, Any]) -> "IngestSummary":
    """
    Shared upsert core — extracted from what was previously inline inside
    ingest(). Opens one transaction on `conn` and upserts the essay (keyed by
    slug, now including main_spine_markdown), each section (keyed by
    essay_id+anchor_slug), and each card (keyed by essay_id+card_key).
    Commits on success; rolls back and re-raises on any database error.

    Sprint09_Nuggets: before anything is written, every [[nugget:key]]
    reference across doc.get('main_spine_markdown', '') and every section's
    body_markdown is resolved against essaycards.nuggets in one query
    (_resolve_nugget_references) — an unresolved key raises IngestionError
    naming EVERY missing key at once, and nothing is written (the existing
    `except Exception: conn.rollback(); raise` wrapper is a harmless no-op
    rollback on this failure path too, since the raise happens before any
    write). Then, per section, once its id is known, essaycards.section_nuggets
    is resynced to that section's current references (_resync_section_nuggets)
    — this only ever removes an association row, never a nuggets row or a
    flashcards row.

    Full-package ingest: doc.get('nuggets', []) — each {nugget_key, title,
    body_markdown?} — is upserted FIRST, in the same transaction, before
    reference resolution, so a single payload can define a nugget and
    reference it via [[nugget:key]] in the same call. Reusing an existing
    nugget_key here updates that nugget's title/body_markdown in place
    (affecting every essay/section that already links to it) — same
    upsert-by-key semantics as POST /nuggets/upsert, not a separate code path.

    Called by ingest() (markdown/CLI path) and by POST /essays/ingest (JSON/API
    path, backend/routers/essays.py) — the single place all essaycards upsert
    SQL lives, which is what makes the nugget-reference validation above
    identical on both ingestion paths.
    """
    summary = IngestSummary()
    try:
        with conn.cursor() as cur:
            for nugget in doc.get("nuggets", []):
                nugget_inserted = _upsert_nugget(cur, nugget)
                if nugget_inserted:
                    summary.nuggets_created += 1
                else:
                    summary.nuggets_updated += 1

            referenced_keys: set[str] = set(extract_nugget_keys(doc.get("main_spine_markdown", "")))
            for section in doc["sections"]:
                referenced_keys |= extract_nugget_keys(section.get("body_markdown", ""))
            nugget_id_by_key = _resolve_nugget_references(cur, referenced_keys)

            essay_id, essay_inserted = _upsert_essay(
                cur, doc["title"], doc["slug"], doc.get("category"),
                doc.get("sort_index", 0), doc.get("status", DEFAULT_ESSAY_STATUS),
                doc.get("main_spine_markdown", ""),
            )
            summary.essay_created = essay_inserted
            summary.essay_id = str(essay_id)

            for section in doc["sections"]:
                section_id, section_inserted = _upsert_section(cur, essay_id, section)
                if section_inserted:
                    summary.sections_created += 1
                else:
                    summary.sections_updated += 1

                section_keys = extract_nugget_keys(section.get("body_markdown", ""))
                section_nugget_ids = [nugget_id_by_key[k] for k in section_keys]
                _resync_section_nuggets(cur, section_id, section_nugget_ids)

                for card in section["cards"]:
                    card_inserted = _upsert_flashcard(cur, essay_id, section_id, card)
                    if card_inserted:
                        summary.flashcards_created += 1
                    else:
                        summary.flashcards_updated += 1
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    return summary


# ── Nugget references (Sprint09_Nuggets) ─────────────────────────────────────

_FENCED_CODE_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
_NUGGET_REF_RE = re.compile(r"\[\[nugget:([a-zA-Z0-9_-]+)\]\]")


def extract_nugget_keys(markdown_text: str) -> set[str]:
    """
    Returns the set of nugget keys referenced via `[[nugget:key]]` in
    `markdown_text`. Fenced code blocks (```...```) and inline code spans
    (`...`) are stripped FIRST with a regex pass, so a reference written
    inside either is never captured — a pragmatic, regex-based mirror of the
    code-safety guarantee the frontend gets for free from operating on a
    parsed Markdown AST (see remarkNuggetRefs, src/ShellEntry.tsx). The
    capture character class matches SLUG_LIKE_RE exactly
    ([a-zA-Z0-9_-]+), so any valid nugget_key (mixed case included) is
    referenceable. Resolution against a captured key remains exact-match/
    case-sensitive — only the accepted character set is widened here, not
    the comparison semantics.
    """
    stripped = _FENCED_CODE_RE.sub("", markdown_text)
    stripped = _INLINE_CODE_RE.sub("", stripped)
    return set(_NUGGET_REF_RE.findall(stripped))


def _resolve_nugget_references(cur: Any, keys: set[str]) -> dict[str, str]:
    """
    Resolves `keys` against essaycards.nuggets in one query. Raises
    IngestionError naming EVERY unresolved key at once (not just the first)
    if any is missing — never auto-creates a placeholder nugget. Returns
    dict[nugget_key, nugget_id] for every key on success. Called once at the
    start of upsert_document, before any write.
    """
    if not keys:
        return {}

    cur.execute(
        "select id, nugget_key from essaycards.nuggets where nugget_key = any(%s)",
        (list(keys),),
    )
    nugget_id_by_key = {row["nugget_key"]: row["id"] for row in cur.fetchall()}

    missing = sorted(keys - nugget_id_by_key.keys())
    if missing:
        raise IngestionError(
            "Unresolved nugget reference(s): " + ", ".join(f"[[nugget:{k}]]" for k in missing)
        )

    return nugget_id_by_key


def _resync_section_nuggets(cur: Any, section_id: str, nugget_ids: list[str]) -> None:
    """
    Fully resyncs essaycards.section_nuggets for `section_id` to exactly
    `nugget_ids` — inserts missing associations, deletes stale ones. Never
    touches a nuggets row or a flashcards row. The `not (... = any(empty
    array))` form of the DELETE correctly clears every existing association
    when the section now references zero nuggets.
    """
    cur.execute(
        """
        insert into essaycards.section_nuggets (section_id, nugget_id)
        select %s, unnest(%s::uuid[])
        on conflict (section_id, nugget_id) do nothing
        """,
        (section_id, nugget_ids),
    )
    cur.execute(
        """
        delete from essaycards.section_nuggets
        where section_id = %s and not (nugget_id = any(%s::uuid[]))
        """,
        (section_id, nugget_ids),
    )


def _upsert_nugget(cur: Any, nugget: dict[str, Any]) -> bool:
    """
    Upsert-by-nugget_key, same SQL as POST /nuggets/upsert
    (backend/routers/nuggets.py) — kept as a separate literal statement rather
    than a shared function because the two call sites validate their input
    independently (this one already trusts a doc validated by
    _validate_ingest_body or the (currently nugget-less) markdown parser) and
    return different shapes. Returns True if inserted, False if updated.
    """
    cur.execute(
        """
        insert into essaycards.nuggets (nugget_key, title, body_markdown)
        values (%s, %s, %s)
        on conflict (nugget_key) do update
            set title         = excluded.title,
                body_markdown = excluded.body_markdown,
                updated_at    = now()
        returning (xmax = 0) as was_inserted
        """,
        (nugget["nugget_key"], nugget["title"], nugget.get("body_markdown", "")),
    )
    return cur.fetchone()["was_inserted"]


# ── Front matter ──────────────────────────────────────────────────────────────

_FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?\n)---\s*\n?", re.DOTALL)


def _parse_front_matter(text: str) -> tuple[str, str, str | None, int, str, str]:
    """Returns (title, slug, category, sort_index, status, remaining_text).

    category is None when the key is absent; sort_index defaults to 0; status
    defaults to DEFAULT_ESSAY_STATUS.
    """
    m = _FRONT_MATTER_RE.match(text)
    if not m:
        raise IngestionError(
            "Missing or unparsable YAML front matter — file must start with '---' "
            "and the front matter block must be closed with a second '---' line"
        )
    try:
        fm = yaml.safe_load(m.group(1))
    except yaml.YAMLError as exc:
        raise IngestionError(f"Front matter is not valid YAML: {exc}") from exc

    if not isinstance(fm, dict):
        raise IngestionError("Front matter must be a YAML mapping")

    title = fm.get("title")
    slug = fm.get("slug")
    if not isinstance(title, str) or not title.strip():
        raise IngestionError("Front matter missing required non-empty 'title'")
    if not isinstance(slug, str) or not slug.strip():
        raise IngestionError("Front matter missing required non-empty 'slug'")

    category = fm.get("category")
    if category is not None:
        if not isinstance(category, str) or not category.strip():
            raise IngestionError("Front matter 'category', if present, must be a non-empty string")
        category = category.strip()

    sort_index = fm.get("sort_index", 0)
    if isinstance(sort_index, bool) or not isinstance(sort_index, int):
        raise IngestionError("Front matter 'sort_index', if present, must be an integer")

    status = fm.get("status", DEFAULT_ESSAY_STATUS)
    if status not in VALID_ESSAY_STATUSES:
        raise IngestionError(
            f"Front matter 'status', if present, must be one of {list(VALID_ESSAY_STATUSES)}"
        )

    return title.strip(), slug.strip(), category, sort_index, status, text[m.end():]


# ── Section splitting ─────────────────────────────────────────────────────────

_HEADING_CANDIDATE_RE = re.compile(r"^##\s+")
_HEADING_RE = re.compile(r"^##\s+(.+?)\s*\{#([a-zA-Z0-9_-]+)\}\s*$")


def _split_sections(body: str) -> list[tuple[str, str, str]]:
    """Returns ordered (heading, anchor_slug, raw_content) tuples.

    Content before the first matched section heading is discarded. A '##'
    line that does not match the full anchor-suffix pattern aborts ingestion,
    citing the line number and heading text.
    """
    lines = body.splitlines()
    sections: list[tuple[str, str, list[str]]] = []
    current: tuple[str, str, list[str]] | None = None

    for lineno, line in enumerate(lines, start=1):
        if _HEADING_CANDIDATE_RE.match(line):
            m = _HEADING_RE.match(line)
            if not m:
                raise IngestionError(
                    f"Line {lineno}: '##' heading missing required {{#anchor}} suffix: {line!r}"
                )
            if current is not None:
                sections.append(current)
            current = (m.group(1), m.group(2), [])
        elif current is not None:
            current[2].append(line)
        # else: content before the first section heading — discarded

    if current is not None:
        sections.append(current)

    return [(heading, anchor, "\n".join(content_lines)) for heading, anchor, content_lines in sections]


# ── Flashcards fence extraction ───────────────────────────────────────────────

_FENCE_OPEN_RE = re.compile(r"^```flashcards\s*$")
_FENCE_CLOSE_RE = re.compile(r"^```\s*$")


def _split_body_and_cards(anchor_slug: str, content: str) -> tuple[str, str | None]:
    """Returns (body_markdown, cards_yaml_text | None).

    Zero fences -> (trimmed content, None). Exactly one fence -> content
    before it becomes body_markdown; content after the closing fence must be
    blank/whitespace-only, else ingestion aborts. More than one fence aborts.
    """
    lines = content.splitlines()
    open_indices = [i for i, line in enumerate(lines) if _FENCE_OPEN_RE.match(line)]

    if not open_indices:
        return content.strip(), None

    if len(open_indices) > 1:
        raise IngestionError(
            f"Section '{anchor_slug}': multiple ```flashcards fenced blocks found — only one is allowed per section"
        )

    open_idx = open_indices[0]
    close_idx = None
    for i in range(open_idx + 1, len(lines)):
        if _FENCE_CLOSE_RE.match(lines[i]):
            close_idx = i
            break
    if close_idx is None:
        raise IngestionError(f"Section '{anchor_slug}': ```flashcards block is not closed with a ``` line")

    trailing = lines[close_idx + 1:]
    if any(line.strip() for line in trailing):
        raise IngestionError(
            f"Section '{anchor_slug}': non-blank content found after the ```flashcards block"
        )

    body_markdown = "\n".join(lines[:open_idx]).strip()
    cards_yaml_text = "\n".join(lines[open_idx + 1:close_idx])
    return body_markdown, cards_yaml_text


# ── Cards YAML parsing ─────────────────────────────────────────────────────────

def _parse_cards_yaml(anchor_slug: str, cards_yaml_text: str) -> list[dict[str, str]]:
    try:
        parsed = yaml.safe_load(cards_yaml_text)
    except yaml.YAMLError as exc:
        raise IngestionError(f"Section '{anchor_slug}': flashcards block is not valid YAML: {exc}") from exc

    if not isinstance(parsed, dict) or "cards" not in parsed:
        raise IngestionError(f"Section '{anchor_slug}': flashcards block missing top-level 'cards' key")

    cards_raw = parsed["cards"]
    if not isinstance(cards_raw, list):
        raise IngestionError(f"Section '{anchor_slug}': 'cards' must be a list")

    cards: list[dict[str, str]] = []
    for position, entry in enumerate(cards_raw):
        if not isinstance(entry, dict):
            raise IngestionError(f"Section '{anchor_slug}': card at position {position} is not a mapping")

        card_id = entry.get("id")
        question = entry.get("q")
        answer = entry.get("a")

        if not isinstance(card_id, str) or not card_id.strip():
            raise IngestionError(f"Section '{anchor_slug}': card at position {position} missing required 'id'")
        if not isinstance(question, str) or not question.strip():
            raise IngestionError(f"Section '{anchor_slug}': card '{card_id}' missing required 'q'")
        if not isinstance(answer, str) or not answer.strip():
            raise IngestionError(f"Section '{anchor_slug}': card '{card_id}' missing required 'a'")

        cards.append({"card_key": card_id.strip(), "question": question, "answer": answer})

    return cards


# ── Cross-file uniqueness ──────────────────────────────────────────────────────

def _validate_uniqueness(sections: list[dict[str, Any]]) -> None:
    seen_anchors: set[str] = set()
    seen_card_keys: set[str] = set()

    for section in sections:
        anchor = section["anchor_slug"]
        if anchor in seen_anchors:
            raise IngestionError(f"Duplicate anchor_slug '{anchor}' appears more than once in the file")
        seen_anchors.add(anchor)

        for card in section["cards"]:
            key = card["card_key"]
            if key in seen_card_keys:
                raise IngestionError(f"Duplicate card id '{key}' appears more than once in the file")
            seen_card_keys.add(key)


# ── Top-level parse ─────────────────────────────────────────────────────────────

def _parse_document(text: str) -> dict[str, Any]:
    title, slug, category, sort_index, status, body = _parse_front_matter(text)
    raw_sections = _split_sections(body)

    sections: list[dict[str, Any]] = []
    for order_index, (heading, anchor_slug, raw_content) in enumerate(raw_sections):
        body_markdown, cards_yaml_text = _split_body_and_cards(anchor_slug, raw_content)
        cards = _parse_cards_yaml(anchor_slug, cards_yaml_text) if cards_yaml_text is not None else []
        sections.append({
            "heading":       heading,
            "anchor_slug":   anchor_slug,
            "order_index":   order_index,
            "body_markdown": body_markdown,
            "cards":         cards,
        })

    _validate_uniqueness(sections)

    return {
        "title": title,
        "slug": slug,
        "category": category,
        "sort_index": sort_index,
        "status": status,
        "sections": sections,
    }


# ── DB upserts ──────────────────────────────────────────────────────────────────

def _upsert_essay(
    cur: Any, title: str, slug: str, category: str | None, sort_index: int, status: str,
    main_spine_markdown: str = "",
) -> tuple[str, bool]:
    cur.execute(
        """
        insert into essaycards.essays (title, slug, category, sort_index, status, main_spine_markdown)
        values (%s, %s, %s, %s, %s, %s)
        on conflict (slug) do update
            set title               = excluded.title,
                category            = excluded.category,
                sort_index          = excluded.sort_index,
                status              = excluded.status,
                main_spine_markdown = excluded.main_spine_markdown,
                updated_at          = now()
        returning id, (xmax = 0) as was_inserted
        """,
        (title, slug, category, sort_index, status, main_spine_markdown),
    )
    row = cur.fetchone()
    return row["id"], row["was_inserted"]


def _upsert_section(cur: Any, essay_id: str, section: dict[str, Any]) -> tuple[str, bool]:
    cur.execute(
        """
        insert into essaycards.essay_sections
            (essay_id, anchor_slug, heading, order_index, body_markdown)
        values (%s, %s, %s, %s, %s)
        on conflict (essay_id, anchor_slug) do update
            set heading       = excluded.heading,
                order_index   = excluded.order_index,
                body_markdown = excluded.body_markdown,
                updated_at    = now()
        returning id, (xmax = 0) as was_inserted
        """,
        (essay_id, section["anchor_slug"], section["heading"], section["order_index"], section["body_markdown"]),
    )
    row = cur.fetchone()
    return row["id"], row["was_inserted"]


def _upsert_flashcard(cur: Any, essay_id: str, section_id: str, card: dict[str, str]) -> bool:
    cur.execute(
        """
        insert into essaycards.flashcards (essay_id, section_id, card_key, question, answer)
        values (%s, %s, %s, %s, %s)
        on conflict (essay_id, card_key) do update
            set question   = excluded.question,
                answer     = excluded.answer,
                section_id = excluded.section_id,
                updated_at = now()
        returning id, created_at, (xmax = 0) as was_inserted
        """,
        (essay_id, section_id, card["card_key"], card["question"], card["answer"]),
    )
    row = cur.fetchone()

    if row["was_inserted"]:
        scheduler, reason = decide_scheduler_assignment(str(row["id"]))
        cur.execute(
            """
            insert into essaycards.flashcard_review_state
                (flashcard_id, last_reviewed_at, next_due_at, review_interval,
                 scheduler, scheduler_assigned_at, scheduler_assignment_reason, experiment_version)
            values (%s, null, %s, interval '0', %s, now(), %s, %s)
            """,
            (row["id"], row["created_at"], scheduler, reason, EXPERIMENT_VERSION),
        )

    return row["was_inserted"]


# ── CLI wrapper ─────────────────────────────────────────────────────────────────

def _main() -> None:
    import sys

    if len(sys.argv) != 2:
        print("Usage: python -m backend.ingest <path>", file=sys.stderr)
        sys.exit(2)

    path = sys.argv[1]

    from backend.database import get_db, init_pool

    init_pool()
    try:
        with get_db() as conn:
            summary = ingest(path, conn)
    except IngestionError as exc:
        print(f"Ingestion failed: {exc}", file=sys.stderr)
        sys.exit(1)

    print(
        f"Ingested '{path}': essay {'created' if summary.essay_created else 'updated'}, "
        f"sections +{summary.sections_created}/~{summary.sections_updated}, "
        f"flashcards +{summary.flashcards_created}/~{summary.flashcards_updated}"
    )


if __name__ == "__main__":
    _main()
