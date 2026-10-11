# EssayCards — External-AI flows (export → ChatGPT → import)

Split out of `CLAUDE.md` (reference detail; load when working on this area).

## External-AI flows
Every flow has the same shape: the UI fetches an **export package** (JSON) from the
backend, copies **prompt intro + package** to the clipboard (`writeClipboard`), the user
chats with an external AI, pastes its JSON **reply** into an import view, and the backend
validates and applies it. Prompt text and the clipboard helpers all live in `src/prompts.ts`.
Packages are bespoke JSON, not `Dataset` (R-CON-BP-04 exemption, as for `examination-package`).

| # | Flow | Trigger (view) | Export endpoint | Prompt (`src/prompts.ts`) | Import view → endpoint | Reply is |
|---|---|---|---|---|---|---|
| 1 | Guided oral (section / essay) | `ReaderView` section / essay menu | `GET /essays/{id}/examination-package?scope=essay (or section)&exam_type=guided[&section_id=…]` | `EXAM_PROMPT_INTRO_GUIDED` via `buildExamClipboardText` | `ImportExaminationsView` → `POST /examinations/import` | exam result JSON |
| 2 | Unguided oral (section / essay) | `ReaderView` section / essay menu | same, `exam_type=unguided` | `EXAM_PROMPT_INTRO_UNGUIDED` via `buildExamClipboardText` | same as 1 | exam result JSON |
| 3 | Explore a flashcard | `ReviewSessionView` | `GET /flashcards/{id}/exploration-package` | `EXPLORE_PROMPT_INTRO` | `ExploreImportView` → `POST /flashcards/exploration/import` (`?dry_run=true` preview, then apply) | exploration actions JSON |
| 4 | Export whole essay | `ReaderView` essay menu | `GET /essays/{id}/export` | `ESSAY_EXPORT_PROMPT_INTRO` | `IngestView` → `POST /essays/ingest` | full ingest payload |
| 5 | Export section | `ReaderView` section menu | `GET /essays/{id}/sections/{sid}/export` | `SECTION_EXPORT_PROMPT_INTRO` | `IngestView` → `POST /essays/ingest` | full ingest payload (only the focus section changed) |
| 6 | Improve section (Sprint15) | `ReaderView` section menu | same, `?include_examinations=true` (adds `focus_section_examinations`) | `SECTION_IMPROVE_PROMPT_INTRO` | `IngestView` → `POST /essays/ingest` | full ingest payload (examinations field omitted) |
| 7 | Insert section after | `ReaderView` section menu | same as 5 + client-spliced placeholder (`buildInsertPlaceholderSection`) | `SECTION_INSERT_PROMPT_INTRO` | `IngestView` → `POST /essays/ingest` | full ingest payload |
| 8 | Export one question | `QuestionOverviewView` | `GET /flashcards/{id}/export` | `QUESTION_EXPORT_PROMPT_INTRO` | `QuestionImportView` → `POST /flashcards/upsert` | question upsert JSON |
| 9 | Author / revise a nugget | `NuggetAuthoringImportView` | `GET /nuggets/authoring-package` | `NUGGET_AUTHORING_PROMPT_INTRO` | same view → `POST /nuggets/upsert` | nugget upsert JSON |
| 10 | Generate flashcards for a nugget | `NuggetPanel` → `GenerateFlashcardsImportView` | `GET /nuggets/{id}/generate-flashcards-package` | `GENERATE_FLASHCARDS_PROMPT_INTRO` | same view → `POST /flashcards/upsert` | card upsert JSON |
| 11 | Write a new essay from scratch | `IngestView` ("copy prompt") | none (no package) | `STUB_PROMPT` (in `views/IngestView.tsx`) | `IngestView` → `POST /essays/ingest` | full ingest payload |

Detail per flow: 1–2 `oral_progression.md`; 3 `exploration.md`; 4–7 `export_insert.md` and
`ingestion.md`; 8 `question_levels.md`; 9–10 `nuggets.md`.

## Where each part is defined
- **Export package:** backend router/module (paths above); examination packages are built in
  `backend/examinations.py`, exploration in `backend/exploration.py`.
- **Prompt text + clipboard text builder:** `src/prompts.ts` (flow 11's `STUB_PROMPT` and the
  placeholder JSON templates stay in their import views).
- **Package/reply TypeScript types:** `src/types.ts`.
- **Reply validation/apply:** the import endpoint's backend module (`ingest.py`,
  `examinations.py`, `exploration.py`, routers for 8–10).

## Rules that must not be duplicated into prompts
- **Oral pass rule** lives only in `backend/oral_state.py` (`PASS_THRESHOLD_PERCENT`). Exam
  packages echo it (`oral_state.scoring_echo()`) — as `scoring` in exam packages and as
  `focus_section_scoring` in the Improve-section export — and the prompts read it from there.
  No prompt hard-codes the threshold.
- **Card `level`, essay `status`/`category`** semantics are described in the prompts for the
  model's benefit; the authoritative validation is in the backend.

## Adding a flow
1. Backend: export endpoint + import endpoint (validate fully before writing; atomic apply).
2. `src/types.ts`: package/reply types. `src/prompts.ts`: intro constant + `build…ClipboardText`.
3. UI: a trigger in the owning view, an import view (or reuse `IngestView`), a `<Route>` in `ShellEntry.tsx`.
4. Add a row to the table above and a test for the export shape and the import validation.
