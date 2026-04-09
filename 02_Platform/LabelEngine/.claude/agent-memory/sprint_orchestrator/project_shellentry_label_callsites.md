---
name: ShellEntry label call site count
description: ShellEntry.tsx has four label search call sites consuming { labels: T[] }, not three — TaskCreatePanel is easily missed
type: project
---

As of Sprint06 (2026-04-09), ShellEntry.tsx contains four call sites that cast apiFetch results as `{ labels: LabelRecord[] }`:

1. LabelPanel.handleQueryChange (~line 435)
2. TaskEditPanel.handleLabelQueryChange (~line 732)
3. TaskEditPanel useEffect for get_task_labels (~line 893)
4. TaskCreatePanel.handleLabelQueryChange (~line 1102)

**Why:** The draft.md and initial design only mentioned "three call sites (~435, ~732, ~893)". The TaskCreatePanel instance at ~1102 was identified during review and required a design correction before implementation.

**How to apply:** When any sprint touches ShellEntry.tsx label call sites, grep for all instances of `{ labels:` or `res\.labels` before finalizing the design — do not rely on line-number hints from draft documents alone.
