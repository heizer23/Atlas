# Sprint Draft — Dataset Extensions: Sibling Fields, List-Valued Columns, Shared Serialization

## Goal

Give apps a supported, versioned way to (1) attach extra structured data next to a
`Dataset` and (2) declare list-valued row fields, plus one shared serialization path,
so apps stop hand-rolling `response_model=None` + `model_dump()` + dict-merge
workarounds. Origin: decision D4 of `00_Blueprint/Quality/Rule_Audit_2026-10-11.md`
(finding T3).

## Layer

02_Platform

## Component

platform_contracts (`02_Platform/packages/platform_contracts/`), with the contract
document and TypeScript types it mirrors (`02_Platform/Atlas_Shell/platform-ui/api/`).

## Why (evidence)

- `Dataset` is `{meta, schema, rows}` only. Pydantic's default `extra="ignore"` silently
  drops any other constructor kwarg (EVD-2026-10-01-004).
- Apps that need more attach it by dumping the model to a dict and merging keys into it
  before wrapping in `JSONResponse`. Values merged after `model_dump(mode="json")` never
  pass through pydantic's serializer, so a raw `date` raises `TypeError` in
  `json.dumps` (EVD-2026-10-01-005). HabitTracker needed three review rounds to close
  this one field at a time (EVD-2026-10-01-004/005/006).
- List-valued row fields (StorageTracker `history`, EssayCards `sections`, Calendar)
  are embedded as undeclared row keys because `ColumnType` has no list type and the
  contract says undeclared row fields are ignored (EVD-2026-08-28-001: "recurring gap").
- The `Dataset` -> `JSONResponse` helper is copy-pasted per router file: about 22
  `model_dump(by_alias=True, mode="json")` call sites across 10 apps. Every
  Dataset-returning route also needs `response_model=None` because the return type is
  `Dataset | ApiError`.

## Scope

1. **Sibling data.** `Dataset` gains one optional, additive, top-level key for
   app-defined structured data that is not rows. The contract defines its name, shape
   (JSON object), absence behavior, and who owns the meaning of its content (the
   producing app, never the platform; R-CON-PL-01).
2. **List-valued columns.** `ColumnType` gains a way to declare that a row field holds
   a JSON array, so `schema` can describe fields like `history`/`sections` instead of
   leaving them undeclared. Rendering is not part of this sprint (see Out of Scope);
   the contract only says that the field exists and is an array.
3. **One serialization path.** A shared helper in `platform_contracts` produces the
   JSON-safe response body for a `Dataset` including the new sibling data, with the
   pydantic JSON serializer applied to the whole payload (dates, datetimes, Decimals,
   UUIDs inside sibling data serialize correctly, with no post-hoc dict merging).
4. **Contract and types.** `UI_Data_Contract.md`, `types.ts`, `contracts.py` and the
   `platform_contracts` `CLAUDE.md` are updated together, with a version bump and
   changelog (R-CON-BP-04 Stability Requirement, items 1-3).
5. **Housekeeping inside the same files.** Reconcile the version mismatch (R-CON-BP-04
   says v0.5, `UI_Data_Contract.md` header says v0.4, and its v0.4 changelog already
   describes the mutation exemption R-CON-BP-04 calls v0.5). Fix stale source references
   (`contracts.py` header and package `CLAUDE.md` cite
   `00_Blueprint/UI/01_UI_Contract` and `R-CON-BP-04_ui_data_contract.md`; the rule is
   `.claude/rules/R-CON-BP.md` R-CON-BP-04).

## Out of Scope

- **Migrating existing apps.** HabitTracker `period_summary`, StorageTracker `history`,
  EssayCards `sections`/`review_stats`, and the ~22 local `_dataset_response` helpers
  keep working unchanged. Migration is optional follow-up work per app. This sprint must
  not alter any existing app's response bytes.
- **Frontend rendering** of list-valued columns or sibling data in generic Dataset views
  (tables, DetailView). Apps continue to read these through their own typed code.
- Any change to `ApiError`, the error envelope, chart mapping types, `CreateForm`, or
  `row_actions`.
- Any domain-specific field or logic in the platform (R-CON-PL-01). The platform carries
  sibling data without interpreting it.
- Pagination/total semantics, new endpoint categories (R-CON-BP-04 section "Endpoint
  categories" is unchanged).

## Constraints and Decisions Already Made

- **Additive only.** No removal or rename of any existing contract field. A producer or
  consumer that ignores the new key and the new column type must behave exactly as
  before (R-CON-BP-04: additive = non-breaking).
- **Not eligible for the fast path** (R-PRO-BP-01 section 11): this changes a shared
  contract surface. Run the full design -> review chain.
- **Dependency direction (R-CON-PL-02).** `platform_contracts` currently depends only on
  `pydantic`. Adding a FastAPI/Starlette dependency to it needs an explicit decision and
  justification in the design; a pure function returning the JSON-safe dict, with apps
  wrapping it in `JSONResponse`, is acceptable if the dependency is not justified. The
  design must also state how the package reaches each consumer's container (Dockerfile
  copy/install path) because a new public symbol is only usable once every consuming
  image is rebuilt.
- **Serialization correctness is the point.** The design must show, by construction,
  that no value reaches `json.dumps` without passing through the pydantic JSON
  serializer (the HabitTracker `anchor_date` class of bug), including `by_alias` for
  `schema` and behavior when the sibling data is absent (key omitted vs `null`;
  R-CON-AL-01 style explicitness: defaults, empty-result behavior).

## Open Questions for the Designer

1. **Name and shape of the sibling key.** A single `extensions: {...}` object (one
   reserved key, collision-free with `meta/schema/rows`) versus arbitrary named
   top-level siblings (matches HabitTracker's existing `period_summary` placement but
   leaves the key space unbounded). Recommendation: single reserved key; state how
   existing top-level siblings relate to it.
2. **List column representation.** A new `ColumnType` value (for example `"list"`) versus
   a flag on `ColumnSchema`. Note `ColumnType` is a closed union in `types.ts` and
   `UI_Data_Contract.md` but an open `str` in `contracts.py`; the design must remove that
   inconsistency or declare it intentional, and must not break `CreateForm`, which reuses
   `ColumnType` for form fields (section 7 of the contract).
3. **Where the shared helper lives and how it is tested.** `platform_contracts` has no
   tests and no test container. Decide where its unit tests run (for example inside an
   existing consumer's test container) and whether a `10_test_spec.md` is required (the
   package exposes no HTTP API, so it is optional per R-PRO-BP-01 section 1, but the
   serialization behavior needs at least date, datetime, Decimal and UUID cases inside
   sibling data, a Dataset without sibling data, and `schema` alias output).
4. **Consumer proof.** Which single existing app route (suggestion: HabitTracker
   `GET /reports`, the case that cost three review rounds) is used as a read-only
   verification that the helper reproduces the current response shape, without migrating
   it in this sprint.

## Non-Functional Notes

- Security (R-OPS-BP-02): no new endpoints, ports, or exposure. Sibling data is
  producer-defined, so the contract must say it is subject to the same data-exposure
  review as rows.
- Rebuild/deploy: every app image that vendors `platform_contracts` must be rebuilt to
  pick up new symbols; apps that do not use them are unaffected until rebuilt.
