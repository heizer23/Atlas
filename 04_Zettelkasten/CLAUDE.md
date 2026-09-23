# CLAUDE.md

## Purpose
This folder is a personal knowledge Zettelkasten built through conversations between the user and Claude — philosophy, history, art, religion, and science. It is not a software component. It is an explicit, deliberate exception to Atlas's four-layer architecture (see root `CLAUDE.md`), requested by the user.

The primary reader of these notes is Claude, not the user. The point is for Claude to hold an accurate, current model of what the user already understands about a given idea, thinker, or connection, and to use that model to guide future discussion — e.g. "we covered Simmel's status dynamics; connect that to Bourdieu and see if the distinction lands."

## Structure

Flat directory, no domain subfolders. Cross-disciplinary ideas (Machiavelli: philosophy, history, political theory) don't fit one bucket — forcing a folder choice recreates the exact problem a Zettelkasten exists to avoid. Domain membership is expressed with `tags` in frontmatter instead; a note can carry multiple tags.

- One atomic note per idea, thinker, or connection — small file, kebab-case filename matching the frontmatter `name`.
- `INDEX.md` — master overview, grouped by tag. Read this first when a philosophy/history/art/religion/science discussion starts or resumes; it's the fast path to "what do we already know."

## Note format

```markdown
---
name: {{kebab-case-slug}}
tags: [{{domain-tags}}]
---

{{What the idea is, in brief. What the user currently understands about it —
their framing, the examples that clicked, the parts that are still shaky.
Open threads: unresolved questions or connections not yet made. Link related
notes inline with [[name]].}}
```

Keep notes compact — a state-of-understanding snapshot, not an essay. If a note changes materially in a later conversation (the user's grasp deepens, corrects itself, or connects further), update it in place rather than creating a near-duplicate.

## When to write

Save a note whenever the user makes a genuinely interesting connection or clearly learns/masters something new in one of these domains — proactively, without asking permission each time. Skip small talk or passing mentions; this isn't a transcript. Update `INDEX.md` in the same pass so it never drifts out of sync with the notes it points to.

## Git

No auto-commit. Create/edit files as normal; the user commits periodically on their own schedule.
