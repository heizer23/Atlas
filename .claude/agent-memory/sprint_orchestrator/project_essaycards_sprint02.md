---
name: project_essaycards_sprint02
description: EssayCards Sprint02_JsonIngestion — POST /essays/ingest + shared upsert refactor + upload UI; TESTS_PASSING; zero correction/fix loops, fully automated single-pass through the whole state machine
metadata:
  type: project
---

Sprint02_JsonIngestion added a JSON HTTP ingestion path (`POST /api/essaycards/essays/ingest`)
alongside Sprint01_Core's existing markdown-CLI ingestion, sharing one upsert core. Ran end to
end with zero human checkpoints per explicit instruction (only "big problem" conditions —
BLOCKED/REJECTED verdict, 2+ correction rounds, TESTS_FAILED_DESIGN_ISSUE, fix_iterations=3 —
would have stopped it early). None triggered; every stage passed on the first attempt:
DRAFT_READY → DESIGN_CREATED (1 pass) → DESIGN_APPROVED (round-1 APPROVED, no corrections) →
IMPLEMENTATION_IN_PROGRESS (1 pass) → TESTS_PASSING (46/46, fix_iterations stayed 0).

**Why this is a useful reference pattern:** it shows the loop can run fully unattended when the
draft is precise and pre-loaded with the exact constraints that would otherwise cause a
correction cycle. The draft explicitly named two hard constraints up front (no Pydantic body
model — same R-CON-BP-04/ApiError-bypass gap Sprint01 found and fixed; and a byte-for-byte
behavior-preserving upsert-core refactor with Sprint01's 36 tests as the regression gate) and
told the design agent to honor them. Both design and review treated them as first-class checks
rather than discovering them cold, and the reviewer verified them concretely (read the actual
`backend/ingest.py` and `tests/test_ingest.py` to confirm the refactor couldn't break existing
assertions, not just trusted the architecture doc's claim).

**Notable finding surfaced during design, not implementation:** the draft's "essay list/picker"
scope item was already built in Sprint01's `ShellEntry.tsx` (`EssayListView` at `/essaycards`).
The designer caught this by reading actual Sprint01 code rather than only Sprint01's design
artifacts, and explicitly scoped the new scaffolding to NOT duplicate it. Worth remembering:
designers building on a prior sprint should read the real implemented code, not just that
sprint's `10_*.json`, since implementation may have diverged from or extended the original design
(Sprint01 wasn't `/sprint-close`d yet either, so there was no `00_architecture/` baseline to seed
from — the design agent used Sprint01_Core's own final `10_*.json` plus the live code instead).

**How to apply:** when a draft pre-resolves known recurring gaps (like the Pydantic/ApiError
pattern — see [[project_essaycards_sprint01]]) and cites the specific prior sprint file as
precedent, pass that context explicitly into the design-agent launch prompt. It measurably
reduces correction loops. Also: when orchestrating "drive it end-to-end, only stop on big
problems," still write real per-agent Activity Report content into the log rather than
compressing to "see agent output" — this run's log entries stayed fully detailed even at zero
checkpoints.

Final state: `TESTS_PASSING`. 3 `[UI — manual]` scenarios (upload form success/failure states,
essay list navigation) need human eyeballing before `/sprint-close`, per this component's
established Sprint01 pattern. `/sprint-close` intentionally not invoked — stays a separate human
gate per explicit instruction for this run.
