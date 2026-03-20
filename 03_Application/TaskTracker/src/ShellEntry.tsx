/**
 * TaskTracker ShellEntry
 *
 * Default-export React component for the Atlas Shell outlet.
 * Renders nested <Routes> (no BrowserRouter — inherits the shell's router context).
 * All platform imports use the @platform-ui alias.
 *
 * Routes:
 *   /tasks  → Task list with create form
 */

import { useState } from 'react';
import { Routes, Route } from 'react-router-dom';
import { useDataset } from '@platform-ui/hooks/useDataset';
import { apiFetch, isApiError } from '@platform-ui/api/client';
import TableView from '@platform-ui/components/TableView';
import DetailView from '@platform-ui/components/DetailView';
import CreateForm from '@platform-ui/components/CreateForm';
import ErrorCard from '@platform-ui/components/ErrorCard';
import type { Row, FormField, Dataset } from '@platform-ui/api/types';

// ── Form field definitions ────────────────────────────────────────────────────

const TASK_FIELDS: FormField[] = [
  { key: 'title',       label: 'Title',       type: 'string', required: true, placeholder: 'Task title' },
  { key: 'description', label: 'Description', type: 'string' },
  { key: 'priority',    label: 'Priority',    type: 'enum',   required: true,
    options: [
      { value: 'low',    label: 'Low' },
      { value: 'medium', label: 'Medium' },
      { value: 'high',   label: 'High' },
    ],
  },
  { key: 'due_date', label: 'Due Date', type: 'date' },
];

// ── Tasks page ────────────────────────────────────────────────────────────────

function TasksPage() {
  const [page, setPage]         = useState(1);
  const [selected, setSelected] = useState<Row | null>(null);
  const [creating, setCreating] = useState(false);

  const { dataset, error, loading, refetch } = useDataset('/tasks', { page: String(page) });

  if (error) return <ErrorCard error={error} />;

  if (selected) {
    return (
      <DetailView
        row={selected}
        schema={dataset!.schema}
        onBack={() => setSelected(null)}
      />
    );
  }

  if (creating) {
    return (
      <div className="page">
        <CreateForm
          title="New Task"
          fields={TASK_FIELDS}
          submitLabel="Create"
          onCancel={() => setCreating(false)}
          onSubmit={async (data) => {
            const res = await apiFetch<Dataset>('/tasks', {
              method: 'POST',
              body: JSON.stringify(data),
            });
            if (isApiError(res)) return res;
            setCreating(false);
            refetch?.();
          }}
        />
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="type-display">Tasks</h1>
        <button className="btn-primary" onClick={() => setCreating(true)}>
          New Task
        </button>
      </div>

      <TableView
        dataset={loading ? null : dataset}
        onRowClick={setSelected}
        onDelete={async (id) => {
          await apiFetch(`/tasks/${id}`, { method: 'DELETE' });
          refetch?.();
        }}
      />
    </div>
  );
}

// ── Shell entry point ─────────────────────────────────────────────────────────

export default function ShellEntry() {
  return (
    <Routes>
      <Route path="/*" element={<TasksPage />} />
    </Routes>
  );
}
