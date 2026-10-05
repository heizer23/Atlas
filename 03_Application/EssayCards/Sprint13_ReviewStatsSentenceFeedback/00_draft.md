# Sprint13 — Review, Stats & Sentence Feedback

## Goal

Improve the study experience in three areas:

1. simplify the **Review page**
2. redesign the **Stats page** around daily activity
3. add lightweight **sentence-level feedback** inside essays

The emphasis is on reducing UI clutter while making study progress easier to understand.

---

## 1. Review Page — Cleaner Header

### Remove redundant page labels

Remove the large body header:

- `Review`

Instead, show the current page in the top navigation/header where we currently have:

- `Atlas`
- `EssayCards`

For example:

`Atlas  EssayCards  Review`

The exact visual treatment can follow the existing navigation style.

---

## 2. Review Page — Daily Study Summary

Replace the current summary block.

### Remove

The following labels are no longer needed:

- Current
- Upcoming
- All
- Session

The summary should represent the **current day**, not the current study session.

### Main metrics

Show five figures:

**Recalls · Unique · First ‖ Due · New**

Definitions:

- **Recalls**
  Total card answers/reviews performed today.

- **Unique**
  Number of different cards seen today.

- **First**
  Number of cards seen for the first time ever today.

- **Due**
  Existing review cards currently due/backlogged.

- **New**
  New cards currently available but not yet introduced.

Keep the existing pattern of:

**large number**
small label underneath

Example:

`42        27        6        33        14`
`Recalls   Unique    First    Due       New`

The labels should stay compact enough to work cleanly on mobile.

---

## 3. Review Page — Interval Distribution

Keep the existing interval buckets such as:

- ≤10m
- <1d
- <7d
- <30d
- <3mo
- ≥3mo

However:

- remove the `All` row label
- remove the `Session` row
- show only the relevant current card population

The interval distribution should visually sit below the five main daily metrics and be secondary to them.

---

## 4. Essay Reader — Sentence Feedback

Add lightweight sentence-level interactions similar to the existing implementation in the Story app.

Each sentence should support two independent states.

### Hard to understand

Allow the user to mark a sentence as:

**Difficult / hard to understand**

Purpose:

- identify sentences that required extra effort
- make difficult wording discoverable later
- potentially use this as a reading-comprehension signal over time

The interaction should be very lightweight and should not interrupt reading.

### Thumbs up

Keep/add the existing:

**Thumbs up**

Purpose:

- mark sentences the user particularly likes
- preserve especially good explanations or phrasing

### Behaviour

A sentence may have:

- neither state
- difficult only
- thumbs up only
- both

The selected state must persist.

Reuse the Story app interaction pattern where practical rather than creating a completely new component.

---

## 5. Stats Page — Aggregate by Day

Change Study Activity from **session-based** to **day-based** aggregation.

Each day should be represented once, regardless of how many separate review sessions happened that day.

---

## 6. Stats Page — Daily Study Activity Chart

Replace the current Study Activity visualization with a **stacked bar chart by day**.

The total height of each bar represents:

**Recalls**

The bar is split into three mutually exclusive parts.

### Repeat

Cards beyond their first occurrence within that day.

Formula:

`Repeat = Recalls - Unique`

### Unique

Unique cards seen that day, excluding cards being seen for the first time ever.

Formula:

`Unique segment = Unique Cards Seen - First Cards Seen`

### First

Cards seen for the first time ever.

Formula:

`First = First Cards Seen`

### Example

If a day contains:

- 20 Recalls
- 12 Unique Cards Seen
- 2 First Cards Seen

the stacked bar must contain:

- Repeat = 8
- Unique = 10
- First = 2

Total:

`8 + 10 + 2 = 20 Recalls`

The legend should therefore read:

**Repeat · Unique · First**

---

## 7. Stats Page — Recall Rate

Show the **daily recall rate above each stacked bar**.

Example:

`87%`

displayed directly above that day's bar.

Recall rate should be based on the same day's review answers.

This allows the chart to show both:

- volume/composition of study activity
- quality of recall

without requiring a second chart.

---

## 8. Stats Page — Observed Recall

Update the **Observed Recall** section.

It should show:

- **Cards Seen**
- **Unique Cards Seen**
- **New Cards Seen**
- **Recall Rate**

These values should use the time range currently selected on the Stats page.

For consistency:

- `Cards Seen` corresponds to total recalls
- `Unique Cards Seen` counts distinct cards
- `New Cards Seen` counts cards whose first-ever review occurred in the selected period

For the compact Review-page terminology, `New Cards Seen` is shown as **First**.

---

## 9. Terminology

Use these terms consistently.

### Review page

- Recalls
- Unique
- First
- Due
- New

### Study Activity chart

- Repeat
- Unique
- First

### Detailed statistics

Use the longer labels where space allows:

- Cards Seen
- Unique Cards Seen
- New Cards Seen
- Recall Rate

This intentionally distinguishes:

**First**
cards actually encountered for the first time

from

**New**
cards still waiting to be introduced.

---

## 10. Acceptance Criteria

The sprint is complete when:

- Review no longer has a separate large page heading.
- Review statistics are based on the current day rather than the current session.
- Review displays Recalls, Unique, First, Due and New.
- Current / Upcoming / All / Session labels are removed.
- Essay sentences can independently be marked difficult and thumbs-up.
- Sentence feedback persists after reload.
- Stats aggregate study activity by calendar day.
- Study Activity uses stacked Repeat / Unique / First bars.
- Each bar adds up exactly to total Recalls for that day.
- Daily recall rate appears above each bar.
- Observed Recall displays Cards Seen, Unique Cards Seen, New Cards Seen and Recall Rate.
- Existing review scheduling and card-selection logic remain unchanged.
