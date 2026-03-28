---
name: Sprint 03 Design Correction Patterns
description: Patterns observed during Sprint 03 design correction round — cross-module import violations, product-decision escalation, Option A resolution
type: project
---

Sprint 03 had a CHANGES_REQUIRED design review with three Confirmed Problems resolved in one correction round.

**Pattern 1 — Private function cross-module import:**
The designer instructed the implementer to import a private function (`_validate_and_normalise`) across module boundaries. This violates Atlas Rule 03 (contracts_and_boundaries). The correct fix is either (a) promote to public or (b) extract to shared module. In Sprint 03, the product decision made this moot — Option A removed the need for the import entirely.

**Why:** Rule 03 requires not blurring public vs private structures. A private function imported by another module becomes a de facto public interface without a declared contract.

**How to apply:** When reviewing design artifacts, check `private_objects` declarations in scaffolding.json against any cross-module import instructions in the same scaffolding or in architecture.json deferrals.

---

**Pattern 2 — Prose-only response contract:**
The designer declared a named response shape (`entry_detail`) only in `purpose` field prose, not as an explicit stable contract artifact. This violates Rule 03 (explicit public interfaces). Fix: add a `contracts.named_contracts` section to architecture.json with field names, types, serialisation rules, and version. Reference it from scaffolding.json TypeScript types and from `interfaces.exposed_surfaces` via `response_contract_ref`.

**How to apply:** When reviewing architecture.json exposed_surfaces, any `ui_contract` field that describes a custom (non-Dataset, non-ApiError) response shape must have a corresponding named contract declaration, not just prose.

---

**Pattern 3 — Product decision surfaced as technical detail:**
The designer resolved "items reconstruction" (a round-trip data loss issue) as "acceptable limitation" rather than surfacing it as a product question. Design reviewers should escalate any decision that changes the semantics of what a user action means (e.g., "editing a meal") to a human-owner open question.

**How to apply:** When a scaffolding `purpose` field contains phrases like "known limitation", "acceptable for this slice", or makes a tradeoff that affects data integrity or UX semantics, escalate to Confirmed Problem with human owner.

---

**Pattern 4 — Human decision as Option A/B:**
Sprint 03 human product decision was given as "Option A" with two-sentence description. This is sufficient to unblock. The design-corrector created a new named contract (`EntryEditRequest`) for the chosen option and recorded the decision in `open_questions` with status RESOLVED and date.

**How to apply:** When a human product decision resolves a design open question, the corrector must:
1. Add or update a named contract in architecture.json for the chosen shape
2. Update open_questions with status RESOLVED, resolution text, and date
3. Propagate the decision through invariants, internal_flow, deferrals, and scaffolding

---

**Pattern 5 — Correction round that eliminates the original violation:**
Option A removed the need for the `_validate_and_normalise` cross-module import entirely. The correction was simpler than either of the two originally proposed fixes (promote to public, or extract to shared module). When a product decision supersedes a technical violation, the corrector should note this explicitly in design_corrections.md.
