# Agent Rule Conflicts

Log of cases where an agent's own instructions (system prompt, skill instructions, or an older local sprint convention) conflicted with a canonical rule document, and how the conflict was resolved.

**Governed by:** R-PRO-BP-01 (`.claude/rules/R-PRO-BP.md`) — "When agent instructions, skill instructions, or older local sprint conventions conflict with this document, this document wins. The agent must follow this document and record the conflict in `00_Blueprint/Quality/agent_rule_conflicts.md`."

---

## Entries

---

### 2026-09-26 — sprint_design_reviewer immediate-artifact template vs. R-PRO-BP-02

**Component / Sprint:** EssayCards / Sprint11_ReviewStats

**Conflict:** The `sprint_design_reviewer` agent's own system-prompt instructions mandate a detailed, multi-section immediate-artifact template for `1N_design_review.md` (`Verdict` / `Confirmed Problems` / `Recommended Improvements` / `Scaffold-Only Observations` / `Hard Rule Violations` / `Open Uncertainties` / `Minimal Change Set` / `Approval Condition`, with a required `Likely Cause (Design Phase)` field per Critical/Major finding). `R-PRO-BP-02` (`.claude/rules/R-PRO-BP.md`) defines a different, shorter "strong convention" structure for the same artifact type (`Verdict`/`Date`/`Reviewer` header, `Blocking Issues` table, `Non-Blocking Issues` table, `Approval Condition`), explicitly stating "This document is authoritative for the current run. It must not become a theory paper."

**Resolution:** Per R-PRO-BP-01's canonical-document precedence and the task's explicit instruction to follow the R-PRO-BP-02 structure, `Sprint11_ReviewStats/11_design_review.md` was written using the R-PRO-BP-02 Blocking/Non-Blocking/Approval-Condition structure, not the agent's own default template. No content was lost — severity classification and per-item location/rationale are preserved inside the table rows.

**Recommended follow-up:** Reconcile the `sprint_design_reviewer` agent's system-prompt template with R-PRO-BP-02 so this conflict does not recur on every design review.

---

### 2026-10-11 — Agent instructions reference non-existent rule files

**Component / Sprint:** n/a (found by `Rule_Audit_2026-10-11.md`, T5)

**Conflict:** `sprint_design_reviewer`, `sprint_design_application`, `sprint_design_platform`, and `sprint_implement` told agents to load `architecture_as_ai_interface.md`, `contracts_and_boundaries.md`, `no_hidden_state.md`, `dependency_direction.md`, `surface_violations.md`, `platform_boundary.md`. None exist; the rules live in `.claude/rules/R-*.md`.

**Resolution:** Agents now cite `.claude/rules/R-CON-BP.md`, `R-CON-AL.md`, `R-CON-PL.md`, `R-OPS-BP.md`, `R-PRO-BP.md` by rule ID. Resolved 2026-10-11 (design reviewer also moved to the R-PRO-BP-02 artifact structure, closing the 2026-09-26 conflict above).

---

### 2026-10-11 — sprint_implement_reviewer vs. R-PRO-BP-01 §1/§6

**Component / Sprint:** EssayCards / Sprint10, Sprint12 (implementation reviews)

**Conflict:** R-PRO-BP-01 §1 states "No implementation review file" and §6 makes `/sprint-close` the only gate. The `sprint_implement_reviewer` agent and two post-TESTS_PASSING implementation reviews (`00_Blueprint/Quality/EssayCards/Sprint10_…`, `Sprint12_…`) continued to exist; both were APPROVED with zero blocking issues.

**Resolution:** `sprint_implement_reviewer` retired (agent file deleted) 2026-10-11. On-demand code review is covered by `atlas_code_reviewer`, which writes outside the sprint folder.

---

### 2026-10-11 — Orchestrator edited a test file vs. R-PRO-BP-01 §7

**Component / Sprint:** Notifications / Sprint01

**Conflict:** R-PRO-BP-01 §7 limits the orchestrator to creating/updating `99_sprint_log.md`. The Notifications Sprint01 log records an `[orchestrator-inline]` test-file fix.

**Resolution:** Single incident; no change made. Watch for recurrence. Logged for traceability (R-OPS-BP-01).

