import { useState, useMemo } from "react";
import type { Dataset, Row, ColumnSchema } from "../api/types";
import Skeleton from "./Skeleton";

type SortDir = "asc" | "desc" | null;

interface Props {
  dataset:       Dataset | null;  // null → Skeleton
  onRowClick?:   (row: Row) => void;
  onEdit?:       (row: Row) => void;
  onDelete?:     (id: string) => void;
  onPageChange?: (page: number) => void;
}

export default function TableView({
  dataset,
  onRowClick,
  onEdit,
  onDelete,
  onPageChange,
}: Props) {
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>(null);
  const [filters, setFilters] = useState<Record<string, string>>({});

  // Hooks must be called unconditionally — compute from dataset defensively
  const rows   = dataset?.rows   ?? [];
  const schema = dataset?.schema ?? [];
  const meta   = dataset?.meta;

  const displayRows = useMemo(() => {
    let result = [...rows];

    for (const [key, value] of Object.entries(filters)) {
      if (!value) continue;
      result = result.filter(row =>
        String(row[key] ?? "").toLowerCase().includes(value.toLowerCase())
      );
    }

    if (sortKey && sortDir) {
      result.sort((a, b) => {
        const av = a[sortKey], bv = b[sortKey];
        if (av === bv) return 0;
        const gt = (av ?? "") > (bv ?? "") ? 1 : -1;
        return sortDir === "asc" ? gt : -gt;
      });
    }

    return result;
  }, [rows, filters, sortKey, sortDir]);

  // Early return after all hooks
  if (dataset === null) return <Skeleton />;

  const showEdit   = meta!.row_actions.includes("edit")   && !!onEdit;
  const showDelete = meta!.row_actions.includes("delete") && !!onDelete;
  const hasActions = showEdit || showDelete;
  const totalPages = Math.ceil(meta!.total / meta!.page_size);

  function toggleSort(key: string) {
    if (sortKey !== key) { setSortKey(key); setSortDir("asc"); return; }
    if (sortDir === "asc") { setSortDir("desc"); return; }
    setSortKey(null); setSortDir(null);
  }

  return (
    <div className="table-view">
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              {schema.map(col => (
                <th key={col.key} className={col.type === "number" ? "num" : ""}>
                  <span
                    className={col.sortable !== false ? "sortable" : ""}
                    onClick={col.sortable !== false ? () => toggleSort(col.key) : undefined}
                  >
                    {col.label}
                    {col.sortable !== false && (
                      <span className="sort-icon">
                        {sortKey === col.key
                          ? sortDir === "asc" ? " ↑" : " ↓"
                          : " ⇅"}
                      </span>
                    )}
                  </span>
                  {col.filterable && (
                    <input
                      className="col-filter"
                      placeholder="Filter…"
                      value={filters[col.key] ?? ""}
                      onChange={e =>
                        setFilters(f => ({ ...f, [col.key]: e.target.value }))
                      }
                    />
                  )}
                </th>
              ))}
              {hasActions && <th className="actions-header">Actions</th>}
            </tr>
          </thead>
          <tbody>
            {displayRows.length === 0 ? (
              <tr>
                <td
                  colSpan={schema.length + (hasActions ? 1 : 0)}
                  className="empty-state"
                >
                  <span className="material-symbols-rounded">inbox</span>
                  <span className="type-body">No data yet</span>
                </td>
              </tr>
            ) : (
              displayRows.map(row => {
                if (!row.id) return null;
                return (
                  <tr
                    key={row.id}
                    onClick={onRowClick ? () => onRowClick(row) : undefined}
                    className={onRowClick ? "clickable" : ""}
                  >
                    {schema.map(col => (
                      <td key={col.key} className={col.type === "number" ? "num" : ""}>
                        {formatCell(row[col.key], col)}
                      </td>
                    ))}
                    {hasActions && (
                      <td
                        className="actions-cell"
                        onClick={e => e.stopPropagation()}
                      >
                        {showEdit && (
                          <button
                            className="icon-btn"
                            title="Edit"
                            onClick={() => onEdit!(row)}
                          >
                            <span className="material-symbols-rounded">edit</span>
                          </button>
                        )}
                        {showDelete && (
                          <button
                            className="icon-btn danger"
                            title="Delete"
                            onClick={() => onDelete!(row.id)}
                          >
                            <span className="material-symbols-rounded">delete</span>
                          </button>
                        )}
                      </td>
                    )}
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="pagination">
          <span className="type-label">{meta!.total} total</span>
          <button
            className="btn-outlined"
            disabled={meta!.page <= 1}
            onClick={() => onPageChange?.(meta!.page - 1)}
          >
            Previous
          </button>
          <span className="type-label">
            Page {meta!.page} / {totalPages}
          </span>
          <button
            className="btn-outlined"
            disabled={meta!.page >= totalPages}
            onClick={() => onPageChange?.(meta!.page + 1)}
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}

function formatCell(value: unknown, col: ColumnSchema): string {
  if (value === null || value === undefined) return "—";
  if (col.type === "date") {
    const d = new Date(String(value));
    return isNaN(d.getTime()) ? String(value) : d.toLocaleDateString();
  }
  if (col.type === "boolean") return value ? "Yes" : "No";
  return String(value);
}
