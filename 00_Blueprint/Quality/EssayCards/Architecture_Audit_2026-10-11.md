# Architecture Audit — EssayCards — component-level (post-Sprint15)

**Verdict:** APPROVED_WITH_CHANGES
**Date:** 2026-10-11
**Reviewer:** architecture audit (general-purpose agent, read-only on code)
**Scope:** `03_Application/EssayCards` as a whole: layer conformance, backend module structure, frontend structure, schema, API design, ops/security posture, docs/snapshot drift, and sustainability. This is a design-level audit. It does not repeat the line-level findings of `Code_Review_2026-10-11.md`.

**Method / evidence base:** I read the manifest, `R-CON-BP`, `R-CON-AL`, `R-CON-PL`, `R-OPS-BP`, `R-PRO-BP`, the component `CLAUDE.md`, `docs/`, the prior reviews and `Rule_Audit_2026-10-11.md`. I read the whole backend structurally and `routers/flashcards.py`, `routers/essays.py`, `progress.py` and `schema.sql` in full. I outlined `src/ShellEntry.tsx`. Live checks were read-only:
- `nginx -T` on `atlas-shell`.
- `docker ps` for port bindings.
- Malformed-id GET probes against `atlas-essaycards-test` (port 9024).
- One read-only integrity `SELECT` on prod `atlas` (7 essays, 202 cards, 347 review events, 25 images, 0 sentence_feedback rows).

**Status of the code review's items:**
- Item 1 (422 shape) and item 2 (malformed path ids → 500) were fixed in `4f4b365`. That commit added a platform `RequestValidationError` handler and a global path-id guard in `main.py:20-45`.
- Item 4 (Sprint15 docs) is partly fixed: `docs/export_insert.md:52` now covers "Improve section".
- Residuals of items 1, 2 and 4 appear below only where the remaining problem is structural (M4, M7).

**Overall:** The backend domain core is in good shape:
- `progress.py` is the single place for derived-state SQL.
- `oral_state.py`, `revalidation.py` and `scheduling.py` are small modules without HTTP code.
- History lives in append-only logs.
- Traffic lights are derived and never stored.
- SQL is parameterised, and the backend is bound to `127.0.0.1`.

The structural risks sit at three edges:
1. The architecture snapshot and rebuild path have drifted (H1).
2. The 5.3k-line frontend file (H2).
3. The LLM round-trip "protocols" are spread across two languages and four places (H3).

Nothing here is blocking for daily use.

---

## Blocking Issues

_(None)_. No finding breaks the running system. H1 breaks only a fresh-database rebuild.

## Findings (ranked)

Each finding is classified as either a **[RULE]** violation (it cites the rule or the documented invariant it breaks) or a **[JUDGEMENT]** improvement (no rule requires it).

| # | Impact | Class | Finding | Minimal recommendation |
|---|---|---|---|---|
| H1 | High | RULE (R-CON-BP-07, R-CON-BP-01) | Architecture snapshot and rebuild path have drifted (see below). | Point the Makefile at `schema.sql` and fix the snapshot semantics (see below). |
| H2 | High | JUDGEMENT | `src/ShellEntry.tsx` is a 5,259-line monolith. | Mechanical split by route/view, with no behaviour change (see below). |
| H3 | High | JUDGEMENT | The LLM round-trip protocols are split across backend and frontend, and the prompts hard-code domain rules. | Create a single `prompts.ts` plus a protocol registry doc; prompts take rule values from packages (see below). |
| M1 | Medium | JUDGEMENT | The "create a card" invariant is implemented in 3 places. | Add a `backend/cards.py::create_card()` and call it from all three. |
| M2 | Medium | JUDGEMENT | The core review use-case lives in a router. Two domain modules return `JSONResponse`. | Extract `backend/review.py` when next touched. |
| M3 | Medium | RULE (CLAUDE.md:87 documented invariant) | Interval thresholds are duplicated as literals. | Import `ESTABLISHED_INTERVAL_SQL` (2 lines). |
| M4 | Medium | JUDGEMENT (+ residual R-CON-BP-04 behaviour) | Validation is fragmented: two HTTP statuses for `VALIDATION_ERROR`, four id-validation strategies, and query-param ids still return 500. | One id guard covering query params; decide the status code; allow Pydantic models going forward. |
| M5 | Medium | JUDGEMENT (functional) | The image-upload cap is 12 MiB in the app, but nginx defaults to 1 MiB. | Add `client_max_body_size 12m;` scoped to `location /api/essaycards`. |
| M6 | Medium | R-OPS-BP-02 — verification required | A Cloudflare tunnel is running with remotely managed ingress, and EssayCards has unauthenticated mutations. | Confirm that the tunnel does not route to `atlas-shell`, or that Cloudflare Access gates it. |
| M7 | Medium | RULE (R-CON-BP-01 legibility; R-CON-BP-09 spirit) | Glossary and schema comments contradict Sprint14 behaviour; there are dangling cross-references; two feature areas have no docs. | One doc pass (list below). |
| M8 | Medium | JUDGEMENT | The schema "migration" is an 874-line idempotent file re-run at every startup, with heuristic one-shot guards and no ledger. | Adopt a ledgered migrations directory at the next non-additive change. |
| L1 | Low | JUDGEMENT (manifest rule 7 / Platform definition) | Platform-type code is copied into the app: `database.py` (identical in 4 apps), `_dataset_response` (8 copies), and the uuid guard. | Promote `dataset_response()` and the id guard to platform packages; route the `database.py` question to the architecture agent. |
| L2 | Low | RULE (R-CON-BP-04 "never redefine locally") | A local `interface Dataset<T>` is defined at `ShellEntry.tsx:482`. | Make the platform `Dataset` generic (additive), then import it. |
| L3 | Low | JUDGEMENT | `flashcards` and `section_examinations` carry both `essay_id` and `section_id`, with no composite FK. | Optional: add `unique(id, essay_id)` plus composite FKs. |
| L4 | Low | JUDGEMENT | `/essays/{id}/*` routes are spread over 3 routers, router registration order matters, and endpoint naming is inconsistent. | Add a naming convention for new endpoints only; no renames. |
| L5 | Low | Rule gap (R-CON-BP-04) | 7 bespoke-JSON GET "package" endpoints each argue their own Dataset exemption. | Codify a "transport package" category in R-CON-BP-04. |
| L6 | Low | R-OPS-BP-02 | The container runs as root and the runtime image ships tests and dev dependencies. | Add `USER` and a non-root UID owning `/app/images` and `/app/logs` (cross-app pattern). |
| L7 | Low | JUDGEMENT | The frontend hard-codes domain lists (`CATEGORY_ORDER`, forecast bands). | Leave as-is; fold into the H2 split's `constants.ts`. |

---

## High

### H1 — Architecture snapshot and rebuild path have drifted  [RULE: R-CON-BP-07, R-CON-BP-01]

**Evidence:**
- `00_architecture/schema.sql` is byte-identical to `Sprint13_ReviewStatsSentenceFeedback/10_schema.sql` (`cmp`). It is a 77-line delta that only creates `essaycards.sentence_feedback`.
- The `summary` field of `00_architecture/architecture.json` is Sprint13's sprint summary ("Reworks EssayCards' Review and Stats pages…"). It does not describe the component. Sprint14 (oral state, locking, revalidation, 4 new tables) and Sprint15 are absent.
- `01_System/Makefile:407-410` `essaycards-schema` pipes **`00_architecture/schema.sql`** into `psql -v ON_ERROR_STOP=1`, and `make up` invokes it (`Makefile:789`). On a fresh database this fails, because the `essaycards` schema and `essay_sections` do not exist yet. That aborts `make up` before `essaycards-build` and every later app (storyreader, console, cloudflared). This is reasoned, not executed. On the existing DB it is a harmless no-op.
- `storyreader-schema` (`Makefile:441`) correctly uses the runtime `schema.sql`.
- `CLAUDE.md:200-205` states that the runtime `schema.sql` is canonical and calls the design copy "one sprint stale (missing `essaycards.images`)". That description is itself stale: the copy is now a single-table delta.
- The design agents treat `<component_root>/00_architecture/architecture.json` as the baseline for new sprints (`.claude/agents/sprint_design_application.md:101`). A Sprint16 designer would therefore start from a pre-Sprint14 model.

**Root cause (systemic, not EssayCards-specific):**
- `.claude/skills/sprint-close.md:48` copies the sprint-local `10_schema.sql`, which is a delta, into `00_architecture/schema.sql`.
- `sprint-close.md:97` generates the make target against that copy.
- Sprint14 and Sprint15 were never closed, so even this weak refresh did not run (already counted in `Rule_Audit_2026-10-11.md` item 5).

**Minimal recommendation:**
1. Change `Makefile:410` to `$(ESSAYCARDS_DIR)/schema.sql`. Alternatively, drop the target, since `init_schema()` already applies it at startup.
2. Replace `00_architecture/` with a component-level snapshot. The cheapest honest version is to delete `00_architecture/schema.sql` and regenerate `architecture.json` from the current code plus `docs/`, or else state in `CLAUDE.md` that `schema.sql` + `docs/` are the snapshot.
3. Fix `CLAUDE.md:200-205`.
4. Systemic, for the human or the rule audit: `sprint-close` must never write a sprint delta into `00_architecture/schema.sql` or generate a make target against it. This is the same class of problem as Rule Audit row R-CON-BP-07 ("sprint delta vs runtime path is undefined in the template").

### H2 — `src/ShellEntry.tsx` monolith  [JUDGEMENT]

**Evidence:**
- 5,259 lines in one file.
- 13 routed views (`ShellEntry.tsx:5239-5258`).
- About 50 interfaces (`:46-487`) and 125 `useState` calls.
- 48 `apiFetch` call sites.
- About 700 lines of LLM prompt and placeholder text (`:791-1196`, `:2915`, `:3640-3767`, `:4001`, `:4168`, `:4676`, `:4817`).
- Large views: `ReaderView` (`:2024-2553`, about 530 lines) and `ReviewSessionView` (`:3298-3767`, about 470 lines).
- It is 2.6× the next-largest app entry (TaskTracker 2,025 lines).
- The Shell already supports multi-file app sources: FoodTracker's `ShellEntry.tsx:25-28` imports `./ReportPage` etc.

**Why it matters here:** Manifest rule 3 says LLM legibility is a design constraint. Every sprint since Sprint09 has edited this one file. Agents must load or search 5k lines to make a local change, and unrelated views share a single module scope, so a name collision or a stray shared style constant silently couples views.

**Minimal recommendation (proportionate, one mechanical commit, no behaviour or state-management change):**
```
src/ShellEntry.tsx          routes only (~40 lines)
src/types.ts                row/package interfaces (:40-487)
src/prompts.ts              all *_PROMPT_INTRO, STUB_PROMPT, *_PLACEHOLDER_JSON, build*ClipboardText (see H3)
src/styles.ts               btnStyle/primaryBtnStyle/gradeStyleFor/etc.
src/constants.ts            FORECAST_COLUMNS, CATEGORY_ORDER, legend text
src/components/             ActionMenu, ProgressDot family, NuggetPanel/NuggetLink/remarkNuggetRefs, Forecast*, ReviewStats*
src/views/<View>.tsx        one file per routed view (EssayList, Reader, QuestionOverview, QuestionImport, ReviewSession, Ingest, ImportExaminations, ExploreImport, Images, NuggetAuthoringImport, GenerateFlashcardsImport, ReviewStats)
```
- Keep `shellConfig.ts`'s `lazy(() => import('./ShellEntry'))` unchanged (R-CON-BP-06).
- The existing Playwright specs (`tests/ui/*.spec.ts`) are the safety net. The deploy hook rebuilds automatically.
- Do not introduce a state library or data-fetching layer as part of this split.

### H3 — LLM round-trip protocols are split across layers and languages  [JUDGEMENT]

**Evidence:** EssayCards' main integration surface is 9 export → external LLM → import flows:
- exam (guided/unguided)
- explore
- section export / improve / insert
- essay export
- question export
- nugget authoring
- generate flashcards
- the ingest stub

Each flow's contract is defined in up to four places:
1. a backend package builder (`examinations.py::build_export_package`, `exploration.py::build_exploration_package`, `routers/essays.py:439/493`, `routers/nuggets.py:225/427`, `routers/flashcards.py:717`);
2. a TSX prompt (`ShellEntry.tsx:791-1196`, `:3640`);
3. a TSX placeholder JSON;
4. a backend validator (`routers/essays.py:634-840`, `examinations.py:250`, `exploration.py:148`, `routers/nuggets.py:160`).

Domain rules are hard-coded into prompt prose:
- `ShellEntry.tsx:999`: "score (0-6; 5 or higher passes)". `oral_state.py:25-31` is documented as the single home of the pass rule. The exam prompts at `:811`/`:857` do this correctly, because they defer to the package's `scoring.min_passing_score`.
- `STUB_PROMPT` (`:3640-3767`) restates the ingest schema in prose. Any validator change in `_validate_ingest_body` has to be mirrored there by hand.

`export_version` exists on 6 packages but not on the exam package, and no importer checks it.

**Why it matters:** Manifest rule 4 says contracts are more durable than code. These protocols are the app's de-facto contracts, yet no single artifact enumerates them. Each new flow adds four places to keep in sync, and a threshold change, such as making the pass rule configurable (noted as intended at `schema.sql:660-661`), silently desynchronises prompts.

**Minimal recommendation:**
1. Do this as part of H2: collect all prompts and placeholders in `src/prompts.ts`.
2. Add `docs/llm_protocols.md`, a one-table registry. Columns: flow | package endpoint | builder fn | prompt const | import endpoint | validator fn | version field.
3. Rule: a prompt may cite a numeric domain rule only through a field the package carries, following the `scoring.min_passing_score` precedent. Fix `:999` by adding `scoring` to the section-export package when `include_examinations=true`.
4. Optional later step, not now: serve the prompt text from the backend alongside the package, so that one Python module owns each protocol end to end.

---

## Medium

### M1 — "Create a card" invariant implemented in 3 places  [JUDGEMENT]
- "Every card has exactly one `flashcard_review_state` row, seeded `last_reviewed_at=null`, `next_due_at=created_at`, `review_interval='0'`" is written independently in `ingest.py:531-557`, `exploration.py:525-545` and `routers/flashcards.py:638-662`.
- Two of the three rely on the column default for `review_interval`; ingest sets it explicitly.
- The `_new_card_key` helper is duplicated on purpose (`exploration.py:438`, `routers/flashcards.py:553`; the docstring says "each module owns its own key-generation concern").
- The prod check shows 0 cards without a state row today. The risk is the 4th writer: a future card-creating flow that forgets the seed would produce a card that never appears in any queue.
- **Recommendation:** add `backend/cards.py::create_card(cur, essay_id, section_id, card_key, question, answer, level=None, nugget_id=None) -> row` (insert plus seed) and `new_card_key(cur, essay_id, prefix)`, and call them from the three sites. Keep the different upsert semantics (ingest may move sections, `/upsert` may not) in the callers.

### M2 — Core review use-case lives in a router; HTTP types leak into domain modules  [JUDGEMENT]
- `routers/flashcards.py:865-974` holds the app's most important state transition: the lock guard, the revalidation branch, the FSRS call, the state UPDATE, the `fsrs_card_state` upsert, the `review_events` append and the revalidation audit. The neighbouring rules (`scheduling.py`, `revalidation.py`, `oral_state.py`) are cleanly extracted, but the orchestration and its persistence helpers (`_load_fsrs_existing_state`, `_upsert_fsrs_card_state`, `_insert_review_event`, `:795-862`) are router-private. Any new mode, like the Sprint14 revalidation, must be threaded through an HTTP handler.
- In the other direction, `examinations.py:54` and `exploration.py:44,57` import `api_error` and return `(result, JSONResponse)` tuples. Domain modules therefore produce HTTP responses.
- **Recommendation:** extract `backend/review.py::apply_review(cur, flashcard_id, grade) -> ReviewOutcome | ReviewError` the next time review behaviour changes. Do not do this as a standalone refactor. Leave the tuple-returning validators alone: they are cheap, consistent within the app and well tested. Do not copy the pattern into new modules.

### M3 — Documented single-source thresholds duplicated  [RULE: CLAUDE.md:87]
- `CLAUDE.md:87` says "Thresholds live once in `backend/progress.py` (`ESTABLISHED_INTERVAL_SQL`, `LEARNED_INTERVAL_SQL`)".
- The literal `interval '24 hours'` (meaning *established*) still appears in `routers/essays.py:201` (`progress_established`) and `routers/flashcards.py:245` (the review-mode eligibility filter).
- The "recent" 24h at `flashcards.py:265,275,277,444` is a different concept (a rolling relearning window) and is fine to keep.
- Frontend copies of thresholds are text only (`ShellEntry.tsx:1600,1612` "30 days"; `:711-718` mirrors the `/stats` bands): acceptable, but see L7.
- **Recommendation:** import `ESTABLISHED_INTERVAL_SQL` at the two sites. This is a 2-line change with no behaviour change.

### M4 — Validation and id-handling strategy is fragmented  [JUDGEMENT, residual R-CON-BP-04 behaviour]
- **Two statuses for one error code.** Manual validators return `VALIDATION_ERROR` with **400** (`platform_errorhandling/api_response.py:5` default). The new platform handler returns `VALIDATION_ERROR` with **422** (`logFastapi.py:16-28`). The raw-`Request` deviation documented in `CLAUDE.md:175-180` existed only to avoid FastAPI's 422 *shape*, and that reason disappeared with `4f4b365`. It still forces about 600 lines of hand-written validators (`routers/essays.py:634-840`, `routers/flashcards.py:474-550`, `examinations.py:250-380`, `exploration.py:148-347`, `routers/nuggets.py:160-220`), and the nugget field rules are duplicated between `essays.py:695-736` and `nuggets.py`.
- **Four id strategies:**
  1. global path guard (`main.py:20-45`);
  2. local `_is_uuid` returning an empty result (`routers/progress.py:51`, `routers/flashcards.py:62`, `exploration.py:66`);
  3. `::text` comparison (`routers/review_stats.py:328-332`, `sentence_feedback.py`);
  4. no handling at all.
- Strategy 4 is live: `GET /flashcards/due?essay_id=bogus` → **500**, `/flashcards/stats?essay_id=bogus` → **500**, `/nuggets/authoring-package?essay_id=bogus&section_id=x` → **500**. Verified on the test container. Code review item 2 covered path ids only.
- **Scope validation copied 3×.** The rules "section_id requires essay_id" and "topic excludes ids" plus the scope filter SQL appear in `flashcards.py:224-256`, `:338-361` and `review_stats.py:311-333`.
- **Recommendation:**
  - (a) Extend the `main.py` guard to query params ending in `_id` (one loop over `request.query_params`), then delete the local `_is_uuid` copies.
  - (b) Pick one status for `VALIDATION_ERROR` (simplest: accept both and record the fact in `CLAUDE.md`, or make the platform handler use 400). Update `CLAUDE.md:175-180` to say Pydantic body models are allowed for new endpoints. Do not rewrite existing validators.
  - (c) Extract `_scope_filter(topic, essay_id, section_id) -> (join, conditions, params) | ApiError` into one helper.

### M5 — Upload cap mismatch between app and proxy  [JUDGEMENT, functional]
- `routers/images.py:60` sets `MAX_UPLOAD_BYTES = 12 MiB` and documents a 413 `PAYLOAD_TOO_LARGE` ApiError.
- The live `nginx -T` on `atlas-shell` has no `client_max_body_size` anywhere, so nginx's 1 MiB default applies to `/api/essaycards`.
- Browser uploads between 1 and 12 MiB (typical phone photos) are therefore rejected by nginx with an HTML 413 before they reach the app's capped stream and its ApiError.
- I did not exercise this, to avoid writing to prod.
- **Recommendation:** add `client_max_body_size 12m;` **inside** `location /api/essaycards` in `02_Platform/Atlas_Shell/nginx.conf`, not server-wide, so other apps keep the default (R-OPS-BP-02 least exposure). This requires the full shell rebuild path per the frontend-deploy note.

### M6 — Public exposure needs verification  [R-OPS-BP-02, verification required]
- The backend is correctly bound to `127.0.0.1:8024` (`compose.yml:9`). The content and staging mounts are `:ro`. SQL is parameterised.
- `atlas-shell` listens on `0.0.0.0:80`, and `atlas-cloudflared` is running with a token-managed tunnel whose ingress lives in the Cloudflare dashboard (`01_System/Access/cloudflared/compose.yml`), so I could not inspect it.
- EssayCards has no authentication of its own, which is the Atlas pattern of relying on the perimeter. It exposes mutations that are destructive in effect: `POST /essays/ingest` overwrites content, and `POST /examinations/import` can trigger the revalidation cascade. It also exposes CPU-heavy ones: `/images/upload` (Pillow decode/re-encode) and `/images/scan`.
- **Recommendation:** confirm that the tunnel does not route a hostname to `atlas-shell`, or that Cloudflare Access gates it. If it does route there, this becomes a System-layer High. No EssayCards change is needed if the perimeter holds.

### M7 — Doc and comment drift not covered by the code review  [RULE: R-CON-BP-01; R-CON-BP-09 spirit]
| Location | Drift |
|---|---|
| `CLAUDE.md:16-19` | Says that `status`, `review_interval` and focus/review "may not all be in the code yet". All have shipped. |
| `CLAUDE.md:113-114` | Says "Current understanding" of a section is always the latest exam row. Since Sprint14 it is the **sticky** `section_oral_state` (a guided pass is never revoked, and grandfathered unlocks exist). |
| `schema.sql:150-153` | Says "there is no separate stored current-score field anywhere in the schema". This is false since Sprint14 (`*_latest_score` in `section_oral_state` / `essay_oral_state`). |
| `schema.sql:410-414` | Says the "`scheduler` column on flashcard_review_state is the single source of truth" for whether `fsrs_card_state` rows exist. That column was dropped at `schema.sql:540`. |
| `schema.sql:338,606`; `:593` | Cross-reference `CLAUDE.md "Known gaps"` and `"Essay reader sentence feedback"`. Neither heading exists. "Known gaps" is now a bold paragraph in `docs/oral_progression.md:111`. |
| `docs/` | Sentence feedback (Sprint13) and the review-stats endpoints (`/review-stats/summary|activity|today|intervals`, Sprint11/13/15) have no doc page. They appear only in `sprint_history.md`. |

**Recommendation:** one doc-only commit that fixes the six rows above. Add `docs/sentence_feedback.md` and `docs/review_stats.md`, or a section in `scheduling.md`, and add them to the `CLAUDE.md` doc map.

### M8 — Schema evolution has no ledger  [JUDGEMENT]
- `schema.sql` is 874 lines, about 60% of them sprint history in comments. It is re-executed in a single transaction at **every** startup and test session.
- One-shot data migrations are guarded heuristically rather than recorded:
  - `:133-136` uses `review_interval = '0'` as the "not yet backfilled" signal;
  - `:509-530` checks table absence plus column presence;
  - `:758-837` checks table absence, then performs grandfathering;
  - `:687-688` runs an `UPDATE` plus `ALTER COLUMN … SET NOT NULL` (an `ACCESS EXCLUSIVE` lock) on every boot.
- `migrate_fsrs_state.py` also runs on every startup (`main.py:77-80`).
- This works at the current size (202 cards). The risk grows with each **non-additive** change: there is no record of what ran, a guard that stops matching re-runs a migration, and retired-feature notes accumulate (`:389-405`).
- **Recommendation (proportionate):** change nothing until the next non-additive schema change. At that point:
  - add `essaycards.schema_migrations(id text primary key, applied_at timestamptz)`;
  - add `migrations/NNN_<name>.sql`, applied once and in order by `init_schema()`;
  - freeze `schema.sql` as the baseline;
  - move the historical comments into `docs/`.
- This is a generic capability. Before building it per app, ask the architecture agent whether it belongs in a platform package (see L1).

---

## Low

- **L1 — Platform-type code copied into the app [JUDGEMENT; manifest rule 7 / Platform definition].**
  - `backend/database.py` is byte-identical in EssayCards, ClaudeConsole, StorageTracker and StoryReader (md5 `719ac549`), and 11 apps carry variants.
  - `_dataset_response()` is copied 8× inside EssayCards alone (every router).
  - The malformed-id guard (`main.py:20-45`) is generic.
  - None of this violates "applications never provide platform services", because nothing outside the app consumes these helpers. It is, however, a generic shared capability living in 03.
  - **Recommendation:** promote `dataset_response()` into `platform_contracts` and the id guard into `platform_errorhandling`, both small and additive. Send the `database.py` / migration-runner question to the architecture agent, because it touches every app.
- **L2 — Local Dataset redefinition [RULE: R-CON-BP-04 "Import from them — never redefine locally"].**
  - `ShellEntry.tsx:482` declares `interface Dataset<T> { meta; rows: T[] }`. It does this because the platform type (`platform-ui/api/types.ts:30-37`) is not generic. HabitTracker and StoryReader do the same.
  - **Recommendation:** make the platform type `Dataset<R extends Row = Row>`. This is an additive, non-breaking change per the R-CON-BP-04 stability clause. Then import it.
- **L3 — Denormalised parent ids without a composite FK [JUDGEMENT].**
  - `flashcards` (`schema.sql:66-86`) and `section_examinations` (`:161-173`) store both `essay_id` and `section_id`. Only application code keeps them consistent. The prod check found 0 mismatches.
  - **Optional:** add `alter table essay_sections add unique (id, essay_id)` plus composite FKs `(section_id, essay_id) → essay_sections(id, essay_id)`. This is cheap and guards the nugget cross-essay case documented at `schema.sql:337-346`.
- **L4 — Route ownership and naming [JUDGEMENT].**
  - `/essays/{id}/…` endpoints live in three routers: `essays.py`, `examinations.py:75,211` and `sentence_feedback.py:72,95`.
  - `main.py:59` documents a registration-order dependency between `flashcards` and `exploration`.
  - Endpoint verbs vary: `export` / `*-package` / `ingest` / `upsert` / `import`.
  - **Recommendation:** add one line to `CLAUDE.md` naming the convention for **new** endpoints (for example `GET …/<thing>-package`, `POST …/<thing>/import`). Do not rename existing endpoints.
- **L5 — Dataset-exemption rule gap [rule gap, R-CON-BP-04].**
  - Seven GET endpoints return bespoke JSON: the examination, exploration, authoring and generate-flashcards packages, and the essay, section and question exports. Each justifies its exemption by citing another endpoint's docstring ("same rationale as examination-package").
  - The reasoning is sound, since these responses are clipboard transport and are not rendered, but R-CON-BP-04 does not name this category.
  - **Recommendation (for the rule owner):** add a "transport package" category (GET, not rendered, versioned via `export_version`) to R-CON-BP-04.
- **L6 — Container least privilege [R-OPS-BP-02].**
  - `Dockerfile` has no `USER`, so the app runs as root with a writable `/app/images` bind mount.
  - The runtime image includes `.[dev]` and `tests/` (`Dockerfile:9,13`), because the same image serves the `-test` container.
  - This is a cross-app pattern.
  - **Recommendation:** add a non-root `USER` with a matching UID on `${DATA_ROOT}/essaycards/{images,logs}`. Defer the test/runtime image split.
- **L7 — Frontend domain constants [JUDGEMENT].**
  - `CATEGORY_ORDER = ['Art','History','Philosophy']` (`ShellEntry.tsx:1500`) re-sorts the free-text categories that the server already orders (`routers/essays.py:215`).
  - `FORECAST_COLUMNS` (`:711-718`) mirrors `STATS_BUCKETS` by comment only.
  - **Recommendation:** acceptable for a solo app. Move both into `constants.ts` during H2 so they are visible.

---

## Area assessments (summary)

1. **Layers and boundaries.**
   - Correctly classified as 03_Application.
   - Platform dependencies run one way only: `platform_contracts` and `platform_errorhandling` (Python), `@platform-ui` (TS), and Shell registration via `shellConfig.ts` (R-CON-BP-06 respected).
   - There are no cross-application reads; the schema is private and exposes no shared views.
   - The only boundary issues are L1 and L2 (platform gaps that the app is compensating for) and the H1 System-layer Makefile coupling.
2. **Backend structure.**
   - Strong: `progress.py` (one home for derived-state SQL), `oral_state.py`, `revalidation.py`, `scheduling.py` (pure), `sentences.py`, `ingest.py::upsert_document` shared by the CLI and JSON paths.
   - Weak: M1 (card creation in 3 places), M2 (review orchestration in a router), M3 (threshold literals) and M4 (validation duplication).
   - SQL inside routers for read endpoints is acceptable at this scale and not a layering violation in Atlas.
3. **Frontend.** See H2. The split is overdue and mechanical; it needs no architecture change.
4. **Data model.**
   - Good:
     - append-only logs (`review_events`, `section_examinations`, `essay_examinations`, `revalidation_events`, `flashcard_revisions`);
     - explicit CHECKs throughout;
     - colours derived, never stored;
     - `review_interval` documented as a single-writer cache;
     - `section_oral_state` correctly treated as durable state rather than a cache, because grandfathering and sticky passes cannot be re-derived from the log.
   - Indexes match the documented access paths.
   - Gaps: L3 and M8.
5. **API design.**
   - `Dataset` is used consistently for rendered GETs (the code review verified all 16).
   - The `ApiError` envelope is now universal.
   - Gaps: the mixed 400/422 status and the query-id 500s (M4), the uncodified package exemption (L5) and naming drift (L4).
   - Versioning exists only as `export_version` on packages, which is adequate for a single-consumer app.
6. **Ops and security.**
   - Good:
     - localhost-bound port;
     - read-only content and staging mounts;
     - parameterised SQL;
     - the upload is size-capped while streaming;
     - images are re-encoded with metadata stripped;
     - SVG is rejected;
     - `GET /images/{slug}` resolves through the DB, not the filesystem path.
   - Open items: M5, M6 and L6.
   - CORS (`main.py:48-53`) is localhost-only, and only for the dev server.
7. **Testability and drift.**
   - Testing is good: 344 backend tests against a real Postgres database with a fixture world, plus 9 Playwright specs. The no-global-literal-counts convention is already adopted.
   - Drift is the weak point: H1 (snapshot) and M7 (glossary and comments). The code review's docs item 4 has been partly addressed.
8. **Sustainability, in order of growth risk:**
   1. H2 + H3: every feature touches the monolith and adds another four-place protocol.
   2. H1: designers working from a stale baseline.
   3. M8: unledgered migrations.
   4. M1/M2: invariants copied across writers.

## Suggested order (smallest first)
1. `Makefile:410` path, and `CLAUDE.md:200-205` (H1, 2 lines).
2. Import `ESTABLISHED_INTERVAL_SQL` (M3, 2 lines). Add the query-param id guard (M4a).
3. Verify the tunnel ingress (M6). Add the scoped `client_max_body_size` (M5).
4. Doc-only pass (M7). Regenerate or retire `00_architecture/` (H1.2). Close S14/S15 with `/sprint-close` once its snapshot step is fixed.
5. Mechanical frontend split, including `prompts.ts` and `docs/llm_protocols.md` (H2 + H3), as one no-behaviour-change commit.
6. When next touched: `cards.py` (M1), `review.py` (M2), migration ledger (M8).

## Process note (R-OPS-BP-01)
R-PRO-BP-02 asks auditors to append evidence entries for Major and Critical findings to `00_Blueprint/Quality/agent_rule_evidence.md`. The caller limited this run to writing this report only, so **no evidence entries were appended**. These are the proposed entries, for a human or a follow-up run to append:
- `pattern_name: architecture_snapshot_is_sprint_delta`: H1. `likely_root_cause: agent_gap` (the `sprint-close` skill). `candidate_response: skill`. Related to the Rule Audit R-CON-BP-07 row.
- `pattern_name: llm_protocol_split_across_layers`: H3. `likely_root_cause: rule_gap`. `candidate_response: design_template`. First observed.
- `pattern_name: documented_single_source_constant_duplicated`: M3. `likely_root_cause: none`. `candidate_response: none`. First observed.

## Approval Condition
None of these items blocks use. The audit resolves when:
- H1 step 1 (the Makefile path) is fixed;
- M6 is verified;
- the remaining items are either scheduled or explicitly declined by the human.
