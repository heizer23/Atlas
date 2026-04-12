---
name: NumericSeries Sprint02 Pattern
description: Chronos write-by-name endpoint + UX polish (+ button, CSS tokens, creation mode); IMPLEMENTATION_IN_PROGRESS; test-runner blocked on Bash
type: project
---

NumericSeries Sprint02_ChronosAndUX added:
1. `POST /api/series/by-name/{label_name}/values` — Chronos name-based external write (case-insensitive match on labels.labels.name)
2. Removed inline CreateForm from SeriesListPage; replaced with '+' button → /series/new
3. SeriesDetailPage: creation mode when label_id === 'new'
4. Fixed list row CSS to use theme tokens (var(--md-sys-color-*))

**State at handoff:** IMPLEMENTATION_IN_PROGRESS (test-runner not yet run)

**Key implementation decisions:**
- by-name route registered BEFORE /{label_id}/values in batch.py to prevent FastAPI path shadowing
- ShellEntry.tsx unchanged — /series/:label_id already matches 'new'; SeriesDetailPage guards on `isNew = label_id === 'new'`
- Test infra created from scratch: tests/conftest.py, tests/fixtures.sql, tests/test_chronos_write.py
- Dockerfile updated to `pip install -e ".[dev]"` and `COPY tests/`; pyproject.toml got `[project.optional-dependencies] dev = [pytest>=8.0, httpx>=0.27]`
- Fixtures insert into labels.labels (fix-label-weight='Weight' with series, fix-label-steps='Daily Steps' without series) and clean_tables DELETEs by id LIKE 'fix-%'
- conftest.py uses `os.environ.setdefault("ATLAS_PG_DB", "atlas_test")` instead of module attribute override (database.py reads from env, not module attr)

**Blocked on:** Bash tool unavailable in orchestrator context; test-runner requires `docker exec atlas-numeric-series pytest tests/ -v`

**Human action required:** Rebuild the container then run tests:
```
docker compose -f 03_Application/NumericSeries/compose.yml build && docker compose -f 03_Application/NumericSeries/compose.yml up -d
docker exec atlas-numeric-series pytest tests/ -v
```
Or invoke sprint_test_runner in a Bash-capable context.

**Why:** No Agent tool and no Bash tool available to orchestrator; implemented directly as in Sprint01.
