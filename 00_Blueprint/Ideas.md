# Ideas

Unstructured ideas for future work. Not committed to, not scheduled — just worth remembering.

---

## Chronos: Context-Aware Bootstrap Injection

**Problem:** `MEMORY.md` (and other bootstrap files) are injected into every call regardless of query type. A simple calendar entry doesn't need personal context; a "what do I have this week?" query does.

**Idea:** Use openclaw's `agent:bootstrap` hook to build a lightweight classifier that inspects the incoming message before finalising the system prompt, and conditionally includes `MEMORY.md` based on query intent.

- Low-personal-context queries (add event, set reminder, quick lookup) → skip `MEMORY.md`
- High-personal-context queries (planning, summaries, advice, anything involving people) → include it

**Why it matters:** `MEMORY.md` is injected on every turn and will grow over time. Skipping it on transactional queries reduces per-call token cost and avoids leaking personal context into calls that don't need it.

**Rough approach:**
- Small openclaw plugin registered on the `agent:bootstrap` hook
- Simple intent heuristic or a fast/cheap model call to classify the message
- Mutate the bootstrap file list before injection

**Reference:** openclaw docs — `agent:bootstrap` hook, `agents.defaults.bootstrapFiles` override.
