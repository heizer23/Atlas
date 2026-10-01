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
