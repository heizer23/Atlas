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

**Abort if `current_state` is not `IMPLEMENTATION_IN_PROGRESS` or `TESTS_PASSING`.** State the current state and what must happen first. Both states are valid entry points for sprint-close: `TESTS_PASSING` when the test stage ran; `IMPLEMENTATION_IN_PROGRESS` when `10_test_spec.md` was absent and the test stage was skipped.

Derive `component_root` from `layer` and `component_name`:
- `02_Platform/<component_name>`
- `03_Application/<component_name>`

---

## Step 1 — Write clean architecture files to `00_architecture/`

Create or overwrite `<component_root>/00_architecture/` with cleaned versions of the sprint design artifacts.

**For `10_architecture.json` and `10_scaffolding.json`:** run the strip script to remove sprint markers before writing:

```bash
python3 /home/linse/Prod/Atlas/.claude/tools/strip_sprint_markers.py \
  <sprint_folder>/10_architecture.json \
  <component_root>/00_architecture/architecture.json

python3 /home/linse/Prod/Atlas/.claude/tools/strip_sprint_markers.py \
  <sprint_folder>/10_scaffolding.json \
  <component_root>/00_architecture/scaffolding.json
```

**Fast-path sprints** (`"fast_path": true`, no `10_*` files): skip the `architecture.json` / `scaffolding.json` / schema copies below. Check whether the change touches anything `00_architecture/` documents; if not, note "snapshot unchanged" in the Step 6 log line.

**Schema snapshot (`00_architecture/schema.sql`) must always be the FULL current schema, never a sprint change file.** `10_schema.sql` is usually a per-sprint delta (only new/changed objects); copying it over the snapshot leaves a partial schema, and any Make target that feeds the snapshot to psql then fails on a fresh database. Pick the source in this order:

1. `<component_root>/schema.sql` exists (the runtime schema applied at startup) → copy it to `<component_root>/00_architecture/schema.sql`.
2. Otherwise, no snapshot exists yet and `10_schema.sql` is present (new component, so the file is the whole schema) → copy it.
3. Otherwise (snapshot exists, only a delta `10_schema.sql`, no runtime schema) → do NOT overwrite. Tell the human the snapshot cannot be refreshed mechanically and why.

This folder is the canonical current-architecture snapshot. Both `architecture.json` and `scaffolding.json` are always clean — no sprint markers, no removed entries, no `sprint_note` field.

---

## Step 2 — Update Makefile (new components only)

Check the Makefile at `01_System/Makefile` for an existing entry referencing `component_root`.

**If an entry already exists and no changes to it are required:** no Makefile changes needed — skip to Step 3.

**If this is a new component or some changes require changes in the make file:** add a region block following the established pattern. Derive the Make target prefix as follows:
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

If the component owns persistent state (a full schema exists: `<component_root>/schema.sql`, or for a new component `10_schema.sql`), also add the target below. It must read the FULL schema: `<component_root>/schema.sql` when that file exists, otherwise `00_architecture/schema.sql` (which Step 1 made a full copy). Never point it at a sprint change file.

```makefile
<prefix>-schema:
	@test -n "$(ATLAS_PG_USER)" || (echo "ATLAS_PG_USER missing" && exit 1)
	@test -n "$(ATLAS_PG_DB)"   || (echo "ATLAS_PG_DB missing" && exit 1)
	$(PG_COMPOSE) exec -T postgres psql -v ON_ERROR_STOP=1 -U $(ATLAS_PG_USER) -d $(ATLAS_PG_DB) < $(<PREFIX>_DIR)/schema.sql

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

## Step 5 — Regenerate the developer reference

```bash
cd /home/linse/Prod/Atlas
python3 .claude/tools/generate_atlas_dev_ref.py
```

This regenerates `.claude/supportDocs/atlas_dev_ref.md` — the canonical development reference for Claude Code. Report whether it was updated successfully.

---

## Step 6 — Mark sprint complete

Update `<sprint_folder>/99_sprint_log.md`:
- Set `current_state` to `SPRINT_COMPLETE`
- Set `last_agent` to `/sprint-close`
- Set `next_agent` to `null`
- Append one line to the log, using the state you actually found in Step 0 as the "from" state: `- <YYYY-MM-DD> \`<previous current_state>\` → \`SPRINT_COMPLETE\` [/sprint-close]`

---

## Step 7 — Report

Print a short summary:
- Sprint closed: `<sprint_name>`
- Component: `<component_name>` (`<layer>`)
- Architecture snapshot: `<component_root>/00_architecture/` updated
- Makefile: updated | unchanged
- Bootstrap: updated | unchanged
- Service: rebuilt and running | error (with detail)
- Developer reference: regenerated
