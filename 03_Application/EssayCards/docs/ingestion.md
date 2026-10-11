# EssayCards — Content ingestion

Split out of `CLAUDE.md` (reference detail; load when working on this area).

## Content ingestion
Essays can be ingested two ways — both upsert by the same stable author-assigned keys
(slug / (essay_id, anchor_slug) / (essay_id, card_key)) and both call the single shared
`backend.ingest.upsert_document(conn, doc)` core, so re-ingestion via either path never
resets a flashcard's review state.

### Essay overview metadata (`category`, `sort_index`, `status`)
Both ingestion paths accept three optional essay-level fields — front-matter keys for the
markdown CLI, top-level JSON keys for the API:
- `category` — free text, no fixed set, no lookup table (an essay has at most one). It is
  the group the essay appears under on the overview page. The known groups (`Art`,
  `History`, `Philosophy`) and their display order live only in the frontend
  (`CATEGORY_ORDER` in `src/ShellEntry.tsx`); any other value renders in its own group
  after those, and `null` renders last under "Uncategorized". Adding a category is a
  content change, not a schema change.
- `sort_index` — integer, default `0`, the essay's position **within its category**,
  ascending (ties break on `created_at`). This is where a sequence number goes — it is
  never written into `title`. Distinct from `essay_sections.order_index`, which is
  auto-derived from payload array order; `sort_index` is set explicitly by the author.
- `status` — `planned` | `complete`, default `complete` (`ck_essays_status`). `planned`
  is a stub whose body text is a planning document; a normal ingest is `complete`, so a
  stub must set `status: planned` explicitly. `VALID_ESSAY_STATUSES` / `DEFAULT_ESSAY_STATUS`
  in `backend/ingest.py` are the single source for both ingest paths.

All three are `on conflict do update`d on re-ingest, so a later payload with the same slug
re-files, re-orders or re-statuses the essay. `GET /essays` orders rows
`(category asc nulls last, sort_index asc, created_at asc)` and carries all three fields
on every row; `EssayListView` groups on them. Blank `category`, non-integer `sort_index`
or a `status` outside the set is `VALIDATION_ERROR` (JSON path) / `IngestionError`
(markdown path).

**Markdown CLI** (offline authoring — YAML front matter, `## Heading {#anchor}` sections,
one fenced ```flashcards YAML block per section):

    docker exec atlas-essaycards python -m backend.ingest /app/content/<file>.md

**JSON API / in-app UI** (Sprint 2): `POST /api/essaycards/essays/ingest`, or the
"Add / Update Essay" nav entry in the app, which pastes the same JSON shape into a
textarea. See `Sprint02_JsonIngestion/00_draft.md` for the payload schema.

One deliberate asymmetry: a card `id` that already exists in the DB under a *different*
section is silently moved by the markdown CLI path (`ON CONFLICT ... DO UPDATE SET
section_id = excluded.section_id`), but rejected as `VALIDATION_ERROR` by the JSON
endpoint's pre-write validation layer. The shared upsert core's SQL is identical for
both paths — only the JSON endpoint's validation is stricter. See
`Sprint02_JsonIngestion/10_architecture.json` §risks.

Deleting a section or flashcard from the source (markdown file or JSON payload) does NOT
delete its row on re-ingestion via either path — this is an explicit Sprint 1 gap,
extended unchanged to the JSON path in Sprint 2 (see `Sprint01_Core/10_architecture.json`
§risks), not a bug.

To use an image in essay or card text, import it first (see `## Images` below), then
reference its slug as ordinary Markdown — `![](/api/essaycards/images/<slug>)` — inside
`body_markdown` / `q` / `a`. Neither ingestion path parses or validates image references;
a reference to a slug that was never imported just renders as a broken image.

The JSON-ingestion helper prompt (`STUB_PROMPT` in `src/ShellEntry.tsx`, shown in the
"Add / Update Essay" view) has an **Images rule** plus an **"Available images"** list the
author fills in by hand from the imported slugs. The generating model only emits
`![](...)` references for slugs on that list; if the list is left empty it emits none.
The endpoint still does no validation — the list is a prompt-side convention, not a
backend check.
