# Fast Path Plan — Sprint15_StatsOralsAndImproveSection

## Eligibility (R-PRO-BP-01 §11)
- No new table — met.
- files_changed <= 5: `backend/routers/review_stats.py`, `backend/routers/essays.py`, `src/ShellEntry.tsx`, `tests/test_review_stats.py`, `tests/test_essays.py` (5) — met.
- No new/changed shared contract surface: the summary Dataset is consumed only by this component's own frontend; three columns are additive — met.
- Single component, single layer — met.

## Query behavior (R-CON-AL-01)
**GET /review-stats/summary** — unchanged params (none), order (day, week, month), zero-fill (always 3 rows). Adds `orals_count`, `guided_orals_count`, `unguided_orals_count` per row: count of `section_examinations` UNION ALL `essay_examinations` rows with `examined_at >= now() - window` (24h / 7d / 30d, same rolling windows as the review aggregates), `exam_type` split guided/unguided; every attempt counted, passed or not. Time basis: stored `examined_at` (persisted domain time, R-CON-AL-06) vs server `now()`. Empty result: 0.

**GET /essays/{id}/sections/{sid}/export** — new optional bool `include_examinations`, default false (package byte-identical to before). When true, adds `focus_section_examinations`: every `exam_type='guided'` row of the focus section, ordered `examined_at` ascending, each `{examined_at, score, passed, question, answer_transcript, feedback}` verbatim; `[]` if none. Unguided never included. Read-only; POST /essays/ingest ignores it.

## Frontend
- `DailyActivityChart`: scroll container starts at far right (newest day); Unique segment uses `--md-sys-color-tertiary`.
- `ReviewStatsCard`: three new figures.
- Reader section menu: "Improve section" -> fetches export with `?include_examinations=true`, copies `SECTION_IMPROVE_PROMPT_INTRO` + package; then the item becomes "Import improved section →" (navigates to the ingest page). Same nugget-drop-detection sessionStorage stash as Export section. Round-trip: the reply is the ingest payload (edit-in-place by card id; omit examinations field); no PATCH semantics involved.

## Tests
`tests/test_review_stats.py` (oral counts per window vs DB ground truth; key-set pin updated), `tests/test_essays.py` (default has no key; guided-only oldest-first; empty list; reimport round trip ignores the field).
