# Sprint Draft — StoryReader: Tap-to-Select Interaction

## Goal

Replace freeform drag-based text selection in the Reader with a tap-count cycle:

> "the selection should be easier though: one click marks the word, two the
> sentence three the paragraph, four unselects everything. Below the
> selection the options for thumbs up, down etc appears. unselection makes
> those buttons disappear again."

## Layer / Component

03_Application / StoryReader (Sprint02, follows Sprint01_Core)

## Fast Path

Requested and confirmed by the human (2026-09-24) — not selected autonomously.

Eligibility checked against R-PRO-BP-01 §11:
- No new database table — confirmed. Word/sentence/paragraph selections still
  resolve to the existing `(paragraph_index, char_start, char_end)` span; no
  schema change.
- `files_changed` ≤ 5 — expected: `src/ShellEntry.tsx` (selection handler +
  reaction-bar positioning) and possibly one small new helper module for
  word/sentence segmentation. Backend untouched.
- No new/changed shared contract surface — the `POST /annotations` payload
  shape is unchanged; only how the frontend computes `char_start`/`char_end`
  changes.
- Single component, single layer — StoryReader frontend only.

All four criteria satisfied. Per §11.3, the resulting plan is saved as
`05_fast_path_plan.md` before implementation starts.

## Scope

- Replace `window.getSelection()`/drag-based selection in the Reader with a
  tap/click handler that resolves a tapped point to a character offset and
  cycles selection granularity on repeated taps at (approximately) the same
  spot: 1st tap = word, 2nd = sentence, 3rd = paragraph, 4th = clear
  selection. A 5th tap (i.e. the next tap after a clear) starts the cycle
  over at word.
- Reaction bar (👍👎😐❓) appears positioned below the current selection
  highlight once a selection exists (tap level 1–3), and disappears the
  moment the selection is cleared (level 4, or tapping elsewhere resets to a
  fresh level-1 word selection at the new spot rather than leaving the old
  bar up).
- Existing Sprint01 behavior is otherwise unchanged: tapping into an
  already-annotated span still shows its current reaction pre-highlighted in
  the bar (same-reaction tap removes it, different-reaction tap overwrites
  it) — see Sprint01's Reaction Semantics, untouched by this sprint.

## Out of Scope

- Any change to the Annotation data model, API, or export format.
- Arbitrary custom-length drag selection — fully replaced by the tap cycle.
- Word/sentence boundary correctness for non-English text or exotic
  punctuation — best-effort via the platform's standard segmentation.
