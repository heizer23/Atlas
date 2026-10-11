import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiFetch, isApiError } from '@platform-ui/api/client';
import ErrorCard from '@platform-ui/components/ErrorCard';
import type { ApiError } from '@platform-ui/api/types';
import { readClipboard } from '../prompts';
import { btnStyle, pageStyle, primaryBtnStyle } from '../styles';

// ── Import Examinations View ───────────────────────────────────────────────────

export interface ImportResultEffect {
  effect: 'section_guided_unlocked' | 'section_unguided_passed' | 'essay_guided_passed'
    | 'essay_unguided_passed' | 'essay_unguided_failed_cascade';
  section_id?: string;
  essay_id?: string;
  cards_flagged?: number;
}

export interface ImportSummary {
  imported: number;
  results: {
    id: string;
    scope: 'section' | 'essay';
    essay_id: string;
    section_id: string | null;
    examined_at: string;
    score: number;
    passed: boolean;
    score_percent: number;
    effects: ImportResultEffect[];
  }[];
  // One entry per unguided-essay failure cascade that fired in this import.
  revalidation: { essay_id: string; cards_flagged: number }[];
}

export const EFFECT_TEXT: Record<ImportResultEffect['effect'], string> = {
  section_guided_unlocked: 'Section flashcards unlocked',
  section_unguided_passed: 'Section unguided oral passed',
  essay_guided_passed: 'Guided essay oral passed',
  essay_unguided_passed: 'Unguided essay oral passed',
  essay_unguided_failed_cascade: 'Essay mastery invalidated',
};

export const EXAM_RESULT_PLACEHOLDER_JSON = `{
  "results": [
    {
      "scope": "section",
      "essay_slug": "the essay's slug, from the examination package",
      "section_anchor_slug": "the section's anchor_slug, from the examination package",
      "section_version": "copied verbatim from the section's section_version in the package",
      "examined_at": "2026-08-28T14:30:00Z",
      "question": "summary of what was asked",
      "answer_transcript": "summary or transcript of the answer given",
      "score": 5,
      "exam_type": "guided",
      "feedback": "optional — one or two sentences, or omit/null"
    },
    {
      "scope": "essay",
      "essay_slug": "a whole-essay result: no section_anchor_slug / section_version",
      "examined_at": "2026-08-28T15:00:00Z",
      "question": "summary of what was asked",
      "answer_transcript": "summary or transcript of the answer given",
      "score": 5,
      "exam_type": "unguided",
      "feedback": null
    }
  ]
}`;

export function ImportExaminationsView() {
  const navigate = useNavigate();
  const [text, setText] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [result, setResult] = useState<ImportSummary | null>(null);
  const [clipboardMsg, setClipboardMsg] = useState<string | null>(null);

  const handlePasteFromClipboard = async () => {
    const res = await readClipboard();
    if ('error' in res) {
      setClipboardMsg(res.error);
      return;
    }
    setText(res.text);
    setClipboardMsg(null);
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    setError(null);
    setResult(null);
    // Send the textarea's raw string content directly — let the backend's
    // manual request.json() parse (or reject) exactly what was pasted.
    const res = await apiFetch<ImportSummary>('/essaycards/examinations/import', {
      method: 'POST',
      body: text,
    });
    setSubmitting(false);
    if (isApiError(res)) {
      setError(res);
      return;
    }
    setResult(res);
  };

  return (
    <div style={pageStyle}>
      <button style={{ ...btnStyle, marginBottom: 12 }} onClick={() => navigate('/essaycards')}>
        ← All essays
      </button>
      <h2 style={{ marginTop: 0 }}>Import Exam Results</h2>
      <div style={{ color: 'var(--md-sys-color-on-surface-variant)', fontSize: 13, marginBottom: 12 }}>
        Paste ChatGPT's JSON reply from an oral examination (started with "Export for examination" on an
        essay's page). Each result is stored as a new historical record — importing never overwrites a
        previous examination, so re-examining a section months later just adds another entry.
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
        <button style={btnStyle} onClick={handlePasteFromClipboard}>Paste from clipboard</button>
      </div>
      {clipboardMsg && (
        <div style={{ fontSize: 12, color: 'var(--md-sys-color-on-surface-variant)', marginBottom: 8 }}>{clipboardMsg}</div>
      )}

      <textarea
        value={text}
        onChange={e => setText(e.target.value)}
        rows={16}
        style={{
          width: '100%',
          fontFamily: 'monospace',
          fontSize: 13,
          padding: 8,
          boxSizing: 'border-box',
          border: '1px solid var(--md-sys-color-outline)',
          borderRadius: 6,
        }}
        placeholder={EXAM_RESULT_PLACEHOLDER_JSON}
      />

      <div style={{ marginTop: 12 }}>
        <button style={primaryBtnStyle} disabled={submitting || !text.trim()} onClick={handleSubmit}>
          {submitting ? 'Submitting…' : 'Submit'}
        </button>
      </div>

      {error && (
        <div style={{ marginTop: 16 }}>
          <ErrorCard error={error} />
        </div>
      )}

      {result && (
        <div style={{
          marginTop: 16,
          padding: 12,
          borderRadius: 8,
          border: '1px solid var(--md-sys-color-outline-variant)',
        }}>
          <div style={{ fontWeight: 600, marginBottom: 8 }}>Import succeeded</div>
          <div style={{ fontSize: 13, color: 'var(--md-sys-color-on-surface-variant)' }}>
            {result.imported} examination result{result.imported === 1 ? '' : 's'} stored.
          </div>
          <ul style={{ fontSize: 13, margin: '8px 0 0', paddingLeft: 18 }}>
            {result.results.map(r => (
              <li key={r.id}>
                {r.scope === 'essay' ? 'Whole essay' : 'Section'}: score {r.score}/6 ({r.score_percent}%) —{' '}
                <strong>{r.passed ? 'Passed' : 'Not passed'}</strong>
                {r.effects.length > 0 && <> · {r.effects.map(e => EFFECT_TEXT[e.effect]).join(', ')}</>}
              </li>
            ))}
          </ul>
          {result.revalidation.map(rv => (
            <div
              key={rv.essay_id}
              role="alert"
              style={{
                marginTop: 12, padding: 10, borderRadius: 6,
                background: 'var(--md-sys-color-error-container)', color: 'var(--md-sys-color-on-surface)',
              }}
            >
              <div style={{ fontWeight: 600 }}>Mastery invalidated</div>
              <div style={{ fontSize: 13, margin: '4px 0 8px' }}>
                The unguided essay oral was failed: Violet and Blue were removed and every section's unguided
                pass was cleared. {rv.cards_flagged} card{rv.cards_flagged === 1 ? '' : 's'} need revalidation.
              </div>
              <button
                style={primaryBtnStyle}
                onClick={() => navigate(`/essaycards/review?revalidate=1&essay_id=${rv.essay_id}`)}
              >
                Start revalidation
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
