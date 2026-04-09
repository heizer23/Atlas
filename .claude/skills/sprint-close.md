# Sprint Close Skill

Invoked as `/sprint-close [sprint_folder_path]`.

This skill closes a sprint, restarts the affected service, updates canonical architecture snapshots, and regenerates the system map. It is the human gate — invoking it is the approval.

---

## Step 0 — Identify the sprint

If a path argument was provided, use it as the sprint folder.
Otherwise, identify the most recently active sprint folder from the current conversation context.

Read `<sprint_folder>/99_sprint_log.md`. Parse the JSON state block to extract:
- `sprint_name`
- `component_name`
- `layer` (`02_Platform` or `03_Application`)
- `current_state`

**Abort if `current_state` is not `IMPLEMENTATION_IN_PROGRESS`.** State the current state and what must happen first.

Derive `component_root` from `layer` and `component_name`:
- `02_Platform/<component_name>`
- `03_Application/<component_name>`

---

## Step 1 — Copy architecture files to `00_architecture/`

Create or overwrite `<component_root>/00_architecture/` with the latest design artifacts from the sprint:

| Source (sprint folder) | Destination |
|---|---|
| `10_architecture.json` | `<component_root>/00_architecture/architecture.json` |
| `10_scaffolding.json` | `<component_root>/00_architecture/scaffolding.json` |
| `10_schema.sql` | `<component_root>/00_architecture/schema.sql` _(only if present)_ |

This folder is the canonical current-architecture snapshot. Agents that need to understand the component without walking sprint history read from here.

---

## Step 2 — Update Makefile (new components only)

Check the Makefile at `01_System/Makefile` for an existing entry referencing `component_root`.

**If an entry already exists:** no Makefile changes needed — skip to Step 3.

**If this is a new component:** add a region block following the established pattern. Derive the Make target prefix as follows:
- Take `component_name`, lowercase it, strip `Tracker`/`Engine`/`Connector`/`Series`/`Gateway` suffixes, use the result as the prefix (e.g. `LabelEngine` → `label`, `TaskTracker` → `task`, `CalendarConnector` → `calendar`).
- If the derived prefix conflicts with an existing target, use the full snake_case lowercase name.

Add this block at the appropriate layer position (Platform before Application):

```makefile
# region --- [Layer]: <component_name>
<PREFIX>_DIR=../<layer>/<component_name>

<PREFIX>_COMPOSE=docker compose \
	-f $(<PREFIX>_DIR)/compose.yml \
	$(ENV_FILES)

<prefix>-build:
	$(<PREFIX>_COMPOSE) build

<prefix>-up:
	$(<PREFIX>_COMPOSE) up -d

<prefix>-down:
	$(<PREFIX>_COMPOSE) down

<prefix>-logs:
	$(<PREFIX>_COMPOSE) logs -f

<prefix>-reboot:
	$(<PREFIX>_COMPOSE) down
	$(<PREFIX>_COMPOSE) up -d
```

If the component owns persistent state (`10_schema.sql` exists), also add:

```makefile
<prefix>-schema:
	@test -n "$(ATLAS_PG_USER)" || (echo "ATLAS_PG_USER missing" && exit 1)
	@test -n "$(ATLAS_PG_DB)"   || (echo "ATLAS_PG_DB missing" && exit 1)
	$(PG_COMPOSE) exec -T postgres psql -v ON_ERROR_STOP=1 -U $(ATLAS_PG_USER) -d $(ATLAS_PG_DB) < $(<PREFIX>_DIR)/00_architecture/schema.sql

# endregion
```

Then update the aggregate targets:

- `net-connect`: add `docker network connect atlas-net atlas-<container_name> 2>/dev/null || true`
  - Derive `container_name` from the `container_name` field in `compose.yml`, or default to `atlas-<lowercase_component_name>`.
- `up`: add `$(MAKE) <prefix>-schema` (if schema) and `$(MAKE) <prefix>-build <prefix>-up` in the appropriate position (Platform services before Application services).
- `down`: add `-$(MAKE) <prefix>-down` in reverse order (Application before Platform).

---

## Step 3 — Update bootstrap_pi.sh (new components only)

Check `01_System/bootstrap_pi.sh` for an existing `DATA_ROOT` entry referencing the component.

**If already present:** skip.

**If new component:** inspect `compose.yml` for volume mounts referencing `DATA_ROOT`. For each unique log or data directory path, add the corresponding `mkdir -p` line to the bootstrap script's data root section:

```bash
  "${DATA_ROOT}/<component_slug>/logs" \
```

---

## Step 4 — Rebuild and restart the service

Determine the Make target prefix (same logic as Step 2, or read from existing Makefile entry).

Run from `01_System/`:

```bash
cd /home/linse/Prod/Atlas/01_System
make <prefix>-build <prefix>-up
```

Wait for the container to start. Check `docker logs <container_name>` — confirm no startup error. Report the result.

If the Makefile has a `<prefix>-schema` target and the schema is new (component is new), also run `make <prefix>-schema` **before** `<prefix>-build <prefix>-up` (schema must exist before the service tries to connect).

---

## Step 5 — Regenerate the system map

```bash
cd /home/linse/Prod/Atlas
python3 .claude/tools/generate_atlas_system_map.py
```

Report whether the map was updated successfully.

---

## Step 6 — Mark sprint complete

Update `<sprint_folder>/99_sprint_log.md`:
- Set `current_state` to `SPRINT_COMPLETE`
- Set `last_agent` to `/sprint-close`
- Set `next_agent` to `null`
- Append one line to the log: `- <YYYY-MM-DD> \`IMPLEMENTATION_IN_PROGRESS\` → \`SPRINT_COMPLETE\` [/sprint-close]`

---

## Step 7 — Report

Print a short summary:
- Sprint closed: `<sprint_name>`
- Component: `<component_name>` (`<layer>`)
- Architecture snapshot: `<component_root>/00_architecture/` updated
- Makefile: updated | unchanged
- Bootstrap: updated | unchanged
- Service: rebuilt and running | error (with detail)
- System map: regenerated
