import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { apiFetch, isApiError } from '@platform-ui/api/client';
import ErrorCard from '@platform-ui/components/ErrorCard';
import Skeleton from '@platform-ui/components/Skeleton';
import type { ApiError } from '@platform-ui/api/types';
import { buildNuggetAuthoringClipboardText, readClipboard, writeClipboard } from '../prompts';
import { btnStyle, pageStyle, primaryBtnStyle } from '../styles';
import type { NuggetAuthoringPackage, NuggetUpsertResult } from '../types';

// ── Nugget authoring import view (Sprint09_Nuggets) ─────────────────────────
//
// Self-contained: fetches its own export package (GET /nuggets/authoring-
// package) on mount and offers both the "Copy prompt" step and the
// paste-JSON-reply/submit step on one page — unlike the essay/section/
// question export flows (which fetch+copy from a *source* page, e.g.
// ReaderView, then toggle to a *separate* Import view), a brand-new nugget
// has no existing "source" page to fetch+copy from. Reached from ReaderView's
// "+ New nugget" button (nugget_id omitted) or NuggetPanel's "Edit nugget"
// button (nugget_id set).

export const NUGGET_JSON_PLACEHOLDER = `{
  "nugget_key": "...",
  "title": "...",
  "body_markdown": "..."
}`;

export function NuggetAuthoringImportView() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const essayId = searchParams.get('essay_id') ?? '';
  const sectionId = searchParams.get('section_id') ?? '';
  const nuggetId = searchParams.get('nugget_id');

  const [pkg, setPkg] = useState<NuggetAuthoringPackage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  const [clipboardMsg, setClipboardMsg] = useState<string | null>(null);
  const [text, setText] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<ApiError | null>(null);
  const [result, setResult] = useState<NuggetUpsertResult | null>(null);

  useEffect(() => {
    (async () => {
      if (!essayId || !sectionId) {
        setLoading(false);
        setError({ error: { code: 'VALIDATION_ERROR', message: 'essay_id and section_id are required', request_id: '' } });
        return;
      }
      setLoading(true);
      const qs = new URLSearchParams({ essay_id: essayId, section_id: sectionId });
      if (nuggetId) qs.set('nugget_id', nuggetId);
      const res = await apiFetch<NuggetAuthoringPackage>(`/essaycards/nuggets/authoring-package?${qs.toString()}`);
      setLoading(false);
      if (isApiError(res)) { setError(res); return; }
      setPkg(res);
    })();
  }, [essayId, sectionId, nuggetId]);

  const handleCopyPrompt = async () => {
    if (!pkg) return;
    const err = await writeClipboard(buildNuggetAuthoringClipboardText(pkg));
    setClipboardMsg(
      err ??
        'Copied. Paste into ChatGPT (or similar), have it draft/revise the nugget, then paste its JSON reply below and Submit.',
    );
  };

  const handlePasteFromClipboard = async () => {
    const res = await readClipboard();
    if ('error' in res) { setClipboardMsg(res.error); return; }
    setText(res.text);
    setClipboardMsg(null);
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    setSubmitError(null);
    setResult(null);
    const res = await apiFetch<NuggetUpsertResult>('/essaycards/nuggets/upsert', {
      method: 'POST',
      body: text,
    });
    setSubmitting(false);
    if (isApiError(res)) { setSubmitError(res); return; }
    setResult(res);
  };

  return (
    <div style={pageStyle}>
      <button style={{ ...btnStyle, marginBottom: 12 }} onClick={() => navigate(`/essaycards/essays/${essayId}`)}>
        ← Back to reader
      </button>
      <h2 style={{ marginTop: 0 }}>{pkg?.nugget ? 'Edit Nugget' : 'New Nugget'}</h2>

      {loading && <Skeleton />}
      {error && <ErrorCard error={error} />}

      {pkg && (
        <>
          <div style={{ color: 'var(--md-sys-color-on-surface-variant)', fontSize: 13, marginBottom: 12 }}>
            {pkg.nugget
              ? `Revising "${pkg.nugget.title}" (${pkg.nugget.nugget_key}).`
              : 'Drafting a brand-new nugget, in the context of this essay/section.'}
            {' '}Copy the prompt, discuss/draft with ChatGPT (or similar), then paste its JSON reply below.
          </div>
          <div style={{ display: 'flex', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
            <button style={btnStyle} onClick={handleCopyPrompt}>Copy prompt</button>
            <button style={btnStyle} onClick={handlePasteFromClipboard}>Paste from clipboard</button>
          </div>
          {clipboardMsg && <div style={{ fontSize: 12, color: 'var(--md-sys-color-on-surface-variant)', marginBottom: 8 }}>{clipboardMsg}</div>}

          <textarea
            value={text}
            onChange={e => setText(e.target.value)}
            rows={12}
            style={{
              width: '100%', fontFamily: 'monospace', fontSize: 13, padding: 8,
              boxSizing: 'border-box', border: '1px solid var(--md-sys-color-outline)', borderRadius: 6,
            }}
            placeholder={NUGGET_JSON_PLACEHOLDER}
          />

          <div style={{ marginTop: 12 }}>
            <button style={primaryBtnStyle} disabled={submitting || !text.trim()} onClick={handleSubmit}>
              {submitting ? 'Submitting…' : 'Submit'}
            </button>
          </div>

          {submitError && <div style={{ marginTop: 16 }}><ErrorCard error={submitError} /></div>}

          {result && (
            <div style={{ marginTop: 16, padding: 12, borderRadius: 8, border: '1px solid var(--md-sys-color-outline-variant)' }}>
              <div style={{ fontWeight: 600, marginBottom: 8 }}>
                {result.created ? 'Nugget created' : 'Nugget updated'}
              </div>
              <div style={{ fontSize: 13, color: 'var(--md-sys-color-on-surface-variant)' }}>
                {result.title} ({result.nugget_key})
              </div>
              <button
                style={{ ...btnStyle, marginTop: 12 }}
                onClick={() => navigate(`/essaycards/essays/${essayId}`)}
              >
                Back to reader
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
