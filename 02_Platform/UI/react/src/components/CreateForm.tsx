import { useState, type FormEvent } from "react";
import type { FormField, ApiError } from "../api/types";
import ErrorCard from "./ErrorCard";

interface Props {
  title:        string;
  fields:       FormField[];
  onSubmit:     (data: Record<string, unknown>) => Promise<ApiError | void> | void;
  onCancel?:    () => void;
  submitLabel?: string;      // default: "Create"
}

// CreateForm — generic form primitive for creating a new entity.
// Fields are declared by the application; this component renders the right
// input type for each field and handles submission lifecycle.
// Follows UI_Contract: submit handler receives plain data; errors use ApiError shape.
export default function CreateForm({
  title,
  fields,
  onSubmit,
  onCancel,
  submitLabel = "Create",
}: Props) {
  const [values, setValues] = useState<Record<string, string>>(
    Object.fromEntries(fields.map(f => [f.key, ""]))
  );
  const [error, setError] = useState<ApiError | null>(null);
  const [busy,  setBusy]  = useState(false);

  function set(key: string, value: string) {
    setValues(v => ({ ...v, [key]: value }));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);

    // Convert empty strings to null for optional fields
    const data: Record<string, unknown> = {};
    for (const field of fields) {
      const val = values[field.key] ?? "";
      data[field.key] = val === "" ? null : val;
    }

    const result = await onSubmit(data);
    if (result && "error" in result) {
      setError(result);
    }

    setBusy(false);
  }

  return (
    <div className="create-form-container">
      <h2 className="type-headline create-form-title">{title}</h2>

      {error && <ErrorCard error={error} />}

      <form className="create-form" onSubmit={handleSubmit}>
        {fields.map(field => (
          <div key={field.key} className="form-field">
            <label className="type-label form-label" htmlFor={field.key}>
              {field.label}
              {field.required && <span className="required-star"> *</span>}
            </label>
            {renderInput(field, values[field.key] ?? "", v => set(field.key, v))}
          </div>
        ))}

        <div className="form-actions">
          {onCancel && (
            <button
              type="button"
              className="btn-text"
              onClick={onCancel}
              disabled={busy}
            >
              Cancel
            </button>
          )}
          <button type="submit" className="btn-filled" disabled={busy}>
            {busy ? "Saving…" : submitLabel}
          </button>
        </div>
      </form>
    </div>
  );
}

function renderInput(
  field: FormField,
  value: string,
  onChange: (v: string) => void
) {
  switch (field.type) {
    case "enum":
      return (
        <select
          id={field.key}
          className="form-input form-select"
          value={value}
          required={field.required}
          onChange={e => onChange(e.target.value)}
        >
          <option value="">Select…</option>
          {field.options?.map(opt => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      );

    case "date":
      return (
        <input
          id={field.key}
          type="date"
          className="form-input"
          value={value}
          required={field.required}
          onChange={e => onChange(e.target.value)}
        />
      );

    case "number":
      return (
        <input
          id={field.key}
          type="number"
          className="form-input"
          value={value}
          placeholder={field.placeholder}
          required={field.required}
          onChange={e => onChange(e.target.value)}
        />
      );

    case "boolean":
      return (
        <select
          id={field.key}
          className="form-input form-select"
          value={value}
          required={field.required}
          onChange={e => onChange(e.target.value)}
        >
          <option value="">Select…</option>
          <option value="true">Yes</option>
          <option value="false">No</option>
        </select>
      );

    default: // "string"
      return (
        <input
          id={field.key}
          type="text"
          className="form-input"
          value={value}
          placeholder={field.placeholder}
          required={field.required}
          onChange={e => onChange(e.target.value)}
        />
      );
  }
}
