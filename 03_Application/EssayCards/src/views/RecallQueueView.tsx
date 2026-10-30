import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiFetch, isApiError } from '@platform-ui/api/client';
import ErrorCard from '@platform-ui/components/ErrorCard';
import Skeleton from '@platform-ui/components/Skeleton';
import type { ApiError } from '@platform-ui/api/types';
import { buildExamClipboardText, writeClipboard } from '../prompts';
import { btnStyle, pageStyle, studyBtnStyle } from '../styles';
import type { Dataset, ExaminationPackage, RecallDueRow } from '../types';

// ── Oral Recall queue (Sprint16_RecallFSRS) ──────────────────────────────────
//
// A separate destination from the flashcard review: whole sections / essays,
// reconstructed aloud in a quiet moment, scheduled by their own FSRS state. This
// view never lists or counts flashcards. The conversation itself still happens in
// ChatGPT: "Start" copies the cold unguided package + instructions; the reply is
// imported on the shared import page.

function dueLabel(iso: string): string {
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
  if (days <= 0) return 'due today';
  return days === 1 ? 'due 1 day ago' : `due ${days} days ago`;
}

export function RecallQueueView() {
  const navigate = useNavigate();
  const [rows, setRows] = useState<RecallDueRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      const res = await apiFetch<Dataset<RecallDueRow>>('/essaycards/recall/due');
      setLoading(false);
      if (isApiError(res)) setError(res); else setRows(res.rows);
    })();
  }, []);

  const start = async (row: RecallDueRow) => {
    setBusyId(row.id);
    setMsg(null);
    const sectionParam = row.scope === 'section' ? `&section_id=${row.section_id}` : '';
    const res = await apiFetch<ExaminationPackage>(
      `/essaycards/essays/${row.essay_id}/examination-package?exam_type=unguided&scope=${row.scope}${sectionParam}`,
    );
    setBusyId(null);
    if (isApiError(res)) {
      setMsg(`Export failed: ${res.error.message}`);
      return;
    }
    const err = await writeClipboard(buildExamClipboardText(res, 'unguided'));
    setMsg(err ?? 'Copied. Paste into ChatGPT, explain the material aloud, then import its JSON reply.');
  };

  return (
    <div style={pageStyle}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, flexWrap: 'wrap', marginBottom: 4 }}>
        <h2 className="type-headline" style={{ margin: 0 }}>Oral Recall</h2>
        {!loading && !error && <span style={{ fontSize: 14 }}>{rows.length} due</span>}
      </div>
      <div style={{ fontSize: 13, color: 'var(--md-sys-color-on-surface-variant)', marginBottom: 16 }}>
        Explain a whole section or essay from memory, ideally somewhere quiet where you can speak. This is
        separate from flashcards and from guided learning.
      </div>

      {loading && <Skeleton />}
      {error && <ErrorCard error={error} />}
      {msg && <div role="status" style={{ fontSize: 13, marginBottom: 12 }}>{msg}</div>}

      {!loading && !error && rows.length === 0 && (
        <div style={{ color: 'var(--md-sys-color-on-surface-variant)', fontSize: 14 }}>
          Nothing is due. Start recall for a section from its menu in the reader; once established, it returns here
          when it is due again.
        </div>
      )}

      {rows.map(row => (
        <div
          key={row.id}
          style={{
            padding: 14, borderRadius: 'var(--radius-card, 12px)', marginBottom: 8,
            border: '1px solid var(--md-sys-color-outline-variant)', background: 'var(--md-sys-color-surface)',
            display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap',
          }}
        >
          <div style={{ flex: '1 1 220px', minWidth: 0 }}>
            <div style={{ fontWeight: 600 }}>{row.scope === 'essay' ? row.essay_title : row.section_heading}</div>
            <div style={{ fontSize: 12, color: 'var(--md-sys-color-on-surface-variant)' }}>
              {row.scope === 'essay' ? 'Whole essay' : row.essay_title} · {dueLabel(row.next_due_at)}
              {row.last_rating === 'again' ? ' · lapsed last time' : ''}
            </div>
          </div>
          <button style={studyBtnStyle} disabled={busyId !== null} onClick={() => start(row)}>
            {busyId === row.id ? 'Preparing…' : 'Start recall'}
          </button>
        </div>
      ))}

      <div style={{ marginTop: 16, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <button style={btnStyle} onClick={() => navigate('/essaycards/examinations/import')}>Import recall result →</button>
        <button style={btnStyle} onClick={() => navigate('/essaycards')}>← All essays</button>
      </div>
    </div>
  );
}
