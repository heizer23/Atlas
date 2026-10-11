import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiFetch, isApiError } from '@platform-ui/api/client';
import ErrorCard from '@platform-ui/components/ErrorCard';
import type { ApiError } from '@platform-ui/api/types';
import { readClipboard } from '../prompts';
import { btnStyle, pageStyle, primaryBtnStyle } from '../styles';
import type { QuestionUpsertResult } from '../types';

// ── Question Import View ─────────────────────────────────────────────────────
//
// Paste ChatGPT's JSON reply from a single-question export (see
// QUESTION_EXPORT_PROMPT_INTRO). Same paste/submit pattern as
// IngestView/ImportExaminationsView/ExploreImportView: the raw pasted text
// goes straight to POST /flashcards/upsert as the request body — no
// client-side JSON.parse/re-stringify — so the backend's own manual
// request.json() parse (or reject) sees exactly what was pasted.

export const QUESTION_IMPORT_PLACEHOLDER_JSON = `{
  "essay_slug": "what_can_we_know",
  "section_id": "7402691f-edbd-4408-8f1c-dbd23916e5a6",
  "card": {
    "id": "plato-appearances-6",
    "level": 3,
    "q": "In Plato's Meno, what was he trying to demonstrate with the example of the road to Larissa?",
    "a": "That a true belief can guide action just as successfully as knowledge, but knowledge is more secure because the true belief is tethered by an account of why it is correct."
  }
}`;

export function QuestionImportView() {
  const navigate = useNavigate();
  const [text, setText] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [result, setResult] = useState<QuestionUpsertResult | null>(null);
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
    const res = await apiFetch<QuestionUpsertResult>('/essaycards/flashcards/upsert', {
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
      <h2 style={{ marginTop: 0 }}>Import Question</h2>
      <div style={{ fontSize: 13, color: 'var(--md-sys-color-on-surface-variant)', marginBottom: 12 }}>
        Paste ChatGPT's JSON reply from a single-question export (started with "Export" on a question
        in that essay's question overview). Only the named card is created or updated — everything else
        in the essay is left untouched.
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
        rows={14}
        style={{
          width: '100%',
          fontFamily: 'monospace',
          fontSize: 13,
          padding: 8,
          boxSizing: 'border-box',
          border: '1px solid var(--md-sys-color-outline)',
          borderRadius: 6,
        }}
        placeholder={QUESTION_IMPORT_PLACEHOLDER_JSON}
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
        <div style={{ marginTop: 16, padding: 12, border: '1px solid var(--md-sys-color-outline)', borderRadius: 8 }}>
          <div style={{ fontWeight: 600, marginBottom: 8 }}>
            {result.created ? 'Question created' : 'Question updated'}
          </div>
          <div style={{ fontSize: 13, marginBottom: 8 }}>
            card id <code>{result.card_id}</code>, level {result.level}
          </div>
          <button style={btnStyle} onClick={() => navigate(`/essaycards/essays/${result.essay_id}/questions`)}>
            Back to question overview →
          </button>
        </div>
      )}
    </div>
  );
}
