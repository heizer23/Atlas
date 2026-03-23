/**
 * CalendarPage — Unified Calendar entry point.
 *
 * Responsibilities:
 * - Fetch sources list on mount (GET /api/chronicle/calendar/sources)
 * - Maintain sources[] and activeSrc state
 * - Auto-open first selected source on initial load (if any selected)
 * - Render SourceChooser + HeatmapRenderer (when a source is active) + DayDetailView
 * - Handle source selection toggle (PATCH /api/chronicle/calendar/sources)
 */

import { useState, useEffect } from 'react';
import { apiFetch, isApiError } from '@platform-ui/api/client';
import ErrorCard from '@platform-ui/components/ErrorCard';
import Skeleton from '@platform-ui/components/Skeleton';
import type { ApiError } from '@platform-ui/api/types';
import type { SourceListRow, CalendarEventRow } from './types';
import SourceChooser from './SourceChooser';
import HeatmapRenderer from './HeatmapRenderer';
import DayDetailView from './DayDetailView';

interface ActiveSource {
  application:  string;
  source_label: string;
}

export default function CalendarPage() {
  const [sources,    setSources]    = useState<SourceListRow[]>([]);
  const [activeSrc,  setActiveSrc]  = useState<ActiveSource | null>(null);
  const [selectedDay, setSelectedDay] = useState<CalendarEventRow | null>(null);
  const [loading,    setLoading]    = useState(true);
  const [error,      setError]      = useState<ApiError | null>(null);
  const [toggling,   setToggling]   = useState(false);

  // ── Load sources on mount ────────────────────────────────────────────────────

  useEffect(() => {
    setLoading(true);
    setError(null);

    apiFetch<SourceListRow[]>('/chronicle/calendar/sources').then((res) => {
      if (isApiError(res)) {
        setError(res);
      } else {
        const list = res as SourceListRow[];
        setSources(list);

        // Auto-open first selected source
        const firstSelected = list.find((s) => s.selected);
        if (firstSelected) {
          setActiveSrc({
            application:  firstSelected.application,
            source_label: firstSelected.source_label,
          });
        }
      }
      setLoading(false);
    });
  }, []);

  // ── Toggle handler ───────────────────────────────────────────────────────────

  async function handleToggle(application: string, source_label: string, selected: boolean) {
    if (toggling) return;
    setToggling(true);

    const res = await apiFetch<{ application: string; source_label: string; selected: boolean }>(
      '/chronicle/calendar/sources',
      {
        method: 'PATCH',
        body: JSON.stringify({ application, source_label, selected }),
      },
    );

    setToggling(false);

    if (isApiError(res)) {
      // Surface error but don't block — leave current state
      setError(res as ApiError);
      return;
    }

    const updated = res as { application: string; source_label: string; selected: boolean };

    // Update sources list optimistically (confirmed by server response)
    setSources((prev) =>
      prev.map((s) =>
        s.application === updated.application && s.source_label === updated.source_label
          ? { ...s, selected: updated.selected }
          : s,
      ),
    );

    // If we just selected a new source and none is active, auto-open it
    if (updated.selected && activeSrc === null) {
      setActiveSrc({ application: updated.application, source_label: updated.source_label });
    }

    // Clear selected day when toggling changes the active source context
    setSelectedDay(null);
  }

  // ── Source click (activate) ──────────────────────────────────────────────────

  function handleActivate(application: string, source_label: string) {
    setActiveSrc({ application, source_label });
    setSelectedDay(null);
  }

  // ── Render ───────────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="page">
        <div className="page-header">
          <h1 className="type-display">Calendar</h1>
        </div>
        <Skeleton />
      </div>
    );
  }

  if (error && sources.length === 0) {
    return (
      <div className="page">
        <div className="page-header">
          <h1 className="type-display">Calendar</h1>
        </div>
        <ErrorCard error={error} />
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="type-display">Calendar</h1>
      </div>

      {error && (
        <div style={{ marginBottom: 'var(--space-sm)' }}>
          <ErrorCard error={error} />
        </div>
      )}

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '200px 1fr',
          gap: 'var(--space-md)',
          alignItems: 'start',
        }}
      >
        {/* Source chooser panel */}
        <aside>
          <h2 className="type-title" style={{ marginBottom: 'var(--space-sm)' }}>
            Sources
          </h2>
          <SourceChooser
            sources={sources}
            onToggle={(application, source_label, selected) => {
              // Toggle selection in DB
              handleToggle(application, source_label, selected);
              // Also activate the clicked source for viewing
              handleActivate(application, source_label);
            }}
          />
        </aside>

        {/* Heatmap area */}
        <main>
          {activeSrc ? (
            <>
              <h2 className="type-title" style={{ marginBottom: 'var(--space-sm)' }}>
                {activeSrc.source_label}
                <span
                  style={{
                    marginLeft: 'var(--space-xs)',
                    fontSize: '0.8em',
                    fontWeight: 400,
                    color: 'var(--md-sys-color-on-surface-variant)',
                  }}
                >
                  ({activeSrc.application})
                </span>
              </h2>
              <HeatmapRenderer
                application={activeSrc.application}
                source_label={activeSrc.source_label}
                onDayClick={setSelectedDay}
              />
              <DayDetailView row={selectedDay} />
            </>
          ) : (
            <p className="type-body" style={{ color: 'var(--md-sys-color-on-surface-variant)' }}>
              Select a source to view its calendar.
            </p>
          )}
        </main>
      </div>
    </div>
  );
}
