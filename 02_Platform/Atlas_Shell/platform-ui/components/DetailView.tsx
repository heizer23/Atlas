import type { Row, ColumnSchema } from "../api/types";

interface Props {
  row:    Row;
  schema: ColumnSchema[];
  onBack: () => void;
}

// Read-only key-value card. Editing is a separate page/dialog.
export default function DetailView({ row, schema, onBack }: Props) {
  const visible = schema.filter(col => col.detail_visible !== false);

  return (
    <div className="detail-view">
      <div className="detail-header">
        <button className="icon-btn" onClick={onBack} title="Back">
          <span className="material-symbols-rounded">arrow_back</span>
        </button>
        <h2 className="type-headline">Detail</h2>
      </div>

      <div className="detail-fields">
        {visible.map(col => (
          <div key={col.key} className="detail-field">
            <span className="detail-field-label type-label">{col.label}</span>
            <span className="detail-field-value type-body">
              {formatValue(row[col.key], col)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function formatValue(value: unknown, col: ColumnSchema): string {
  if (value === null || value === undefined) return "—";
  if (col.type === "date" && value) {
    const d = new Date(String(value));
    return isNaN(d.getTime()) ? String(value) : d.toLocaleDateString();
  }
  if (col.type === "boolean") return value ? "Yes" : "No";
  return String(value);
}
