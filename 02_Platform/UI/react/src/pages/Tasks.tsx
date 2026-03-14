import { useState } from "react";
import { useDataset } from "../hooks/useDataset";
import { apiFetch, isApiError } from "../api/client";
import TableView from "../components/TableView";
import DetailView from "../components/DetailView";
import CreateForm from "../components/CreateForm";
import ErrorCard from "../components/ErrorCard";
import type { Row, FormField, ApiError } from "../api/types";

// ── Status filter options ─────────────────────────────────────────────────────

const STATUS_FILTERS = [
  { value: "",            label: "All" },
  { value: "open",        label: "Open" },
  { value: "in_progress", label: "In Progress" },
  { value: "done",        label: "Done" },
] as const;

// ── CreateForm field definitions ──────────────────────────────────────────────

const CREATE_FIELDS: FormField[] = [
  {
    key:         "title",
    label:       "Title",
    type:        "string",
    required:    true,
    placeholder: "What needs to be done?",
  },
  {
    key:         "description",
    label:       "Description",
    type:        "string",
    placeholder: "Optional details",
  },
  {
    key:     "priority",
    label:   "Priority",
    type:    "enum",
    required: true,
    options: [
      { value: "low",    label: "Low" },
      { value: "medium", label: "Medium" },
      { value: "high",   label: "High" },
    ],
  },
  { key: "due_date", label: "Due Date", type: "date" },
];

const EDIT_FIELDS: FormField[] = [
  {
    key:         "title",
    label:       "Title",
    type:        "string",
    required:    true,
    placeholder: "Task title",
  },
  {
    key:         "description",
    label:       "Description",
    type:        "string",
    placeholder: "Optional details",
  },
  {
    key:     "status",
    label:   "Status",
    type:    "enum",
    required: true,
    options: [
      { value: "open",        label: "Open" },
      { value: "in_progress", label: "In Progress" },
      { value: "done",        label: "Done" },
    ],
  },
  {
    key:     "priority",
    label:   "Priority",
    type:    "enum",
    required: true,
    options: [
      { value: "low",    label: "Low" },
      { value: "medium", label: "Medium" },
      { value: "high",   label: "High" },
    ],
  },
  { key: "due_date", label: "Due Date", type: "date" },
];

// ── Component ─────────────────────────────────────────────────────────────────

type View = "list" | "detail" | "create" | "edit";

export default function Tasks() {
  const [page,         setPage]         = useState(1);
  const [statusFilter, setStatusFilter] = useState("");
  const [view,         setView]         = useState<View>("list");
  const [selected,     setSelected]     = useState<Row | null>(null);
  const [mutateError,  setMutateError]  = useState<ApiError | null>(null);

  const params: Record<string, string> = { page: String(page) };
  if (statusFilter) params.status = statusFilter;

  const { dataset, error, loading: _loading, refresh } = useDataset("/tasks", params);

  // ── Mutations ──────────────────────────────────────────────────────────────

  async function handleCreate(data: Record<string, unknown>) {
    const res = await apiFetch<unknown>("/tasks", {
      method: "POST",
      body:   JSON.stringify(data),
    });
    if (isApiError(res)) return res;
    setView("list");
    refresh();
  }

  async function handleEdit(data: Record<string, unknown>) {
    if (!selected) return;
    const res = await apiFetch<unknown>(`/tasks/${selected.id}`, {
      method: "PATCH",
      body:   JSON.stringify(data),
    });
    if (isApiError(res)) return res;
    setView("list");
    setSelected(null);
    refresh();
  }

  async function handleDelete(id: string) {
    setMutateError(null);
    const res = await apiFetch<unknown>(`/tasks/${id}`, { method: "DELETE" });
    if (isApiError(res)) { setMutateError(res); return; }
    refresh();
  }

  function openEdit(row: Row) {
    setSelected(row);
    setView("edit");
  }

  function openDetail(row: Row) {
    setSelected(row);
    setView("detail");
  }

  // ── Render: non-list views ─────────────────────────────────────────────────

  if (view === "create") {
    return (
      <div className="page">
        <CreateForm
          title="New Task"
          fields={CREATE_FIELDS}
          submitLabel="Create Task"
          onCancel={() => setView("list")}
          onSubmit={handleCreate}
        />
      </div>
    );
  }

  if (view === "edit" && selected) {
    const defaults = selected as Record<string, unknown>;
    const editFields = EDIT_FIELDS.map(f => ({
      ...f,
      placeholder: defaults[f.key] != null ? String(defaults[f.key]) : f.placeholder,
    }));
    return (
      <div className="page">
        <CreateForm
          title="Edit Task"
          fields={editFields}
          submitLabel="Save Changes"
          onCancel={() => { setView("list"); setSelected(null); }}
          onSubmit={handleEdit}
        />
      </div>
    );
  }

  if (view === "detail" && selected && dataset) {
    return (
      <div className="page">
        <DetailView
          row={selected}
          schema={dataset.schema}
          onBack={() => { setView("list"); setSelected(null); }}
        />
      </div>
    );
  }

  // ── Render: list view ──────────────────────────────────────────────────────

  if (error) return <ErrorCard error={error} />;

  return (
    <div className="page">
      <div className="tasks-toolbar">
        <h1 className="type-headline">Tasks</h1>
        <button className="btn-filled" onClick={() => setView("create")}>
          + New Task
        </button>
      </div>

      {/* Status filter chips */}
      <div className="tasks-filters">
        {STATUS_FILTERS.map(f => (
          <button
            key={f.value}
            className={`filter-chip${statusFilter === f.value ? " active" : ""}`}
            onClick={() => { setStatusFilter(f.value); setPage(1); }}
          >
            {f.label}
          </button>
        ))}
      </div>

      {mutateError && <ErrorCard error={mutateError} />}

      <TableView
        dataset={dataset}
        onRowClick={openDetail}
        onEdit={openEdit}
        onDelete={handleDelete}
        onPageChange={setPage}
      />
    </div>
  );
}
