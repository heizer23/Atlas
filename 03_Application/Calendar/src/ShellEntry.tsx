/**
 * Calendar — ShellEntry
 *
 * Renders a FullCalendar week/day view backed by the Calendar API.
 * Events are fetched on mount and when the visible date window changes.
 * Create: click-drag on calendar → modal form.
 * Edit/Delete: click on event → modal form.
 * Drag/Resize: handled by FullCalendar interaction plugin → PATCH.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Routes, Route } from 'react-router-dom';
import FullCalendar from '@fullcalendar/react';
import type { EventClickArg, EventDropArg, DateSelectArg, EventResizeDoneArg } from '@fullcalendar/core';
import dayGridPlugin from '@fullcalendar/daygrid';
import timeGridPlugin from '@fullcalendar/timegrid';
import interactionPlugin from '@fullcalendar/interaction';
import { apiFetch, isApiError } from '@platform-ui/api/client';
import ErrorCard from '@platform-ui/components/ErrorCard';
import Skeleton from '@platform-ui/components/Skeleton';
import type { ApiError } from '@platform-ui/api/types';

// ── Types ─────────────────────────────────────────────────────────────────────

interface CalendarEventRow {
  id: string;
  title: string;
  start_at: string;
  end_at: string;
  event_type: string;
  source_object_type: string | null;
  source_object_id: string | null;
  notes: string | null;
}

interface EventFormState {
  id?: string;
  title: string;
  start_at: string;
  end_at: string;
  event_type: string;
  source_object_id: string;
  notes: string;
}

const EMPTY_FORM: EventFormState = {
  title: '',
  start_at: '',
  end_at: '',
  event_type: 'personal_block',
  source_object_id: '',
  notes: '',
};

const EVENT_TYPE_OPTIONS = [
  { value: 'personal_block', label: 'Personal Block' },
  { value: 'task_block',     label: 'Task Block' },
  { value: 'blocker',        label: 'Blocker' },
];

const EVENT_TYPE_COLORS: Record<string, string> = {
  task_block:     'var(--md-sys-color-primary)',
  personal_block: 'var(--md-sys-color-secondary)',
  blocker:        'var(--md-sys-color-error)',
};

// ── Utility: ISO-8601 format from Date ────────────────────────────────────────

function toISO(date: Date): string {
  return date.toISOString();
}

function toInputDatetime(iso: string): string {
  // Convert ISO-8601 to datetime-local input value (YYYY-MM-DDTHH:MM)
  return iso.slice(0, 16);
}

function fromInputDatetime(value: string): string {
  // datetime-local input → ISO-8601 with Z
  return value ? new Date(value).toISOString() : '';
}

// ── EventModal ────────────────────────────────────────────────────────────────

function EventModal({
  form,
  isNew,
  saving,
  error,
  onChange,
  onSave,
  onDelete,
  onClose,
}: {
  form: EventFormState;
  isNew: boolean;
  saving: boolean;
  error: ApiError | null;
  onChange: (form: EventFormState) => void;
  onSave: () => void;
  onDelete?: () => void;
  onClose: () => void;
}) {
  const overlayStyle: React.CSSProperties = {
    position:       'fixed',
    inset:          0,
    background:     'rgba(0,0,0,0.45)',
    display:        'flex',
    alignItems:     'center',
    justifyContent: 'center',
    zIndex:         1000,
  };

  const modalStyle: React.CSSProperties = {
    background:    'var(--md-sys-color-surface)',
    border:        '1px solid var(--md-sys-color-outline-variant)',
    borderRadius:  '12px',
    padding:       'var(--space-lg)',
    width:         '440px',
    maxWidth:      '92vw',
    display:       'flex',
    flexDirection: 'column',
    gap:           'var(--space-md)',
  };

  const inputStyle: React.CSSProperties = {
    width:        '100%',
    padding:      'var(--space-xs) var(--space-sm)',
    borderRadius: '6px',
    border:       '1px solid var(--md-sys-color-outline-variant)',
    background:   'var(--md-sys-color-surface)',
    color:        'var(--md-sys-color-on-surface)',
    fontSize:     '0.95rem',
    boxSizing:    'border-box',
  };

  const labelStyle: React.CSSProperties = {
    display:      'block',
    fontSize:     '0.8rem',
    fontWeight:   600,
    color:        'var(--md-sys-color-on-surface-variant)',
    marginBottom: '4px',
  };

  const fieldStyle: React.CSSProperties = {
    display:       'flex',
    flexDirection: 'column',
    gap:           '4px',
  };

  function field<K extends keyof EventFormState>(key: K) {
    return {
      value: form[key] as string,
      onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
        onChange({ ...form, [key]: e.target.value }),
    };
  }

  return (
    <div style={overlayStyle} onClick={onClose}>
      <div style={modalStyle} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h2 className="type-display" style={{ fontSize: '1.1rem', margin: 0 }}>
            {isNew ? 'New Event' : 'Edit Event'}
          </h2>
          <button className="btn-outlined" onClick={onClose} style={{ padding: '2px 10px' }}>
            ✕
          </button>
        </div>

        {error && (
          <div>
            <ErrorCard error={error} />
          </div>
        )}

        <div style={fieldStyle}>
          <label style={labelStyle}>Title *</label>
          <input type="text" style={inputStyle} {...field('title')} placeholder="Event title" />
        </div>

        <div style={fieldStyle}>
          <label style={labelStyle}>Start *</label>
          <input
            type="datetime-local"
            style={inputStyle}
            value={form.start_at ? toInputDatetime(form.start_at) : ''}
            onChange={(e) => onChange({ ...form, start_at: fromInputDatetime(e.target.value) })}
          />
        </div>

        <div style={fieldStyle}>
          <label style={labelStyle}>End *</label>
          <input
            type="datetime-local"
            style={inputStyle}
            value={form.end_at ? toInputDatetime(form.end_at) : ''}
            onChange={(e) => onChange({ ...form, end_at: fromInputDatetime(e.target.value) })}
          />
        </div>

        <div style={fieldStyle}>
          <label style={labelStyle}>Type</label>
          <select style={inputStyle} {...field('event_type')}>
            {EVENT_TYPE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>

        {form.event_type === 'task_block' && (
          <div style={fieldStyle}>
            <label style={labelStyle}>Task ID (optional)</label>
            <input
              type="text"
              style={inputStyle}
              {...field('source_object_id')}
              placeholder="Paste task UUID"
            />
          </div>
        )}

        <div style={fieldStyle}>
          <label style={labelStyle}>Notes</label>
          <textarea
            style={{ ...inputStyle, resize: 'vertical' }}
            rows={2}
            value={form.notes}
            onChange={(e) => onChange({ ...form, notes: e.target.value })}
          />
        </div>

        <div style={{ display: 'flex', gap: 'var(--space-sm)' }}>
          <button
            className="btn-filled"
            onClick={onSave}
            disabled={saving || !form.title.trim() || !form.start_at || !form.end_at}
          >
            {saving ? 'Saving…' : 'Save'}
          </button>
          {!isNew && onDelete && (
            <button className="btn-outlined" onClick={onDelete} disabled={saving}
              style={{ color: 'var(--md-sys-color-error)', borderColor: 'var(--md-sys-color-error)' }}>
              Delete
            </button>
          )}
          <button className="btn-outlined" onClick={onClose} disabled={saving}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

// ── CalendarPage ──────────────────────────────────────────────────────────────

function CalendarPage() {
  const calRef = useRef<FullCalendar>(null);
  const [events, setEvents] = useState<CalendarEventRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<ApiError | null>(null);
  const [modal, setModal] = useState<{ open: boolean; isNew: boolean; form: EventFormState }>({
    open: false,
    isNew: true,
    form: EMPTY_FORM,
  });
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<ApiError | null>(null);

  // Fetch events for the current calendar view window.
  const fetchEvents = useCallback(async (start?: string, end?: string) => {
    setLoading(true);
    setLoadError(null);
    let url = '/cal/events';
    const params: string[] = [];
    if (start) params.push(`start=${encodeURIComponent(start)}`);
    if (end) params.push(`end=${encodeURIComponent(end)}`);
    if (params.length) url += '?' + params.join('&');

    const res = await apiFetch<{ rows: CalendarEventRow[] }>(url);
    setLoading(false);
    if (isApiError(res)) {
      setLoadError(res as ApiError);
    } else {
      setEvents((res as { rows: CalendarEventRow[] }).rows ?? []);
    }
  }, []);

  useEffect(() => {
    // Initial fetch — no filter (FullCalendar will trigger datesSet after mount)
    fetchEvents();
  }, [fetchEvents]);

  // ── FullCalendar event objects ────────────────────────────────────────────

  const fcEvents = events.map((e) => ({
    id: e.id,
    title: e.title,
    start: e.start_at,
    end: e.end_at,
    backgroundColor: EVENT_TYPE_COLORS[e.event_type] ?? 'var(--md-sys-color-primary)',
    borderColor: EVENT_TYPE_COLORS[e.event_type] ?? 'var(--md-sys-color-primary)',
    extendedProps: {
      event_type:         e.event_type,
      source_object_type: e.source_object_type,
      source_object_id:   e.source_object_id,
      notes:              e.notes,
    },
  }));

  // ── Handlers ──────────────────────────────────────────────────────────────

  function openCreateModal(start: string, end: string) {
    setSaveError(null);
    setModal({
      open: true,
      isNew: true,
      form: { ...EMPTY_FORM, start_at: start, end_at: end },
    });
  }

  function openEditModal(event: CalendarEventRow) {
    setSaveError(null);
    setModal({
      open: true,
      isNew: false,
      form: {
        id:               event.id,
        title:            event.title,
        start_at:         event.start_at,
        end_at:           event.end_at,
        event_type:       event.event_type,
        source_object_id: event.source_object_id ?? '',
        notes:            event.notes ?? '',
      },
    });
  }

  function closeModal() {
    setModal((m) => ({ ...m, open: false }));
  }

  async function handleSave() {
    const { form, isNew } = modal;
    if (!form.title.trim() || !form.start_at || !form.end_at) return;
    setSaving(true);
    setSaveError(null);

    const payload: Record<string, unknown> = {
      title:      form.title.trim(),
      start_at:   form.start_at,
      end_at:     form.end_at,
      event_type: form.event_type,
      notes:      form.notes.trim() || null,
    };

    if (form.event_type === 'task_block' && form.source_object_id.trim()) {
      payload.source_object_type = 'task';
      payload.source_object_id = form.source_object_id.trim();
    } else {
      payload.source_object_type = null;
      payload.source_object_id = null;
    }

    let res: unknown;
    if (isNew) {
      res = await apiFetch('/cal/events', { method: 'POST', body: JSON.stringify(payload) });
    } else {
      res = await apiFetch(`/cal/events/${form.id}`, { method: 'PATCH', body: JSON.stringify(payload) });
    }

    setSaving(false);
    if (isApiError(res)) {
      setSaveError(res as ApiError);
      return;
    }

    closeModal();
    // Re-fetch to sync state
    const calApi = calRef.current?.getApi();
    if (calApi) {
      const view = calApi.view;
      fetchEvents(view.activeStart.toISOString(), view.activeEnd.toISOString());
    } else {
      fetchEvents();
    }
  }

  async function handleDelete() {
    const { form } = modal;
    if (!form.id) return;
    setSaving(true);
    setSaveError(null);

    const res = await apiFetch(`/cal/events/${form.id}`, { method: 'DELETE' });
    setSaving(false);
    if (isApiError(res)) {
      setSaveError(res as ApiError);
      return;
    }

    closeModal();
    setEvents((prev) => prev.filter((e) => e.id !== form.id));
  }

  // ── FullCalendar callback handlers ────────────────────────────────────────

  function handleDateSelect(selectInfo: DateSelectArg) {
    openCreateModal(toISO(selectInfo.start), toISO(selectInfo.end));
  }

  function handleEventClick(clickInfo: EventClickArg) {
    const id = clickInfo.event.id;
    const raw = events.find((e) => e.id === id);
    if (raw) openEditModal(raw);
  }

  async function handleEventDrop(dropInfo: EventDropArg) {
    const { event } = dropInfo;
    if (!event.start || !event.end) { dropInfo.revert(); return; }

    const res = await apiFetch(`/cal/events/${event.id}`, {
      method: 'PATCH',
      body: JSON.stringify({
        start_at: toISO(event.start),
        end_at:   toISO(event.end),
      }),
    });
    if (isApiError(res)) {
      dropInfo.revert();
    } else {
      setEvents((prev) =>
        prev.map((e) =>
          e.id === event.id
            ? { ...e, start_at: toISO(event.start!), end_at: toISO(event.end!) }
            : e,
        ),
      );
    }
  }

  async function handleEventResize(resizeInfo: EventResizeDoneArg) {
    const { event } = resizeInfo;
    if (!event.end) { resizeInfo.revert(); return; }

    const res = await apiFetch(`/cal/events/${event.id}`, {
      method: 'PATCH',
      body: JSON.stringify({ end_at: toISO(event.end) }),
    });
    if (isApiError(res)) {
      resizeInfo.revert();
    } else {
      setEvents((prev) =>
        prev.map((e) =>
          e.id === event.id ? { ...e, end_at: toISO(event.end!) } : e,
        ),
      );
    }
  }

  // Re-fetch when user navigates to a different week/day
  function handleDatesSet(dateInfo: { start: Date; end: Date }) {
    fetchEvents(dateInfo.start.toISOString(), dateInfo.end.toISOString());
  }

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="page">
      {loadError && (
        <div style={{ marginBottom: 'var(--space-sm)' }}>
          <ErrorCard error={loadError} />
        </div>
      )}

      {loading && events.length === 0 ? (
        <Skeleton />
      ) : (
        <div style={{ height: 'calc(100vh - 80px)' }}>
          <FullCalendar
            ref={calRef}
            plugins={[dayGridPlugin, timeGridPlugin, interactionPlugin]}
            initialView="timeGridWeek"
            headerToolbar={{
              left:   'prev,next today',
              center: 'title',
              right:  'timeGridWeek,timeGridDay',
            }}
            events={fcEvents}
            selectable={true}
            selectMirror={true}
            editable={true}
            droppable={false}
            eventResizableFromStart={false}
            select={handleDateSelect}
            eventClick={handleEventClick}
            eventDrop={handleEventDrop}
            eventResize={handleEventResize}
            datesSet={handleDatesSet}
            height="100%"
          />
        </div>
      )}

      {modal.open && (
        <EventModal
          form={modal.form}
          isNew={modal.isNew}
          saving={saving}
          error={saveError}
          onChange={(form) => setModal((m) => ({ ...m, form }))}
          onSave={handleSave}
          onDelete={modal.isNew ? undefined : handleDelete}
          onClose={closeModal}
        />
      )}
    </div>
  );
}

// ── Shell entry point ─────────────────────────────────────────────────────────

export default function ShellEntry() {
  return (
    <Routes>
      <Route path="/*" element={<CalendarPage />} />
    </Routes>
  );
}
