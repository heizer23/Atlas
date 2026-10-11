# EssayCards — Review screen and navigation

Split out of `CLAUDE.md` (reference detail; load when working on this area).

## Review screen (`src/views/ReviewSessionView.tsx` / `src/components/ReviewStatsPanel.tsx`)
Material 3 layout, no page header: one flat `surface-variant` stats card, the
question card (`surface` + `elevation-1`, the dominant element), a full-width
primary **Flip** button (grade buttons replace it after flip), then a small
diagnostics frame. The stats card has two sections, their names (`CURRENT` /
`UPCOMING`) rotated vertically in a left gutter, no divider between them:
- **CURRENT** — three metric blocks: `Session` (reviews done this session,
  including a card that came back around), `Backlog` (cards due in the most
  recent `/due` refetch), `New` (`is_new` cards in that same queue).
- **UPCOMING** — a two-row × six-column forecast (`≤10m <1d <7d <30d <3mo ≥3mo`),
  horizontally scrollable on narrow widths. `All` = live `GET /stats` (the six
  forward bands, `due_now` omitted). `Session` = client-side tally: each review
  response gives `next_due_at − last_reviewed_at`, bucketed by the same band
  edges and counted per session (reset when the session starts, not on the
  per-grade refetch). No backend state; `FORECAST_COLUMNS` in `src/format.ts`
  mirrors the `/stats` band edges.

**Recency-selected bold frame.** The question card gets a **2 px primary
border** whenever the current card's `is_recent` is true — i.e. it was placed
ahead of the backlog because it was reviewed within the last 24 h (RECENT
category, sorted by `next_due_at`), not because of its interval. The
diagnostics frame under the buttons then shows either "↩ Failed earlier this
session — shown again" (the card's `flashcard_id` is in the session's
`againIds` set) or "◆ Selected by recency…", plus the current card's
`scheduled_interval_seconds` ("last interval" — the BACKLOG sort key) and the
new interval the previously-graded card landed on. `againIds` is a
diagnostics-only label; it has no effect on which card is shown.

**Refetch-on-grade (supersedes the Sprint05c relearning sub-queue).** The
session re-fetches `GET /flashcards/due` on mount, after **every** grade, and
from the completion screen's **Check again** button — never on a timer.
`ReviewSessionView` holds no `index` or client-side relearning queue; it always
renders `queue[0]` from the latest response. The card just graded is scheduled
at least 5 s (`again`) / 1 min (floored `hard`) into the future, so it is
absent from the immediate refetch and reappears only on a **later** refetch,
once it actually comes due, in the server's RECENT-first order. The session
ends when a refetch returns nothing due. One accepted gap: the very last card
graded `again` or floored `hard`, with nothing else to grade while its
interval elapses — **Check again** on the completion screen re-runs the fetch
for exactly that case.


## Button and nav consolidation (Sprint12)
Essay/section button rows are replaced by a reusable `ActionMenu` component
(`src/components/ActionMenu.tsx`) — a primary button plus an accessible dropdown
(`role=menu`/`menuitem`, Escape + click-outside to close, keyboard-operable).
Used at two sites:
- **Essay header** (`ReaderView`) — primary = Study (focus session on the
  whole essay, when it has cards) or Question overview (fallback, when it has
  none); secondary dropdown = Question overview (when not primary), Guided
  oral exam, Unguided oral exam (both gated on `status === 'complete'`),
  Export essay / Import, + New nugget (gated on `sections.length > 0`). The
  `← All essays` back button stays standalone, never folded into the menu.
- **Section end** (`ReaderView`) — primary = Review this section; secondary
  dropdown = Export section / Import, Insert section after / Import.
  `SectionExaminationHistory` is unaffected, sitting below the menu as before.

Every pre-existing action is preserved somewhere post-consolidation — none
silently dropped (see `Sprint12_FSRSAndUXOverhaul/10_architecture.json
§button_nav_inventory` for the complete pre -> post mapping).

**Category collapse** (`EssayListView`). Each category heading gets a
collapse/expand toggle (▸/▾ chevron, same glyph convention as
`SectionExaminationHistory`), persisted via `localStorage` key
`essaycards:categoryCollapsed:<category>` (`UNCATEGORIZED` for the
null-category group), defaulting expanded when no stored value exists. The
heading row (title, established/total, open count, the per-category Study
button) always stays visible; only the essay rows beneath it collapse/hide.

**Nav regrouping** (`src/shellConfig.ts`). `mobilePrimaryNav` trimmed to
Essays / Due for review / Stats (the everyday-learning + stats items).
Add / Update Essay moves to the new `secondaryMenu` (the Shell's existing
mobile "More" overlay). `desktopNav` keeps all four items (no group concept
in the Shell's current `AppConfig`/`NavItem` contract — R-CON-BP-06; desktop
"grouping" is order-only). The Experiment nav entry is removed entirely.
