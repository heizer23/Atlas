# StoryReader — Tap-to-Select Interaction (Sprint02, fast path)

## Context

Sprint01 shipped a drag-based selection (`window.getSelection()` on `mouseup`/`touchend`)
for marking passages. On a phone, dragging a precise text range is fiddly. The user
wants a tap-count cycle instead: **1st tap = word, 2nd = sentence, 3rd = paragraph,
4th = clear**, with the reaction bar appearing **below** the selection (currently above)
and disappearing the instant the selection clears. This is purely a frontend interaction
change — the annotation data model, API, and reaction create/update/delete semantics
from Sprint01 are untouched; only *how a `(paragraph_index, char_start, char_end)` span
gets produced* changes.

Everything below is confined to one file:
`/home/linse/Prod/Atlas/03_Application/StoryReader/src/ShellEntry.tsx`.

## Current behavior being replaced (verified by reading the file in full)

- `onMouseUp`/`onTouchEnd={handleSelectionEnd}` on the paragraph container (:487) reads
  `window.getSelection()`, rejects cross-paragraph/zero-length selections, and computes
  `charStart`/`charEnd` via `getOffsetWithinParagraph` (:195-204, a `TreeWalker` text-node
  walk) against `closestParagraphEl` (:206-213, walks up to the nearest
  `[data-paragraph-index]` element).
- `PopoverState` (:182-193) holds `paragraphIndex/charStart/charEnd/selectedText/
  contextBefore/contextAfter/existingId/existingReaction/x/y`.
- `ReactionPopover` (:289-330) is `position: fixed`, `top: popover.y - 56` — **above** the
  selection. No pending-selection highlight exists today; the browser's native blue
  selection painted that role, driven by the real `Selection` object we're about to stop
  creating.
- `handleReact` (:429-455): same reaction tapped again → `DELETE`; anything else →
  `POST` (create or overwrite-in-place); always clears the browser selection, closes the
  popover, and refetches the annotation list. **This logic is reused unchanged.**
- `renderParagraph` (:222-275) builds a per-character `covering` array from saved
  annotations, merges same-coverage runs into segments, and renders annotated ones as
  `<mark>` with a trailing reaction-icon `<span>`. No markdown rendering — paragraphs are
  flat text, so DOM offset math stays simple.
- No `user-select` CSS, no word/sentence tokenizer, no `Intl.Segmenter` anywhere today.

## Approach

### 1. Tap → character offset (replaces the Selection-based path)

Add `caretOffsetFromPoint(x, y): { node: Node; offset: number } | null` that tries
`document.caretPositionFromPoint(x, y)` first (now supported in Firefox and Chrome),
falling back to the WebKit-only `document.caretRangeFromPoint(x, y)` (Safari) — this
covers iOS Safari and Chrome/Android, the two mobile targets that matter here. Feed the
result into the **existing** `closestParagraphEl` + `getOffsetWithinParagraph` (both
untouched, both already node/offset-based, not Selection-based) to get
`{ paragraphIndex, charOffset }`. If nothing resolves (unsupported browser, or the tap
landed outside any `[data-paragraph-index]` element), treat it as "tap elsewhere."

### 2. Level cycling — new `handleParagraphTap(e: React.MouseEvent)`

Replaces `handleSelectionEnd` as the container's handler (single `onClick`, dropping
`onMouseUp`/`onTouchEnd` — a tap fires a synthetic click on both mouse and touch, so one
handler covers both):

- Resolve `{ paragraphIndex, charOffset }` per step 1. If it fails, `setPopover(null)`
  (tap-away dismiss) and return.
- If an active `popover` exists, is in the **same paragraph**, and
  `charOffset` falls inside `[popover.charStart, popover.charEnd)` → **advance**:
  `word → sentence → paragraph → clear`. Advancing past paragraph calls
  `setPopover(null)` and returns (reaction bar disappears — the "4th tap unselects"
  requirement).
- Otherwise → **start a fresh cycle at word level** anchored at `charOffset` (covers both
  "tapped a different word" and "no popover was active").
- In both non-clearing cases, compute the new `[charStart, charEnd)` for the target
  level (step 3), then rebuild the rest of `PopoverState` exactly as
  `handleSelectionEnd` already does today (context-window slicing via the existing
  `CONTEXT_WINDOW` logic, the exact-match `existing` lookup, and the bounding-rect-based
  `x`/`y`) and `setPopover(...)`.

### 3. Word/sentence/paragraph range helpers (new, pure functions on plain text)

No `Intl.Segmenter` (inconsistent baseline support isn't worth it for English prose) —
plain regex, matching the file's existing "explicit, no new dependency" style:

- `findWordRange(text, offset)`: match `/[A-Za-z0-9''-]+/g`, pick the match containing
  `offset`, else the nearest match at-or-after `offset`, else the last match before it.
- `findSentenceRange(text, offset)`: split on `/(?<=[.!?])\s+/` boundaries (sentence-
  ending punctuation followed by whitespace), same containing/nearest rule as words,
  trimmed of surrounding whitespace.
- Paragraph level: `{ charStart: 0, charEnd: text.length }` directly, no helper needed.

These three are the only new "business logic" in the file. Documented as English-only,
best-effort — matches the draft's stated Out of Scope.

### 4. Live pending-selection highlight (new — currently missing)

Today nothing visually marks an in-progress selection; the browser's native blue
highlight did that job. Since native selection is being disabled (step 5), add a
synthetic entry to `renderParagraph`'s existing `covering`-array mechanism: when the
paragraph being rendered matches `popover.paragraphIndex`, fold
`[popover.charStart, popover.charEnd)` into the coverage computation as a pseudo-
annotation with no `id`/`reaction`, rendered with a distinct subtle style (light gray
background, no emoji) layered under/around any real `<mark>` it overlaps — so tapping
into an already-reacted passage still shows its saved highlight *plus* the pending
outline while deciding whether to change/remove it. This reuses the merge-by-same-
covering-set logic already in the file; it just adds one more "annotation-shaped" input
to it.

### 5. Disable native selection UI

Add `userSelect: 'none', WebkitUserSelect: 'none', WebkitTouchCallout: 'none',
touchAction: 'manipulation'` to the paragraph container's style — stops the browser's
own selection handles/magnifier and double-tap-zoom from fighting the custom tap
handling. (`touchAction: 'manipulation'` is defense-in-depth; Atlas Shell's mobile
viewport likely already disables pinch/double-tap zoom globally.)

### 6. Reaction bar moves below the selection

In `ReactionPopover`, change positioning from `top: popover.y - 56` (above) to
`top: rect.bottom + 8` — requires passing the pending span's bounding rect (or just its
`bottom` in viewport coords) through `PopoverState` instead of the current single `y`
(rename/repurpose the field). Compute it the same way `handleSelectionEnd` computes
`rect` today (`range.getBoundingClientRect()`), just from a Range built for
`[charStart, charEnd)` via a new small helper (`rangeForCharSpan`, the mirror-image of
the existing `getOffsetWithinParagraph` TreeWalker) rather than from
`window.getSelection()`. Clamp `top` to `window.innerHeight - <bar height> - 8` so the
bar can't run off the bottom of the viewport on a short screen.

## Files touched

- `03_Application/StoryReader/src/ShellEntry.tsx` only. No backend, schema, or API
  change (fast-path eligibility already confirmed in
  `Sprint02_TapToSelect/00_draft.md`).

## Verification

1. `npx vite build` for Atlas Shell, `docker cp dist/. atlas-shell:/usr/share/nginx/html/`
   (per the standing frontend-deploy convention for this repo).
2. Ingest a short multi-paragraph, multi-sentence test story via the existing
   `docker exec atlas-storyreader python -m backend.ingest` path so there's real content
   to tap through.
3. Manual pass in a mobile viewport (browser devtools device toolbar, since this is a
   touch-first interaction): tap a word → bar appears below it; tap again inside it →
   selection grows to the sentence; again → whole paragraph; again → bar disappears and
   highlight clears. Tap a reaction → saved highlight appears, bar closes. Tap into that
   saved highlight once (word) → bar reopens with the existing reaction pre-selected;
   tapping the same reaction removes it; tapping a different one overwrites it (Sprint01
   behavior, unchanged — just confirming the new selection path still feeds it
   correctly).
4. Record the plan file as `Sprint02_TapToSelect/05_fast_path_plan.md` before
   implementing, per R-PRO-BP-01 §11.3.
