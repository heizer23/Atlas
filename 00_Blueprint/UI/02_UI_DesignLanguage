# 01.UI.DesignLanguage
> **Status:** Foundational — changes deliberately and explicitly, never during feature work.  
> **Audience:** LLMs doing UI work, human reviewing visual decisions.  
> **Relationship:** Defines the visual rules that `UI_Implementation` enforces in code and `UI_Contract` is styled against.

---

## 1. Design Language Choice

Atlas uses **Material Design 3 (M3)** as its design language foundation.

**Why M3:**
- Stable, named token system (`--md-sys-color-*`, typescale roles, elevation levels) gives LLMs reliable semantic anchors across sessions.
- Designed around components-as-configurations — aligns with Atlas's "reuse over customization" principle.
- Token architecture separates *role* from *value*: `color-primary` carries meaning independent of hex, making future theme changes a token swap, not a rewrite.
- Sufficiently documented that any LLM can reason about it without this document alone.

**What M3 is not used for:**
- Navigation Drawer or FAB clusters.
- Touch-optimized interaction models (long-press, swipe-to-dismiss).
- Consumer app aesthetics (large hero images, rounded display type).

Atlas uses M3 as a **token and component discipline**. Bottom Navigation is permitted for mobile viewports (see §2 and §10).

---

## 2. Deviations from Stock M3

> Per Architectural Rule 9: deviations must be explicit.

| Area | Stock M3 | Atlas deviation | Reason |
|---|---|---|---|
| Type scale | Includes Display, Headline, Title, Body, Label with many sub-levels | Atlas uses exactly 5 named levels (see §4) | Reduces LLM decision surface |
| Motion | Emphasizes expressive spring animations | Subtle, fast transitions only (150–250ms ease) | Data tool; animation should not distract |
| Elevation | 5 tonal elevation levels with surface tint | 3 levels only (see §5) | Keeps visual hierarchy legible at data density |
| Navigation | Navigation Bar / Drawer as primary patterns | Left sidebar (desktop/tablet) + M3 Bottom Navigation Bar (mobile, max 5 items) | Desktop-first sidebar; Bottom Navigation permitted on mobile viewports |
| FAB | Prominent action surface | Not used in Atlas | Actions live in Top Bar or inline in tables |
| Color surface tint | M3 tints surfaces with primary color at each elevation | Atlas uses neutral surface tints only | Avoids color bleed on data-dense pages |

---

## 3. Color System

Atlas defines a **single light theme**. Dark mode is out of scope until explicitly added.

### Token Mapping

Atlas uses a restricted subset of M3 color tokens. Only these tokens are used in components. Never use hex values directly in component code — always reference a token.

| Token | Role | Atlas hex | Usage |
|---|---|---|---|
| `--md-sys-color-primary` | Brand, key actions, active states | `#4A6FA5` | Primary buttons, active nav, links |
| `--md-sys-color-on-primary` | Text/icon on primary | `#FFFFFF` | Labels on filled primary elements |
| `--md-sys-color-primary-container` | Subtle primary backgrounds | `#D8E4F5` | Chips, selected states, highlights |
| `--md-sys-color-on-primary-container` | Text on primary container | `#0C2545` | Text inside primary-container surfaces |
| `--md-sys-color-secondary` | Supporting actions, less emphasis | `#5C6F85` | Secondary buttons, metadata labels |
| `--md-sys-color-secondary-container` | Subtle secondary backgrounds | `#DCE8F5` | Segmented button active state |
| `--md-sys-color-tertiary` | Accent, complementary highlights | `#6B5778` | Badges, tags, accent indicators |
| `--md-sys-color-tertiary-container` | Subtle tertiary backgrounds | `#EEDDF5` | Metric tiles, status chips |
| `--md-sys-color-error` | Destructive actions, validation errors | `#BA1A1A` | Delete actions, error states |
| `--md-sys-color-error-container` | Error background | `#FFDAD6` | Error card backgrounds |
| `--md-sys-color-surface` | Default card/panel background | `#F8FAFE` | Cards, dialogs, sheets |
| `--md-sys-color-surface-variant` | Alternate surface | `#DFE5EF` | Table header rows, input backgrounds |
| `--md-sys-color-background` | Page background | `#EEF2F7` | Body background only |
| `--md-sys-color-on-surface` | Primary text | `#191C20` | Body text, headings |
| `--md-sys-color-on-surface-variant` | Secondary text, metadata | `#43474E` | Table cell secondary text, labels |
| `--md-sys-color-outline` | Strong borders | `#73787F` | Input borders, dividers with emphasis |
| `--md-sys-color-outline-variant` | Subtle borders | `#C3C7CF` | Table row dividers, card borders |

### Chart Color Palette

Charts use a dedicated sequence, separate from the UI token system. Always assign colors in order.

| Index | Hex | Usage |
|---|---|---|
| `--atlas-chart-1` | `#4A6FA5` | Primary series (bars, first line) |
| `--atlas-chart-2` | `#6B9AC4` | Second series |
| `--atlas-chart-3` | `#9EC5E8` | Third series |
| `--atlas-chart-4` | `#C5DFF5` | Fourth series |
| `--atlas-chart-line-1` | `#D04B3A` | First line overlay (ComboChart) |
| `--atlas-chart-line-2` | `#E8956B` | Second line overlay |

Chart colors are **not** M3 tokens — they are Atlas-specific and live separately. Never use `--md-sys-color-*` tokens inside chart elements.

---

## 4. Typography

Atlas uses **Google Sans** as its sole typeface family. This is M3's reference typeface and is well-known to LLMs.

- `Google Sans` — body, labels, UI chrome
- `Google Sans Display` — large headings, metric values, page titles

### Type Scale (5 levels only)

| Level | Font | Size | Weight | Line height | Usage |
|---|---|---|---|---|---|
| `display` | Google Sans Display | 28px | 400 | 1.2 | Page titles, large metric values |
| `headline` | Google Sans Display | 22px | 400 | 1.3 | Card titles, section headings |
| `title` | Google Sans | 16px | 500 | 1.4 | Table column headers, dialog titles |
| `body` | Google Sans | 14px | 400 | 1.5 | Table cell content, form labels, descriptions |
| `label` | Google Sans | 12px | 500 | 1.4 | Chips, badges, axis tick labels, metadata |

No other sizes are used. If a size is needed that doesn't fit these levels, use the closest level and note the decision.

---

## 5. Elevation

Atlas uses 3 elevation levels. M3's tonal surface tint is **not applied** — elevation is communicated by shadow only.

| Level | Shadow | Usage |
|---|---|---|
| `0` | none | Page background elements, table rows |
| `1` | `0 1px 3px rgba(25,28,32,.08), 0 4px 12px rgba(25,28,32,.08)` | Cards, panels, table containers |
| `2` | `0 2px 6px rgba(25,28,32,.12), 0 8px 24px rgba(25,28,32,.10)` | Dialogs, dropdowns, tooltips |

Never use `z-index` stacking as a substitute for elevation communication.

---

## 6. Shape (Border Radius)

| Context | Radius | Usage |
|---|---|---|
| Cards, panels | `12px` | All card surfaces |
| Buttons (filled, outlined) | `20px` | Standard button shape |
| Segmented buttons, chips | `20px` | Pill shape |
| Dialogs, bottom sheets | `28px` | M3 dialog shape |
| Tooltips | `10px` | Compact info surfaces |
| Table rows | `0` | No rounding on table rows |
| Input fields | `8px` | Form inputs, search |

---

## 7. Spacing

Atlas uses a **4px base grid**. All spacing values are multiples of 4.

| Token | Value | Usage |
|---|---|---|
| `--space-xs` | `4px` | Icon padding, tight internal gaps |
| `--space-sm` | `8px` | Chip padding, compact list items |
| `--space-md` | `16px` | Card internal padding, form field gaps |
| `--space-lg` | `24px` | Section gaps, dialog padding |
| `--space-xl` | `32px` | Page section separation |

Page outer padding: `24px` on desktop, `16px` on mobile.

---

## 8. Interaction States

Every interactive element must have all applicable states. Never omit hover or focus.

| State | Implementation |
|---|---|
| Hover | Background shifts to `surface-variant` at 60% opacity, or element darkens by 8% |
| Focus | `2px` outline in `--md-sys-color-primary`, `2px` offset |
| Active / Pressed | Background darkens by 12% |
| Disabled | Opacity `38%`, no pointer events |
| Selected | `primary-container` background, `on-primary-container` text |
| Loading | Skeleton pulse animation (see §9) |

Ripple effects from stock M3 are **not implemented** — hover background shifts are used instead. This is a deliberate web-first deviation.

---

## 9. Motion

Transitions are **functional, not expressive**. They communicate state change, not delight.

| Context | Duration | Easing | Usage |
|---|---|---|---|
| State transitions (hover, focus) | `150ms` | `ease` | Color/background shifts |
| Component enter (cards, panels) | `250ms` | `cubic-bezier(0.2, 0, 0, 1)` | Fade + translateY(8px) → 0 |
| Overlay appear (dialogs, tooltips) | `200ms` | `ease-out` | Opacity 0 → 1 |
| Skeleton pulse | `1.5s` | `ease-in-out`, infinite | Loading placeholders |

No spring animations. No bounce. No choreographed sequences across multiple elements.

---

## 10. Component Usage Map

Maps Atlas UI primitives to their M3 component counterparts. Use these mappings — do not reach for other M3 components.

| Atlas primitive | M3 component basis | Key deviations |
|---|---|---|
| `TableView` | Data Table | Header uses `surface-variant`; row hover uses subtle bg shift |
| `DetailView` | List (two-line) inside a Card | Read-only; no list item actions |
| `BarChart` / `LineChart` / `ComboChart` | No M3 equivalent | Uses Atlas chart palette; axis labels use `label` typescale |
| `ErrorCard` | Filled Card + Error color | Icon + message + collapsible detail |
| `WarningPlaceholder` | Outlined Card + Tertiary color | Always visible; never dismissible |
| Top App Bar | Top App Bar (Medium) | No subtitle line; title uses `headline` scale |
| Page navigation (desktop/tablet) | Navigation Rail | Left-aligned; icons + labels; no FAB slot |
| Page navigation (mobile) | Navigation Bar (Bottom Navigation) | Fixed bottom; max 5 items; icons + labels; active item uses `primary-container` indicator pill |
| Buttons (primary) | Filled Button | Standard M3; `primary` color |
| Buttons (secondary) | Outlined Button | Standard M3; `outline` border |
| Buttons (destructive) | Filled Button | `error` color; always requires confirmation dialog |
| Segmented buttons | Segmented Button | Standard M3; used for view mode switching |
| Chips (filter) | Filter Chip | Standard M3; `primary-container` when selected |
| Dialogs | Basic Dialog | `28px` radius; destructive confirm only |
| Tooltips | Plain Tooltip | `10px` radius; `on-surface` background |
| Skeleton / loading | No M3 equivalent | Animated gradient sweep on `surface-variant` |

## 11. Versioning

This document changes when a **deliberate visual direction decision** is made. It does not change during feature development.

Change process:
1. Identify the decision (new token needed, deviation from M3, new component mapping).
2. Propose the change explicitly — do not implement it silently.
3. Update this document first, then update `UI_Implementation` to reflect it.
4. Record the reason in the change.

Any LLM session that produces UI code inconsistent with this document has made an undeclared deviation. That deviation must either be ratified here or reverted.
