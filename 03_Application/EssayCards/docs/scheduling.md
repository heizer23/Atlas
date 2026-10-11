# EssayCards — Scheduling and queues

Split out of `CLAUDE.md` (reference detail; load when working on this area).

## Due-queue ordering
`GET /api/essaycards/flashcards/due` — base eligibility is `next_due_at <= now()`, AND
(Sprint14) the card's section is unlocked AND the card is not `needs_revalidation` (flagged
cards are served only by `GET /flashcards/revalidation`). The ORDER BY below is unchanged.
**Sprint07** splits the endpoint into two session types, inferred from whether a
scope param is present (there is no `mode` param — see `## Roadmap, focus and
review`):

- **review** (no scope) additionally requires `review_interval >= interval '24
  hours'` — only `established` cards that are also due.
- **focus** (`?topic=` | `?essay_id=` | `?essay_id=&section_id=`) applies no
  interval filter — every open card in scope (new, learning, established).

Within either session, eligible cards are returned in two categories, **RECENT
entirely before BACKLOG** (Sprint05):

- **RECENT** — `last_reviewed_at >= now() - interval '24 hours'` (a rolling
  window off Postgres `now()`, *not* a calendar day / "reviewed today"; a
  never-reviewed card is never RECENT). Sorted by `next_due_at` **DESC** —
  closest-to-now first — so a card the user just pushed a few minutes out
  re-enters near the front once that delay elapses. Serves relearning.
- **BACKLOG** — everything else eligible. Sorted by `flashcard_review_state.review_interval`
  (`== next_due_at - last_reviewed_at`), **DESC** (longest first). Overdue
  duration is deliberately ignored. A never-reviewed card has `review_interval`
  `'0'` (seeded by `ingest.py`) and sorts behind every reviewed backlog card —
  no separate new-card queue.
- Tie-breakers: `next_due_at ASC`, then `f.id ASC`.

`last_reviewed_at` / `next_due_at` / `review_interval` (on `flashcard_review_state`,
all written by `POST .../review` from a single `select now()`) are the source of
truth — EssayCards has no per-review history table. All ordering logic is one SQL
`ORDER BY` in `list_due_flashcards`; the review UI renders `rows` in server order.

Each `/due` row also carries three additive fields (R-CON-BP-04; none affects
eligibility or ordering): `is_new` (bool) = `last_reviewed_at IS NULL`;
`is_recent` (bool) = `last_reviewed_at >= now() - interval '24 hours'` (the
RECENT-vs-BACKLOG category flag, false when `is_new`); and
`scheduled_interval_seconds` (int) = epoch seconds of `review_interval`, the
interval the card is currently scheduled across (the BACKLOG sort key; `0` when
`is_new`). All three feed the review screen.

## Roadmap, focus and review
Sprint07. Terms are defined in `## Glossary`; this section is the implementation
contract.

### `review_interval` (materialised interval)
`flashcard_review_state.review_interval` (`interval`, `NOT NULL DEFAULT '0'`,
`ck_review_state_interval >= 0`) is a **write-time cache** of
`next_due_at - last_reviewed_at`. The timestamp difference stays the definition
of record. Single writer: `POST /flashcards/{id}/review` sets it in the same
`UPDATE` as `next_due_at`, to `next_due_at - now` (`now` also being
`last_reviewed_at`), so the cache always equals the difference. `ingest.py`
seeds `'0'`. Any future code path that reschedules a card without going through
`backend.scheduling.FSRSScheduler` (the sole scheduler since Sprint12 — see
`## FSRS scheduling (Sprint12)`) must recompute it. Card classification:
`new` = `last_reviewed_at IS NULL` (interval `'0'`); `learning` =
`review_interval < interval '24 hours'` and not new; `established` =
`review_interval >= interval '24 hours'`.

### focus vs review (`GET /flashcards/due`)
No `mode` param — the session type is inferred from scope presence:
`{}` → review (`+ review_interval >= '24 hours'`); `{topic}` / `{essay_id}` /
`{essay_id, section_id}` → focus (no interval filter). Rejected with
`VALIDATION_ERROR`: `section_id` without `essay_id`; `topic` together with
`essay_id` or `section_id`. `topic` filters on `essays.category`. The reader's
end-of-section jump is already scoped, so it is a focus session with no code
change. `GET /flashcards/stats` is unchanged.

### `GET /essays` roadmap indicators
Every row carries, beyond `id/title/slug/category/sort_index/status`, three
category-level indicators (against Postgres `now()` at query time; `list_essays`
docstring is authoritative):
- `progress_total` (int) — every flashcard in the essay (not gated on a
  review-state row existing; locked cards included).
- `progress_established` (int) — those with `review_interval >= interval '24 hours'`
  (a `LEFT JOIN`, so a card with no review-state row counts in total, not here).
- `open_count` (int) — those with `next_due_at <= now()` AND in an unlocked section
  AND not `needs_revalidation` (Sprint14: exactly what a focus session would surface;
  not gated on established).

plus the Sprint14 derived essay traffic light (`essay_state`, `essay_next_step`,
`essay_guided_passed`, `essay_unguided_passed`, the two latest scores and passed dates,
`cards_learned_count`, `sections_total`, `sections_unguided_passed_count`,
`revalidation_pending_count`) — see `## Section progression (Sprint14)`. The nine
Sprint12 learning-progress fields and `learning_level` are removed.

Topic-level progress / open count are **not** returned — the frontend sums the
per-essay counts of a topic's rows. `GET /essays/{id}` (detail) carries the same
essay-progress fields as the list endpoint, computed by the identical shared SQL
(`backend/progress.py::essay_progress_lateral_sql`).

## Queue stats
`GET /api/essaycards/flashcards/stats` — review-queue forecast. Returns a Dataset of
exactly **seven** zero-filled rows partitioning every flashcard that has a review-state
row into non-overlapping horizon bands by `next_due_at` vs Postgres `now()`: `due_now`,
`within_10_min`, `within_1_day`, `within_7_days`, `within_30_days`, `within_90_days`,
`beyond_90_days` (bands open on the lower edge, closed on the upper; the seven counts
sum to the total UNLOCKED scheduled cards in scope — Sprint14 excludes locked cards;
cards flagged `needs_revalidation` stay counted in their FSRS due-date bands, so `due_now`
can exceed the focus queue and `open_count` by the number of flagged due cards). The 30-/90-day split feeds the review
screen's UPCOMING `≤3 mo` / `>3 mo` forecast columns. Same `topic` / `essay_id` /
`section_id` scoping rules as `GET /flashcards/due` (`section_id` without `essay_id`,
or `topic` with `essay_id`/`section_id` → `VALIDATION_ERROR`) — but **no** interval
filter: it always counts every unlocked scheduled card in scope, so the forecast
approximates the focus session it accompanies (`ReviewStatsPanel` passes the session's
scope through). Review-stats endpoints (`/review-stats/*`) are unchanged: they read
`review_events`, which a 'preserved' revalidation check never writes.


## FSRS scheduling (Sprint12)
FSRS (`fsrs` PyPI package, FSRS-6) is the SOLE scheduler. Sprint10's
dual-scheduler A/B experiment (Classic vs FSRS, persistent 50/50 assignment,
the scheduler badge, the experiment dashboard) is retired in full: its
schema columns dropped, its router/UI deleted. The due-queue selection/
ordering mechanism (`## Due-queue ordering`, `## Queue stats`, Focus/Review
eligibility, the 24-hour learning/established threshold) remains completely
untouched by this — only the mechanism that computes `next_due_at` changed.

**`backend/scheduling.py`.** `VALID_GRADES` is unchanged. `ClassicScheduler`,
`compute_next_due_at`, and `decide_scheduler_assignment` are REMOVED (verified
safe to remove only after the migration and FSRS review dispatch were
confirmed correct by the test suite). `FSRSScheduler` is unchanged from
Sprint10: loads or creates an `fsrs.Card`, drives a module-level
`fsrs.Scheduler(desired_retention=DESIRED_RETENTION)`, library-default
parameters/learning_steps/relearning_steps. `DESIRED_RETENTION` (new) — a
module constant, `float(os.environ.get('ESSAYCARDS_FSRS_DESIRED_RETENTION',
'0.9'))`, read once at import time; no UI exposure this sprint (env-var-only
server setting). FSRS's own memory state (stability, difficulty, its internal
Learning/Review/Relearning state, step) remains a SEPARATE, additional
persisted concept (`essaycards.fsrs_card_state`) — never confused with or
substituted for `review_interval`. Rating mapping unchanged: direct 1:1 name
match (`again`/`hard`/`good`/`easy` -> `fsrs.Rating.Again`/`Hard`/`Good`/`Easy`);
every datetime handed to the library is normalized to exactly
`.astimezone(timezone.utc)` first.

**Review transaction.** `POST /flashcards/{id}/review` now ALWAYS dispatches
to `FSRSScheduler` — no scheduler column to read, no branch. Inside the same
transaction as the `flashcard_review_state` `UPDATE`, it always upserts
`essaycards.fsrs_card_state` and always inserts one `essaycards.review_events`
row (append-only; the `scheduler` column on this table is also dropped). New
card creation (`backend/ingest.py`, `backend/routers/flashcards.py::
_upsert_question`, `backend/exploration.py::execute_plan`'s `create_card`
branch) seeds a bare `flashcard_review_state` row with no scheduler metadata
at all.

**Legacy FSRS-state migration (documented approximation — R-OPS-BP-01).**
`backend/migrate_fsrs_state.py::migrate_legacy_fsrs_state`, invoked once at
every startup immediately after `init_schema()`: for every
`flashcard_review_state` row with `last_reviewed_at IS NOT NULL` and no
existing `fsrs_card_state` row, synthesizes initial FSRS state via
`backend.scheduling.estimate_initial_fsrs_state(review_interval,
last_reviewed_at, desired_retention)` — a pure, independently unit-testable
function. This is an APPROXIMATION, not a reconstruction of real review
history: no complete per-review rating history exists anywhere in this schema
to replay. Stability is inverted from FSRS-6's own
interval-from-stability-and-retention formula, reading `FACTOR`/`DECAY`
directly off the live `fsrs.Scheduler` instance (never hardcoded literals —
they are themselves trainable-parameter-derived and would silently drift from
whatever parameter vector the scheduler actually uses). Difficulty is
obtained by running one `review_card()` call on a fresh `fsrs.Card()` with a
neutral `Rating.Good`, timestamped at the card's own `last_reviewed_at` — not
hand-derived, so it stays correct across a library version bump. Each row is
backfilled in its own small transaction (one bad row logs and is skipped, not
a startup failure); a skipped row falls back to a fresh `fsrs.Card()` on its
next real review, same as a never-reviewed card. Never writes
`next_due_at`/`review_interval`/`last_reviewed_at` — those are read-only
inputs to the synthesis, never its targets.

**Schema migration.** `essaycards.pre_fsrs_migration_backup_sprint12` — a new,
retained-indefinitely audit table (no pruning policy yet), created and
populated from the Sprint10 scheduler-assignment columns BEFORE they are
dropped, guarded by both the backup table's own absence and the source
`scheduler` column still existing (so it is correctly a no-op on a fresh
database that never had those columns, not just on a rerun). `schema.sql`
then drops `flashcard_review_state.scheduler` /
`scheduler_assigned_at` / `scheduler_assignment_reason` / `experiment_version`
and `review_events.scheduler`. The old Sprint10 `ADD COLUMN`/`CREATE INDEX`/
backfill-`UPDATE` statements for these columns are NOT reproduced in
`schema.sql` — keeping an add-then-drop pair for a permanently retired column
in the same idempotently-rerun file would churn forever (add — drop — add —
drop — ...) rather than converging; see the file's own "Sprint10_DualSchedulerAB
(retired by Sprint12)" comment block.
