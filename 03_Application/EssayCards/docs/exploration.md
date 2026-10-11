# EssayCards — Flashcard exploration

Split out of `CLAUDE.md` (reference detail; load when working on this area).

## Flashcard exploration (Sprint06)
Explore a *single* flashcard with ChatGPT — deliberately action-neutral at export
time (the user does not pre-decide whether the problem is their own
misunderstanding, a bad question, a wrong answer, or a missing distinction; that
emerges from the conversation).

- **Export.** `GET /api/essaycards/flashcards/{flashcard_id}/exploration-package`
  returns a bespoke JSON blob (`export_version: 1`) — the card (identified by its
  **uuid** `card_id`, with `card_key` echoed for readability), its essay/section
  metadata, and a `context` object. EssayCards has **no card→paragraph linkage**;
  the finest context available is either the whole containing section
  (`context.section_body_markdown`, a legacy card whose `nugget_id` is null) or, for
  a nugget-linked card (Sprint09), the nugget's own independent explanation
  INSTEAD OF the section (`context.nugget_body_markdown` +
  `context.nugget_key`/`context.nugget_title` — a replacement, not an addition; see
  `## Nuggets`). Same R-CON-BP-04 exemption rationale as `examination-package`. The
  **Explore** button on the revealed answer in `ReviewSessionView` fetches it and
  copies it + `EXPLORE_PROMPT_INTRO` (src/prompts.ts) to the clipboard
  ("Copied for ChatGPT"). Read-only — never touches review/scheduling state. It
  sits next to the existing "Jump to passage" control, same `jumpBtnStyle` weight,
  and after a successful copy becomes an **Import result →** button routing to
  `ExploreImportView` (reset on the next card).
- **Import.** `POST /api/essaycards/flashcards/exploration/import` — raw
  `request.json()`, `{"actions": [...]}` (a bare single action object is also
  accepted). `?dry_run=true` validates + resolves + returns the plan **without
  writing**; the `ExploreImportView` (`/essaycards/explore/import`, reachable from
  the essay list) previews that, then re-POSTs without the flag to apply.
- **Actions.** Exactly one `save_discussion` (required); 0..1 `update_card` per
  card_id; 0..n `create_card`. `update_card.changes` is whitelisted to
  `question` / `answer`; `reason` is mandatory and persisted. `create_card` needs
  `section_id` (+ optional `section_anchor_slug`, validated against it), gets an
  auto-generated `card_key` (`disc-<8hex>`) and a fresh `flashcard_review_state`
  row like ingest.
- **Atomicity & errors.** The whole import is one transaction — any failure rolls
  back every action, including the discussion. A rejected import returns a
  complete, copy-pasteable `error.message` ("EssayCards could not import … Nothing
  was saved. Fix the JSON and send the complete … package again."); the import
  view has a **Copy error for ChatGPT** button.
- **Persistence.** `flashcard_discussions` (one row per exploration;
  `question_at_time` / `answer_at_time` / `section_id_at_time` snapshotted from the
  live card *before* any `update_card` from the same import; `knowledge_gap`
  nullable) and `flashcard_revisions` (one row per Q/A edit; both old+new of both
  fields always stored; mandatory `reason`; `source_discussion_id` links the edit
  to its discussion). Historical question/answer text lives **only** in
  `flashcard_revisions` — `flashcards` always holds just the current version, so an
  edited-away question never reappears in `GET /flashcards/due`. The returned JSON
  is transport only; it is decomposed into these rows and never stored verbatim.
- Backend: `backend/exploration.py` (build/validate/plan/execute) +
  `backend/routers/exploration.py` (registered after `flashcards.router`).
