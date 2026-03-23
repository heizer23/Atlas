/**
 * DayDetailView — shows fields for a selected CalendarEventRow.
 * Returns null when row prop is null (nothing selected).
 */

import type { CalendarEventRow } from './types';

interface Props {
  row: CalendarEventRow | null;
}

export default function DayDetailView({ row }: Props) {
  if (!row) return null;

  return (
    <div
      style={{
        marginTop: 'var(--space-md)',
        padding: 'var(--space-md)',
        background: 'var(--md-sys-color-surface)',
        border: '1px solid var(--md-sys-color-outline)',
        borderRadius: '4px',
      }}
    >
      <h3 className="type-title" style={{ marginBottom: 'var(--space-sm)' }}>
        Day Detail
      </h3>
      <dl
        style={{
          display: 'grid',
          gridTemplateColumns: 'max-content 1fr',
          gap: 'var(--space-xs) var(--space-md)',
          margin: 0,
        }}
      >
        <Field label="Date"         value={row.date} />
        <Field label="Application"  value={row.application} />
        <Field label="Source"       value={row.source_label} />
        <Field label="Label"        value={row.label} />
        <Field label="Value"        value={String(row.value)} />
        {row.detail    && <Field label="Detail"    value={row.detail} />}
        {row.deep_link && (
          <>
            <dt className="type-label" style={{ color: 'var(--md-sys-color-on-surface-variant)' }}>
              Link
            </dt>
            <dd className="type-body" style={{ margin: 0 }}>
              <a href={row.deep_link} target="_blank" rel="noreferrer">
                {row.deep_link}
              </a>
            </dd>
          </>
        )}
      </dl>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: 'contents' }}>
      <dt className="type-label" style={{ color: 'var(--md-sys-color-on-surface-variant)' }}>
        {label}
      </dt>
      <dd className="type-body" style={{ margin: 0 }}>
        {value}
      </dd>
    </div>
  );
}
