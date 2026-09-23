# Sprint09 — Nugget-based learning architecture

## Scope

Introduce reusable, independently-learnable **Nuggets** as a new layer between
essay sections and flashcards, restructure essays around a compact **main
spine**, and establish explicit navigation between essays, sections, nuggets
and flashcards. Additive only: no existing table is recreated, no flashcard
identity, review state, discussion/revision history or examination history is
reset or deleted. Legacy essays/sections/flashcards remain fully usable
without conversion.

## 0. Product intent (compressed)

Four levels, each with a distinct job:

```
Essay (main spine)  — the intellectual journey, compact enough to memorize
  Section (sub-spine) — short narrative connecting its required nuggets,
                         does not repeat their explanations
    Nugget             — a small, independently learnable concept; owns the
                          actual explanation; reusable across sections/essays
      Flashcard         — tests recall of one nugget's knowledge
```

A nugget is a standalone object, not owned by one essay or section. The same
nugget can be referenced by multiple sections/essays without duplicating its
content, its flashcards, or their review state. Reading flow: essay → main
spine → section → click a referenced concept → nugget → optionally its
flashcards → back to the section at the same reading position → next
concept. All existing features (spaced repetition, oral exams, flashcard
exploration, discussion/revision history, images, both ingestion paths) must
keep working unchanged for content that hasn't adopted nuggets.

## 1. Database changes

All additive via the existing `alter table ... add column if not exists` /
guarded-constraint pattern already used for `essays.category/sort_index/status`,
`flashcards.level`, and `flashcard_review_state.review_interval`.

- **`essaycards.nuggets`** — `id uuid PK default gen_random_uuid()`,
  `nugget_key text not null unique` (globally unique, no scoping — nuggets
  aren't owned by one essay), `title text not null`, `body_markdown text not
  null default ''`, `created_at`/`updated_at timestamptz`. Suitable index on
  `nugget_key` (unique constraint already provides one) and `created_at` for
  a list view.
  - `nugget_key` is author-assigned, same convention as essay `slug` /
    section `anchor_slug` / card `card_key`: validated against the existing
    `_SLUG_LIKE_RE = ^[a-zA-Z0-9_-]+$` pattern, no auto-slugify, no
    auto-lowercasing. Promote that regex out of `essays.py` (currently a
    private copy there) into `ingest.py`, alongside the other cross-router
    shared constants (`VALID_ESSAY_STATUSES`/`DEFAULT_ESSAY_STATUS`), so
    `nuggets.py` imports the one canonical definition (R-CON-BP-07) rather
    than duplicating it.
  - Nugget create/update is **upsert-by-key**:
    `on conflict (nugget_key) do update set title = excluded.title,
    body_markdown = excluded.body_markdown, updated_at = now()`. This is what
    guarantees a title edit can never change the key (the key is the `WHERE`,
    the title is just a `SET` column) — mirrors the existing app-wide
    precedent that `slug`/`anchor_slug`/`card_key` have no in-place rename
    path either. No key-rename support this sprint.

- **`essaycards.section_nuggets`** — many-to-many, `(section_id, nugget_id)`
  composite PK (or unique constraint), FKs to `essay_sections.id` and
  `nuggets.id`, both `on delete cascade`. **Derived, not author-maintained**:
  a section's Markdown references are the sole source of truth. Rows are
  fully resynced (insert missing, delete stale) on every section
  upsert — see §2. This resync is an explicit, documented exception to the
  app's general no-delete-on-re-ingest policy: it only ever removes
  association rows, never a `nuggets` row or a `flashcards` row.

- **`flashcards.nugget_id`** — `uuid null references essaycards.nuggets(id)`.
  Nullable; existing flashcards remain valid with no nugget. No automatic
  assignment based on title/question/section matching — assignment is
  explicit only (§4/§5). `essay_id`/`section_id` remain required and
  unchanged this sprint (see ownership note below).

- **`essays.main_spine_markdown`** — `text not null default ''`. The
  existing `essay_sections.body_markdown` becomes the location for the
  written-out sub-spine; unchanged in shape, just newly expected to reference
  nuggets via the syntax in §2.

- **Documented ownership limitation (no code guard)**: a flashcard reachable
  through a shared nugget from another essay is still only owned by its
  original `essay_id`/`section_id`. A cascading delete of that section (or
  essay) would remove the card even though other essays still reference it
  via the nugget. The app currently has **no delete endpoint anywhere**
  (confirmed — essays/sections/flashcards/images are all upsert-only), so
  this risk has no live trigger through the app today; it is latent, not
  exercised. Document it in three places, no guard code:
  1. Inline comment on `flashcards.nugget_id` in `schema.sql` (same style as
     the existing `images`/`section_examinations` comments).
  2. A "Known gap" bullet in `CLAUDE.md`, same style as the existing
     no-paragraph-linkage / images-not-backed-up notes.
  3. `10_architecture.json §risks` once this sprint reaches design, matching
     how the Sprint02 card/section-move asymmetry is already tracked there.

## 2. Nugget-reference syntax and validation

Syntax: `[[nugget:key]]` inside `essays.main_spine_markdown` and
`essay_sections.body_markdown`. Resolved through the stable `nugget_key`;
rendered title always comes from the live `nuggets.title` — never duplicated
as a separate copy in the referencing Markdown.

- New shared helper `extract_nugget_keys(markdown_text: str) -> set[str]` in
  `ingest.py`: strips fenced code blocks (`` ``` ``) and inline code spans
  (`` ` ``) first with a regex pass, then matches `\[\[nugget:([a-z0-9_-]+)\]\]`
  on what remains. This is a pragmatic mirror, on the Python side, of the
  code-safety guarantee the frontend gets for free from operating on the
  parsed Markdown AST (§3) — consistent with how this module already treats
  Markdown informally (the flashcards-fence extraction is regex-based too,
  not a real CommonMark parser).
- **`upsert_document(conn, doc)`** (the one shared core used by both the
  markdown CLI and the JSON API) gets a new first step, before `_upsert_essay`
  is called: collect the union of `extract_nugget_keys()` over
  `doc.get("main_spine_markdown", "")` and every section's `body_markdown`;
  one query against `essaycards.nuggets`; if any required key doesn't
  resolve, `raise IngestionError(...)` naming **every** missing key at once
  (not just the first — same all-at-once convention as
  `_validate_uniqueness`/`_check_card_section_collisions`). Nothing is
  written yet, so the existing `except Exception: conn.rollback(); raise`
  wrapper is a harmless no-op rollback.
  - This makes nugget-reference validation **identical on both ingestion
    paths** — unlike the pre-existing card/section-collision check, which
    stays exactly as asymmetric as it is today (JSON pre-checks, markdown CLI
    doesn't). Only this new feature is unified; nothing about the existing
    asymmetry changes.
- Later in the same function's per-section loop, once `_upsert_section`
  returns the section's id: resync `section_nuggets` from that section's
  already-extracted key set — `insert ... on conflict (section_id, nugget_id)
  do nothing`, then `delete ... where section_id = %s and nugget_id not in
  (...)` for references removed since the last save.
- Callers: `ingest.py`'s CLI `_main()` already has `except IngestionError`
  handling — no change needed. `essays.py::ingest_essay` wraps its existing
  `upsert_document(conn, doc)` call in `try/except IngestionError as exc:
  return api_error("VALIDATION_ERROR", str(exc))`.
- Never auto-create a placeholder nugget for an unresolved reference — an
  unresolved key is always a validation error, full stop.

## 3. Frontend Markdown rendering

Current rendering is bare `<ReactMarkdown>{body}</ReactMarkdown>`
(`src/ShellEntry.tsx`), no plugins. `unist-util-visit@5.1.0` is already
present transitively (via `react-markdown`'s own remark dependency chain in
`Atlas_Shell/node_modules`) — add it as an explicit direct dependency in
`Atlas_Shell/package.json` rather than relying on the undeclared transitive
resolution.

- New remark plugin `remarkNuggetRefs(titleMap: Record<string,string>)`:
  `visit(tree, 'text', ...)` — visits only mdast `text` nodes. By the time
  remark hands off, fenced code blocks and inline code spans are already
  separate `code`/`inlineCode` node types, so a `[[nugget:...]]` written
  inside either is structurally invisible to a `text`-node visitor — no
  hand-written fence/span detection needed.
- Each match in a `text` node is replaced with a `link` mdast node:
  resolved key → `url: "nugget:<key>"`, child text = `titleMap[key]`;
  unresolved key → `url: "nugget-missing:<key>"`, child text = the raw key
  (never silently rendered as if it were a valid concept name).
- `<ReactMarkdown remarkPlugins={[remarkNuggetRefs(titleMap)]}
  components={{ a: NuggetLink }}>`. `NuggetLink` branches on the `href`
  scheme: `nugget:` → in-app navigation (not a real `<a>` — a full page nav
  would break reading-position preservation, §7); `nugget-missing:` →
  non-clickable, styled as broken; anything else → ordinary `<a>` (unchanged
  behavior for normal links/images).
- `titleMap` is built from whatever the section-detail response already
  returns for that section's referenced nuggets (§4) — computed once per
  section render, not fetched per link.

## 4. Backend API

New `backend/routers/nuggets.py`:

- `GET /nuggets` — Dataset (R-CON-BP-04): `id`, `nugget_key`, `title`,
  `created_at`, `updated_at`. No `body_markdown` in the list row.
- `GET /nuggets/{id}` — full detail including `body_markdown`.
- `POST /nuggets/upsert` — `{nugget_key, title, body_markdown}`, upsert-by-key
  per §1. Raw-Request JSON validation, `VALIDATION_ERROR` on any malformed
  shape — same precedent as `POST /flashcards/upsert` and `POST /essays/ingest`.
- `GET /nuggets/{id}/flashcards` — flat list (`id`, `card_key`, `question`,
  `answer`, `level`, `essay_id`, `section_id`) of cards currently pointing at
  this nugget. Read-only, no scheduling fields — see §6 for why this is
  deliberately not a due-queue-shaped endpoint.
- `GET /nuggets/{id}/sections` — sections (with essay context:
  `essay_id`/`essay_title`/`essay_slug`) currently referencing this nugget
  via `section_nuggets`, for the nugget view's "referenced by" list.

Existing routers:

- `essays.py` — `main_spine_markdown` added to essay detail, `GET
  /essays/{id}/export`, and `POST /essays/ingest`'s payload shape; ingest
  treats it exactly like `category`/`sort_index`/`status` already are
  (optional top-level key, defaults to `''` on omission — the existing
  whole-document-upsert convention, distinct from the field-omit-vs-null
  PATCH semantics below, which only apply to narrow single-record mutation
  endpoints).
- Section-bearing reads (essay detail, `GET .../questions`, both export
  endpoints) gain each section's referenced nuggets as `{nugget_key, title}`
  pairs — enough for the frontend's `titleMap` (§3) without pulling every
  nugget's full `body_markdown` into lightweight essay-list responses.
- `POST /flashcards/upsert` gains optional `nugget_id`. Per R-CON-AL-04:
  **field omitted** → existing assignment untouched (a legacy importer that
  never sends this field must never reset an existing assignment); **field
  present as `null`** → clears the assignment; **field present with a
  value** → resolves and sets it (`VALIDATION_ERROR` if the id doesn't
  resolve to an existing nugget).
- `GET /flashcards/{id}/export` and `GET /flashcards/due` rows gain
  `nugget_id` (additive field, R-CON-BP-04-compatible) alongside existing
  fields, for the frontend's source-navigation logic (§6).

## 5. Ingestion / migration safety

Both paths continue sharing `upsert_document`; nugget-reference validation
is unified per §2. No automatic reassignment of existing flashcards to
nuggets by matching title/question/section — assignment is explicit only,
via `POST /flashcards/upsert`'s `nugget_id` field (manual, one card at a
time, this sprint). No placeholder nuggets are ever auto-created.

## 6. Review / practice flow

No new `nugget_id` scope on `GET /flashcards/due` or `GET /flashcards/stats`.
With a typical 2–3 cards per nugget, a full due-queue session
(new/learning/established bucketing, RECENT/BACKLOG ordering) is
disproportionate. `GET /nuggets/{id}/flashcards` (§4) is a flat display list;
practicing a nugget-linked card for real spaced repetition still goes through
the existing essay/section-scoped focus session the card already belongs to
— identical to how a legacy card works today. `/due` and `/stats` are
untouched by this sprint.

Flashcard source navigation: `nugget_id` set → `Flashcard → Nugget` (with a
further link to `GET /nuggets/{id}/sections` for "referenced by"); `nugget_id`
null → `Flashcard → Section` (unchanged legacy behavior). Opening/closing
source material from an active review session must not interrupt or reset
it — implement as an overlay/panel, not a route change that unmounts
`ReviewSessionView`.

## 7. Reading-position preservation

Inspect the existing routing approach in `ShellEntry.tsx`/`shellConfig.ts`
during design/implementation before choosing the mechanism (route state vs.
a detail panel/drawer vs. browser history) — not decided in this draft.
Required behavior regardless of mechanism: opening a nugget from a section
and returning lands the reader at the same scroll position/paragraph, with
no full page reload (this is also why nugget links render as in-app
navigation rather than real `<a>` tags — see §3).

## 8. ChatGPT round-trip extensions

Same export → copy → discuss → paste → validate/dry-run → apply pattern as
every existing round trip in this app.

- **Nugget authoring package** (new export/import pair) — context: current
  essay title + main spine, current section + its spine, the target nugget
  (existing body if editing, a blank placeholder if creating, same
  placeholder-value-as-instructions convention as `STUB_PROMPT`), and its
  prerequisite/connected nuggets (resolved via `extract_nugget_keys()` on the
  target nugget's own `body_markdown`, §2). Applies via `POST /nuggets/upsert`.
  Prompt explicitly instructs: the nugget must stay independently
  understandable and must not reproduce the whole essay.
- **Section spine revision package** — extends the existing single-section
  export/import (`GET .../sections/{id}/export`, same whole-array round trip
  and "why the full array, not just one section" rationale already
  documented for `order_index` preservation) to also carry the main spine and
  each required nugget's `{nugget_key, title, body_markdown}` as read-only
  context. Import preview surfaces (not silently blocks) any case where a
  previously-required nugget reference has been dropped from the returned
  section, so an intentional editorial removal is distinguishable from an
  accidental one.
- **Flashcard generation from a nugget** — new export shape:
  `{nugget: {nugget_key, title, body_markdown}, existing_flashcards: [...]}`.
  Imported cards get `nugget_id` pre-set to the source nugget; same
  card-level conventions as the existing question-import flow (level
  required on every card, stable `card_key`, fresh `flashcard_review_state`
  row per new card).
- **Flashcard exploration package** — when a card's `nugget_id` is set, its
  exploration context becomes the nugget's `body_markdown` instead of the
  whole containing section. Legacy cards (`nugget_id` null) keep the current
  section-body context, unchanged.
- **Oral examinations** — content stays section-spine-based (testing the
  narrative connecting nuggets, not a re-list of flashcard questions);
  freshness detection extended per §9. No other shape change.

## 9. Examination freshness (nugget-aware)

- Additive `section_examinations.nugget_versions_at jsonb null` — `null`
  means "predates this feature" (existing rows stay fully readable, per the
  no-discard requirement); `{}` means "this section referenced zero nuggets
  at exam time."
- `build_export_package` adds a `nugget_versions` object per section —
  `{nugget_key: current nuggets.updated_at}` for that section's currently
  referenced nuggets — mirroring the existing `section_version` field
  (current `essay_sections.updated_at`, already echoed into the package).
- `validate_import_body`/`import_results` accept and store this value back
  verbatim into the new column — same echo-through-import behavior as
  `section_version_at`'s existing handling, not recomputed at import time.
- Freshness comparison (wherever ultimately surfaced): a currently-referenced
  nugget whose live `updated_at` doesn't match the value recorded on the
  latest exam row, or one missing from that recorded map entirely, flags
  "nugget changed since last exam," additive to whatever the existing
  section-level check already does. A `null` `nugget_versions_at` skips the
  nugget-level check gracefully. Accepts the same known
  false-positive-on-byte-identical-re-save limitation the section-level
  mechanism already has — not solved here, just not made worse.

## 10. Initial content / end-to-end test case

Essay **Rationalism**, main spine `Cogito → Adequacy → Innateness → Limits`,
sections `Descartes — Cogito` / `Spinoza — Adequacy` / `Leibniz — Innateness`
/ `Kant — Limits`. Only Descartes needs full demonstration this sprint.
Required nuggets: Methodical Doubt, Cogito, Wax and the Intellect, God and
Certainty, The External World, Mind and Body — all six referenced explicitly
in the Descartes sub-spine. Demonstrate: open Rationalism → see main spine →
open Descartes → read narrative → click "Wax and the Intellect" → read
nugget → view its flashcards → return to the section at the same location →
continue. Also demonstrate the same nugget referenced by a second section
without duplicating its content, flashcards, or review state. Use test
fixtures or clearly non-destructive demonstration data — do not overwrite the
real `why-libraries-of-alexandria-burned` content or any existing production
data to stage this.

## 11. Non-goals (explicit)

Knowledge-graph UI or automatic semantic link discovery; AI-generated
relationships; a new spaced-repetition algorithm; a full essay-editor
rewrite; a generic content-management platform; a prerequisite
recommendation engine; a standalone nugget scheduling system; an Atlas Shell
refactor; automatic conversion of every historical essay; automatic
reassignment of historical flashcards by guessed semantic match; a
nugget-scoped `/due`/`/stats` endpoint (§6); an app-level guard against the
ownership/cascade risk in §1 (documented only, per explicit decision);
nugget-key rename support (§1).

## Note

Original product spec supplied by the user in chat, framed as a sprint from
the start. Seven open technical questions it raised — Markdown-rendering
mechanism, main-spine authoring on the CLI path, ingestion-path unification
for nugget references, the nugget-key convention, handling of the
ownership/cascade risk, review-session scope, and the examination-freshness
mechanism — were resolved in conversation before this draft was written; the
resolutions are folded into §§1–9 above rather than left as open questions.
Intended to go through the full `R-PRO-BP-01` pipeline
(`sprint_design_application` → `sprint_design_reviewer` → `sprint_implement`
→ `sprint_test_runner`) rather than direct implementation, unlike the
Sprint05/Sprint08 precedent.
