/**
 * CalendarPage — Unified Calendar entry point.
 *
 * Responsibilities:
 * - Fetch sources list on mount (GET /api/chronicle/calendar/sources)
 * - Maintain sources[] state; derive selectedSources = sources.filter(s => s.selected)
 * - Pass selectedCount and maxSelected (4) to SourceChooser
 * - Render SwimlaneRenderer when selectedSources.length > 0
 * - Show a prompt text when no sources are selected
 * - Handle source selection toggle (PATCH /api/chronicle/calendar/sources)
 *   confirm-then-apply: wait for server response before updating state; no rollback
 * - Render DayDetailView for the selected day
 */

import { useState, useEffect, useMemo } from 'react';
import { apiFetch, isApiError } from '@platform-ui/api/client';
import ErrorCard from '@platform-ui/components/ErrorCard';
import Skeleton from '@platform-ui/components/Skeleton';
import type { ApiError } from '@platform-ui/api/types';
import type { SourceListRow, CalendarEventRow } from './types';
import SourceChooser from './SourceChooser';
import SwimlaneRenderer from './SwimlaneRenderer';
import DayDetailView from './DayDetailView';

const MAX_SELECTED = 4;

export default function CalendarPage() {
  const [sources,     setSources]     = useState<SourceListRow[]>([]);
  const [selectedDay, setSelectedDay] = useState<CalendarEventRow | null>(null);
  const [loading,     setLoading]     = useState(true);
  const [error,       setError]       = useState<ApiError | null>(null);
  const [toggling,    setToggling]    = useState(false);

  // Memoised — stable reference prevents SwimlaneRenderer's useEffect from
  // re-firing (and re-fetching) on unrelated CalendarPage re-renders (e.g. setSelectedDay).
  const selectedSources = useMemo(() => sources.filter((s) => s.selected), [sources]);

  // ── Load sources on mount ────────────────────────────────────────────────────

  useEffect(() => {
    setLoading(true);
    setError(null);

    apiFetch<SourceListRow[]>('/chronicle/calendar/sources').then((res) => {
      if (isApiError(res)) {
        setError(res as ApiError);
      } else {
        setSources(res as SourceListRow[]);
      }
      setLoading(false);
    });
  }, []);

  // ── Toggle handler (confirm-then-apply) ──────────────────────────────────────

  async function handleToggle(application: string, source_label: string, selected: boolean) {
    if (toggling) return;
    setToggling(true);

    const res = await apiFetch<{ application: string; source_label: string; selected: boolean }>(
      '/chronicle/calendar/sources',
      {
        method: 'PATCH',
        body:   JSON.stringify({ application, source_label, selected }),
      },
    );

    setToggling(false);

    if (isApiError(res)) {
      // Server rejected — surface error, leave selection state unchanged
      setError(res as ApiError);
      return;
    }

    const updated = res as { application: string; source_label: string; selected: boolean };

    // Update sources list only after server confirms the change
    setSources((prev) =>
      prev.map((s) =>
        s.application === updated.application && s.source_label === updated.source_label
          ? { ...s, selected: updated.selected }
          : s,
      ),
    );

    // Clear selected day when selection changes (stale detail from a removed source)
    setSelectedDay(null);
  }

  // ── Day click ────────────────────────────────────────────────────────────────

  function handleDayClick(row: CalendarEventRow) {
    setSelectedDay(row);
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

      {/* Non-fatal error banner (e.g. PATCH failure) */}
      {error && (
        <div style={{ marginBottom: 'var(--space-sm)' }}>
          <ErrorCard error={error} />
        </div>
      )}

      {/* Chooser always above chart — column layout on all screen sizes */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>

        {/* Source chooser panel */}
        <aside>
          <h2 className="type-title" style={{ marginBottom: 'var(--space-sm)' }}>
            Sources
          </h2>
          <SourceChooser
            sources={sources}
            onToggle={handleToggle}
            selectedCount={selectedSources.length}
            maxSelected={MAX_SELECTED}
          />
        </aside>

        {/* Day detail — above the grid so it is visible without scrolling */}
        <DayDetailView row={selectedDay} />

        {/* Swimlane / empty state area */}
        <main>
          {selectedSources.length > 0 ? (
            <SwimlaneRenderer
              sources={selectedSources}
              onDayClick={handleDayClick}
            />
          ) : (
            <p
              className="type-body"
              style={{ color: 'var(--md-sys-color-on-surface-variant)' }}
            >
              Select a source to view its calendar.
            </p>
          )}
        </main>
      </div>
    </div>
  );
}
