# EssayCards — Nuggets

Split out of `CLAUDE.md` (reference detail; load when working on this area).

## Nuggets (Sprint09)
See `## Glossary` "Nuggets (Sprint09)" for the core vocabulary. This section is the
implementation contract.

**Schema.** `essaycards.nuggets` (`id`, `nugget_key` unique, `title`, `body_markdown`,
`created_at`/`updated_at`) and `essaycards.section_nuggets` (many-to-many,
`(section_id, nugget_id)` composite PK, both FKs `on delete cascade`) are new tables.
`flashcards.nugget_id` (nullable, `on delete set null`) and
`essays.main_spine_markdown` (`not null default ''`) are additive columns. All
additive/idempotent, per the existing `create table if not exists` /
`alter table ... add column if not exists` pattern.

**Reference resolution and resync.** `backend/ingest.py::extract_nugget_keys` strips
fenced code blocks and inline code spans, then matches `\[\[nugget:([a-zA-Z0-9_-]+)\]\]`
— the character class matches `SLUG_LIKE_RE` exactly, so any valid `nugget_key` (mixed
case included) is referenceable. `upsert_document`'s first step (before any write)
resolves the union of every referenced key across `main_spine_markdown` and every
section's `body_markdown` against `essaycards.nuggets`, raising `IngestionError` naming
every unresolved key at once if any is missing — identical on both the markdown CLI and
`POST /essays/ingest` JSON paths, because both share this one core. No placeholder
nugget is ever auto-created. Once a section's id is known, `section_nuggets` is fully
resynced to that section's current references (insert missing, delete stale) — the one
explicit exception to the app's general no-delete-on-re-ingest policy; it only ever
removes an association row, never a `nuggets` or `flashcards` row.

**`SLUG_LIKE_RE`** (`^[a-zA-Z0-9_-]+$`) lives in `backend/ingest.py`, promoted from what
was previously a private copy in `essays.py` — the one canonical definition
(`essays.py`, `nuggets.py` both import it; `flashcards.py`'s separate `_CARD_ID_RE`,
same pattern, is untouched).

**`essays.main_spine_markdown`** is settable via `POST /essays/ingest` only (optional
top-level key, default `''` on omission, same convention as `category`/`sort_index`/
`status`). The markdown-CLI front-matter grammar is unchanged — an essay ingested via
the CLI keeps `main_spine_markdown = ''` until edited through the JSON path.

**API** (`backend/routers/nuggets.py`, mounted at `/api/essaycards/nuggets`):
`GET ''` (list, no `body_markdown`), `GET '/{id}'` (detail), `POST '/upsert'`
(upsert-by-`nugget_key`), `GET '/{id}/flashcards'` (flat, no scheduling fields —
reviewing a nugget-linked card for real spaced repetition still goes through the
existing essay/section-scoped focus session; no nugget-scoped `/due` or `/stats` this
sprint), `GET '/{id}/sections'` ("referenced by"), `GET '/authoring-package'` and
`GET '/{id}/generate-flashcards-package'` (bespoke JSON, Dataset-exempt — ChatGPT round
trips, see below). Existing endpoints extended: essay detail/export/section-export gain
`main_spine_markdown`/`main_spine_nuggets`/per-section `nuggets`; question-overview rows
gain `section_nuggets`/`nugget_id`; `POST /flashcards/upsert` gains `nugget_id`
(omit/null/value tri-state, R-CON-AL-04); `GET /flashcards/due` and single-question
export gain `nugget_id`.

**Frontend rendering.** `remarkNuggetRefs` (a remark plugin, `src/ShellEntry.tsx`)
visits mdast `text` nodes and turns a resolved `[[nugget:key]]` into an in-app link
(`NuggetLink`, `href="nugget:<key>"`) or a non-clickable broken-link span for an
unresolved one (`href="nugget-missing:<key>"`) — fenced/inline code is already a
separate node type by the time remark hands off, so no hand-written stripping is
needed on the frontend (unlike the backend's regex-based `extract_nugget_keys`).
Clicking a resolved link opens `NuggetPanel`, an in-page overlay with its own
click-through id-stack — never a route navigation, so `ReaderView`/`ReviewSessionView`
never unmount and reading position / review-session state survive opening and closing
it. `ReviewSessionView`'s revealed-answer area shows "Flashcard → Nugget" (opens the
same overlay) when the current card's `nugget_id` is set, else the unchanged "Jump to
passage" route navigation.

**ChatGPT round trips**, same export → copy → discuss → paste → apply pattern as every
other round trip in this app: nugget authoring (`GET /nuggets/authoring-package` →
`POST /nuggets/upsert`, reachable via "+ New nugget" in `ReaderView` / "Edit nugget" in
`NuggetPanel`) and flashcard generation from a nugget (`GET
/nuggets/{id}/generate-flashcards-package` → one `POST /flashcards/upsert` per
AI-returned card, sequential, each pre-set with `nugget_id` — not atomic across the
batch, see Known gap below). The section spine-revision package
(`GET .../sections/{id}/export`) additionally carries `main_spine_markdown`,
`main_spine_nuggets`, and `focus_section_nuggets` (full body, focus section only); on
reimport, `IngestView` compares the returned focus section's current nugget keys
against a set stashed in `sessionStorage` at export time and shows a non-blocking
warning banner naming any accidentally-dropped reference (submission is never blocked).

**Known gap — ownership/cascade (documented, not guarded).** A flashcard reachable
through a shared nugget from another essay is still only *owned* by its own
`essay_id`/`section_id` (`flashcards.nugget_id` does not change this — see schema.sql's
comment on the column). Deleting the owning section or essay would remove the card even
though another essay still references it via the nugget. The app has no delete endpoint
anywhere today (essays/sections/flashcards/images are all upsert-only), so this risk has
no live trigger through the app; it is latent, not exercised. No app-level guard is
added — an explicit decision, same pattern as the Sprint02 card/section-move asymmetry.

**Known gap — non-atomic flashcard generation.** "Generate flashcards from a nugget"
issues one `POST /flashcards/upsert` per AI-generated card, not a single atomic batch —
if card *N* of *M* fails, cards `1..N-1` are already saved while `N..M` are not. The
import view reports per-card success/failure so a failed card can be retried
individually.
