# Create Chronos Skill

Invoked as `/create-chronos-skill <service-name>`.

Creates a new openclaw workspace skill for a Chronos-accessible Atlas service, following the quality standard established to minimise wasted API round-trips.

---

## Why this standard exists

Every openclaw skill has two parts that serve different purposes:

- **`description` (frontmatter)** — injected into the system prompt on every call as a one-line entry in the `<available_skills>` list. This is what the agent sees without reading anything. It must contain enough to route correctly and avoid guessing.
- **`SKILL.md` body** — loaded on demand when the agent needs to act. Contains full endpoint reference, examples, error handling.

If the description is missing the base URL, the agent will try to reconstruct it from compacted session memory and get it wrong — wasting 2-3 extra API calls per task.

---

## Step 0 — Gather inputs

Collect the following before writing anything. If not provided as arguments, read them from the existing service:

| Input | How to find it |
|---|---|
| `service_name` | Argument, e.g. `atlas-tasks` |
| `base_url_docker` | From the service's `compose.yml` → `container_name` + port. Pattern: `http://<container_name>:<port>/api` |
| `base_url_host` | From `compose.yml` port mapping or `.env`. Pattern: `http://localhost:<host_port>/api` |
| `what_it_does` | One sentence — what domain does it own? |
| `trigger_phrases` | 6-10 natural phrases a user might say to invoke it |
| `key_endpoints` | The 2-3 most common operations (for the Common Workflows section) |
| `do_not_use` | Any tools/CLIs the agent might mistakenly reach for instead |

Read `01_System/Makefile` and the service's `compose.yml` to derive base URLs if not supplied.

---

## Step 1 — Write the skill file

Create the file at:
```
/home/linse/Prod/Atlas/01_System/Chronos/workspace/skills/<service_name>/SKILL.md
```

### Frontmatter standard (non-negotiable)

The `description` field must contain all four of these elements:

1. **What it does** — one sentence covering the domain
2. **Trigger phrases** — natural language that routes to this skill
3. **Base URL** — exact Docker-internal URL with trailing slash note if relevant
4. **Read instruction** — `Read this SKILL.md before every <domain> operation — do not guess endpoints from memory.`

```yaml
---
name: <service_name>
description: >
  <What it does — one sentence>.
  Use when <trigger conditions>.
  Triggers on phrases like "<phrase 1>", "<phrase 2>", "<phrase 3>".
  Base URL: <base_url_docker> (no trailing slash).
  IMPORTANT: Read this SKILL.md before every <domain> operation — do not
  guess endpoints from memory. Do NOT use <do_not_use_tools> instead.
---
```

### Body standard

```markdown
# <Service Display Name>

<One sentence — what it does and what transport it uses.>

## Base URLs

\```
# Inside Docker on atlas-net (preferred):
<base_url_docker>

# From the host:
<base_url_host>
\```

---

## Endpoints

### <Most common operation>

\```
<METHOD> /api/<path>
\```

<Parameter table if applicable.>

Returns: <what it returns.>

---

[... remaining endpoints ...]

---

## Common Workflows

**<Most common task>:**
\```
<METHOD> /api/<path>
<body if POST/PATCH>
\```

[... 2-3 more workflows ...]

---

## Error Handling

All errors follow the Atlas ApiError envelope:

\```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "human readable",
    "request_id": "..."
  }
}
\```

| Code | Meaning |
|---|---|
| `NOT_FOUND` | Resource does not exist |
| `VALIDATION_ERROR` | Invalid field value |

---

## Notes

- No authentication required. Network-restricted to `atlas-net` inside Docker.
- Do NOT access the database directly — use the HTTP API only.
```

---

## Step 2 — Validate against the checklist

Before copying into the container, verify:

- [ ] `description` contains the base URL
- [ ] `description` contains "Read this SKILL.md before every ... operation"
- [ ] `description` contains at least 5 trigger phrases
- [ ] `description` contains what NOT to use (if applicable)
- [ ] Body has a `## Base URLs` section with both Docker and host URLs
- [ ] Body has at least one `## Common Workflows` example
- [ ] Body has an `## Error Handling` section

---

## Step 3 — Copy into the Chronos container

```bash
docker cp /home/linse/Prod/Atlas/01_System/Chronos/workspace/skills/<service_name>/SKILL.md \
  atlas-chronos:/home/node/.openclaw/workspace/skills/<service_name>/SKILL.md
```

Confirm the copy succeeded.

---

## Step 4 — Audit existing skills for gaps

After creating the new skill, check the other workspace skills for the same issues:

```bash
for skill in atlas-calendar atlas-notifications atlas-food-tracker atlas-tasks; do
  echo "=== $skill ==="
  docker exec atlas-chronos head -20 /home/node/.openclaw/workspace/skills/$skill/SKILL.md
done
```

For each skill whose `description` is missing the base URL or the read instruction, apply the same frontmatter fix and re-copy.

---

## Step 5 — Report

Print a short summary:
- Skill created: `<service_name>`
- Location: `...workspace/skills/<service_name>/SKILL.md`
- Checklist: all items passed / gaps (list any)
- Existing skills audited: list any that were also patched
