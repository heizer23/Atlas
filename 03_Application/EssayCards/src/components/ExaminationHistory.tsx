import React, { useEffect, useState } from 'react';
import { apiFetch, isApiError } from '@platform-ui/api/client';
import ErrorCard from '@platform-ui/components/ErrorCard';
import type { ApiError } from '@platform-ui/api/types';
import { btnStyle } from '../styles';
import type { Dataset, EssayExaminationRow, GuidedSessionRow, SectionExaminationRow } from '../types';

// ── Section Examination History ────────────────────────────────────────────────
//
// Collapsed by default, fetched on first expand — a plain reverse-chronological
// list of stored results (date/score/feedback). Deliberately not a chart or
// trend analysis — that stays out of scope for now.

export function SectionExaminationHistory({ sectionId }: { sectionId: string }) {
  // Mounted only while opened from the section's "More" menu; loads on mount.
  const open = true;
  const [loaded, setLoaded] = useState(false);
  const [rows, setRows] = useState<SectionExaminationRow[]>([]);
  const [error, setError] = useState<ApiError | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const res = await apiFetch<Dataset<SectionExaminationRow>>(`/essaycards/sections/${sectionId}/examinations`);
      if (cancelled) return;
      if (isApiError(res)) setError(res); else setRows(res.rows);
      setLoaded(true);
    })();
    return () => { cancelled = true; };
  }, [sectionId]);

  return (
    <div style={{ marginTop: 8 }}>
      <div style={{ fontSize: 12, fontWeight: 600 }}>Examination history{loaded ? ` (${rows.length})` : ''}</div>
      {open && (
        <div style={{ marginTop: 8 }}>
          {error && <ErrorCard error={error} />}
          {loaded && !error && rows.length === 0 && (
            <div style={{ color: 'var(--md-sys-color-on-surface-variant)', fontSize: 13 }}>Not examined yet.</div>
          )}
          {rows.map(r => (
            <div
              key={r.id}
              style={{
                padding: 8,
                borderRadius: 6,
                border: '1px solid var(--md-sys-color-outline-variant)',
                marginBottom: 6,
                fontSize: 13,
              }}
            >
              <div style={{ fontWeight: 600 }}>
                {new Date(r.examined_at).toLocaleDateString()} — score {r.score}/6
                {' · '}
                <span style={{ textTransform: 'capitalize', fontWeight: 400, color: 'var(--md-sys-color-on-surface-variant)' }}>{r.exam_type}</span>
                {' · '}
                <span>{r.passed ? 'Passed' : 'Not passed'}</span>
              </div>
              {r.feedback && <div style={{ color: 'var(--md-sys-color-on-surface-variant)', marginTop: 4 }}>{r.feedback}</div>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// Guided-learning sessions of one section (GET /sections/{id}/guided-sessions):
// the AI's recommendation next to what the learner decided, plus open gaps.
export function SectionGuidedHistory({ sectionId }: { sectionId: string }) {
  const [loaded, setLoaded] = useState(false);
  const [rows, setRows] = useState<GuidedSessionRow[]>([]);
  const [error, setError] = useState<ApiError | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const res = await apiFetch<Dataset<GuidedSessionRow>>(`/essaycards/sections/${sectionId}/guided-sessions`);
      if (cancelled) return;
      if (isApiError(res)) setError(res); else setRows(res.rows);
      setLoaded(true);
    })();
    return () => { cancelled = true; };
  }, [sectionId]);

  return (
    <div style={{ marginTop: 8 }}>
      <div style={{ fontSize: 12, fontWeight: 600 }}>Guided sessions{loaded ? ` (${rows.length})` : ''}</div>
      <div style={{ marginTop: 8 }}>
        {error && <ErrorCard error={error} />}
        {loaded && !error && rows.length === 0 && (
          <div style={{ color: 'var(--md-sys-color-on-surface-variant)', fontSize: 13 }}>No guided session yet.</div>
        )}
        {rows.map(r => (
          <div
            key={r.id}
            style={{ padding: 8, borderRadius: 6, border: '1px solid var(--md-sys-color-outline-variant)', marginBottom: 6, fontSize: 13 }}
          >
            <div style={{ fontWeight: 600 }}>
              {new Date(r.session_at).toLocaleDateString()} — Level {r.level}
              {' · '}
              <span style={{ fontWeight: 400, color: 'var(--md-sys-color-on-surface-variant)' }}>
                AI: {r.recommendation} · you: {r.learner_decision}
                {r.advanced_to ? ` → Level ${r.advanced_to} reached` : ''}
              </span>
            </div>
            <div style={{ color: 'var(--md-sys-color-on-surface-variant)', marginTop: 4 }}>{r.rationale}</div>
            {r.gaps_text && <div style={{ marginTop: 4, whiteSpace: 'pre-line' }}>Open gaps: {r.gaps_text}</div>}
          </div>
        ))}
      </div>
    </div>
  );
}

// Sprint14: full-essay oral attempts (GET /essays/{id}/examinations), same
// collapsible list as SectionExaminationHistory, pass/fail per attempt.
export function EssayExaminationHistory({ essayId }: { essayId: string }) {
  const [open, setOpen] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [rows, setRows] = useState<EssayExaminationRow[]>([]);
  const [error, setError] = useState<ApiError | null>(null);

  const handleToggle = async () => {
    const next = !open;
    setOpen(next);
    if (next && !loaded) {
      const res = await apiFetch<Dataset<EssayExaminationRow>>(`/essaycards/essays/${essayId}/examinations`);
      if (isApiError(res)) setError(res); else setRows(res.rows);
      setLoaded(true);
    }
  };

  return (
    <div style={{ marginBottom: 12 }}>
      <button style={{ ...btnStyle, fontSize: 12 }} onClick={handleToggle}>
        {open ? '▾' : '▸'} Essay oral history{loaded ? ` (${rows.length})` : ''}
      </button>
      {open && (
        <div style={{ marginTop: 8 }}>
          {error && <ErrorCard error={error} />}
          {loaded && !error && rows.length === 0 && (
            <div style={{ color: 'var(--md-sys-color-on-surface-variant)', fontSize: 13 }}>No whole-essay oral exam yet.</div>
          )}
          {rows.map(r => (
            <div
              key={r.id}
              style={{ padding: 8, borderRadius: 6, border: '1px solid var(--md-sys-color-outline-variant)', marginBottom: 6, fontSize: 13 }}
            >
              <div style={{ fontWeight: 600 }}>
                {new Date(r.examined_at).toLocaleDateString()} — score {r.score}/6
                {' · '}
                <span style={{ textTransform: 'capitalize', fontWeight: 400, color: 'var(--md-sys-color-on-surface-variant)' }}>{r.exam_type}</span>
                {' · '}
                <span>{r.passed ? 'Passed' : 'Not passed'}</span>
              </div>
              {r.feedback && <div style={{ color: 'var(--md-sys-color-on-surface-variant)', marginTop: 4 }}>{r.feedback}</div>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
