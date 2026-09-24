---
name: project_storyreader_sprint01
description: StoryReader Sprint01_Core — new mobile markdown reader with tap-to-save passage reactions; TESTS_PASSING after one design correction cycle; Codex-CLI ingestion pattern reused from EssayCards
metadata:
  type: project
---

StoryReader (03_Application) Sprint01_Core built end to end via the standard chain
(no fast path — new persistent tables + new API surface disqualified it under
R-PRO-BP-01 §11). Reached `TESTS_PASSING`; awaiting human `/sprint-close`.

**Why this sprint is a useful reference for future similar sprints:**

- The draft explicitly left 4 open design questions (paragraph-split algorithm,
  context-window bound, slug-vs-story_id endpoint convenience, content-mount env var)
  and the designer resolved all 4 concretely rather than punting — reviewer verified
  each was actually resolved, not just mentioned. Good template for how "Open Design
  Questions" sections should be closed out.
- **Rename-placeholder deferral pattern**: the draft said the component name
  (`StoryReader`) could be renamed "if a better name comes to mind." The designer
  agent has no file-move/delete tool, so it correctly declined to attempt a partial
  rename (which would've left an orphaned duplicate draft at the old path) and instead
  flagged the rename as a human-actionable follow-up in `10_architecture.json`'s
  `naming_note`. The reviewer correctly treated this as an acceptable deferral, not a
  defect, since the draft never *required* a rename. Orchestrator should recognize
  this pattern: an agent declining a filesystem move it can't safely complete, and
  documenting it instead, is correct behavior, not a gap to route back for.
- One correction cycle: reviewer round 1 caught (a) a missing instruction to wire the
  new app's shellConfig import into `02_Platform/Atlas_Shell/src/shell/main.tsx`
  (design had correctly flagged the analogous `nginx.conf` edit as a risk but missed
  the structurally identical main.tsx one — worth checking for on any new-app sprint:
  both edits are always needed together), and (b) a Dataset row shape missing the
  required `id` field on one GET endpoint (R-CON-BP-04). Corrector fixed both in one
  pass; round-2 review APPROVED with independent re-verification against live
  artifacts (not just trusting the corrections file).
- Test runner independently rebuilt the `-test` container from scratch rather than
  trusting the implementer's "40 tests passing" self-report — found it still true, but
  also surfaced a real process gap: `01_System/test/compose.test.yml` (the central test
  compose file) has no `storyreader-test` entry, unlike every other component. Worked
  around via the component-local `compose.yml`. This central-registration gap should be
  fixed by a human at some point — flagging here so it isn't lost, and so a future
  orchestrator run isn't surprised if the standard
  `docker compose -f 01_System/test/compose.test.yml ... up -d storyreader-test --build`
  invocation fails for this component specifically.
- Reused EssayCards' CLI-ingestion-by-Codex-over-SSH pattern (`python -m backend.ingest`,
  hash-based idempotency, no upload endpoint) and its R-CON-BP-04-exempt bespoke export
  endpoint pattern (`.../annotations/export`) — same rationale as EssayCards'
  `exploration-package`/`examination-package`.
- Port 8026 (next free after StorageTracker 8022 / Calendar 8023 / EssayCards 8024 /
  ClaudeConsole 8025).
