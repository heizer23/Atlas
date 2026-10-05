---
name: EssayCards Sprint14 SectionProgressionAndRevalidation review
description: First-round review (2026-10-05) APPROVED_WITH_CHANGES; what was verified and what recurring checks proved useful
type: project
---
Sprint14 (section traffic lights, 70% oral pass, unlock, cascade, revalidation): design was strong; one Major (revalidation grade control left "either way"), rest minor.

Verified by grep against real source: removed Sprint12 fields (`learning_level`, `milestone_*`) are consumed only by ShellEntry.tsx, essays.py, tests, CLAUDE.md. `EssayDetailRow extends EssayRow` so a prop typed EssayRow accepts the detail row.

Techniques worth repeating:
- When a design adds a NOT NULL column without a default, grep tests/fixtures.sql for existing inserts into that table (3 section_examinations inserts would have broken).
- Canonical schema.sql wraps everything in begin/commit; a design `10_schema.sql` with its own begin/commit nests when folded in.
- Compare each endpoint's `purpose` sentence against its `boundary_construction` (stats purpose said "matches focus session" but kept flagged cards).
- Check design header comments vs backfill SQL for historical-verdict semantics.

**Why:** product-owned open_questions were all pre-flagged by the designer with sensible defaults; reviewer treated them as Open Uncertainties, not blockers.
**How to apply:** when a designer pre-flags draft deviations, verify the arithmetic/grep claims rather than re-litigating product intent.
