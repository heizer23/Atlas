import React, { useEffect, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { apiFetch, isApiError } from '@platform-ui/api/client';
import ErrorCard from '@platform-ui/components/ErrorCard';
import Skeleton from '@platform-ui/components/Skeleton';
import type { ApiError } from '@platform-ui/api/types';
import { buildGenerateFlashcardsClipboardText, readClipboard, writeClipboard } from '../prompts';
import { btnStyle, pageStyle, primaryBtnStyle } from '../styles';
import type { GenerateFlashcardsPackage, QuestionUpsertResult } from '../types';

// ── Generate flashcards from a nugget (Sprint09_Nuggets) ────────────────────
//
// Self-contained, same shape as NuggetAuthoringImportView above. Import
// issues one POST /flashcards/upsert per generated card, SEQUENTIALLY, each
// with nugget_id pre-set to the source nugget — no new bulk/atomic backend
// endpoint (10_architecture.json risks: not atomic across the batch). Reports
// per-card success/failure so the user can retry only the failed ones.

export const GENERATE_FLASHCARDS_JSON_PLACEHOLDER = `{
  "cards": [
    { "level": 2, "q": "...", "a": "..." }
  ]
}`;

export interface GeneratedCardResult {
  q: string;
  ok: boolean;
  message: string;
}

export function GenerateFlashcardsImportView() {
  const { id: nuggetId } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const essayId = searchParams.get('essay_id') ?? '';
  const sectionId = searchParams.get('section_id') ?? '';

  const [pkg, setPkg] = useState<GenerateFlashcardsPackage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  const [clipboardMsg, setClipboardMsg] = useState<string | null>(null);
  const [text, setText] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [results, setResults] = useState<GeneratedCardResult[] | null>(null);

  useEffect(() => {
    (async () => {
      if (!nuggetId || !essayId || !sectionId) {
        setLoading(false);
        setError({ error: { code: 'VALIDATION_ERROR', message: 'nugget id, essay_id and section_id are required', request_id: '' } });
        return;
      }
      setLoading(true);
      const qs = new URLSearchParams({ essay_id: essayId, section_id: sectionId });
      const res = await apiFetch<GenerateFlashcardsPackage>(
        `/essaycards/nuggets/${nuggetId}/generate-flashcards-package?${qs.toString()}`,
      );
      setLoading(false);
      if (isApiError(res)) { setError(res); return; }
      setPkg(res);
    })();
  }, [nuggetId, essayId, sectionId]);

  const handleCopyPrompt = async () => {
    if (!pkg) return;
    const err = await writeClipboard(buildGenerateFlashcardsClipboardText(pkg));
    setClipboardMsg(
      err ?? 'Copied. Paste into ChatGPT (or similar), generate the cards, then paste its JSON reply below and Submit.',
    );
  };

  const handlePasteFromClipboard = async () => {
    const res = await readClipboard();
    if ('error' in res) { setClipboardMsg(res.error); return; }
    setText(res.text);
    setClipboardMsg(null);
  };

  const handleSubmit = async () => {
    setSubmitError(null);
    setResults(null);
    let parsed: any;
    try {
      parsed = JSON.parse(text);
    } catch {
      setSubmitError('That is not valid JSON.');
      return;
    }
    if (!Array.isArray(parsed?.cards) || parsed.cards.length === 0) {
      setSubmitError('Expected a JSON object of the shape {"cards": [{"level", "q", "a"}, ...]}.');
      return;
    }

    setSubmitting(true);
    const outcomes: GeneratedCardResult[] = [];
    // Sequential — reuses the existing single-card endpoint, one POST per
    // card, not atomic across the batch (see module docstring).
    for (const card of parsed.cards) {
      const res = await apiFetch<QuestionUpsertResult>('/essaycards/flashcards/upsert', {
        method: 'POST',
        body: JSON.stringify({
          essay_slug: pkg!.context.essay_slug,
          section_id: pkg!.context.section_id,
          card: { level: card?.level, q: card?.q, a: card?.a, nugget_id: nuggetId },
        }),
      });
      outcomes.push(
        isApiError(res)
          ? { q: String(card?.q ?? '(unknown)'), ok: false, message: res.error.message }
          : { q: String(card?.q ?? '(unknown)'), ok: true, message: 'Saved' },
      );
    }
    setSubmitting(false);
    setResults(outcomes);
  };

  return (
    <div style={pageStyle}>
      <button style={{ ...btnStyle, marginBottom: 12 }} onClick={() => navigate(`/essaycards/essays/${essayId}`)}>
        ← Back to reader
      </button>
      <h2 style={{ marginTop: 0 }}>Generate Flashcards From Nugget</h2>

      {loading && <Skeleton />}
      {error && <ErrorCard error={error} />}

      {pkg && (
        <>
          <div style={{ color: 'var(--md-sys-color-on-surface-variant)', fontSize: 13, marginBottom: 12 }}>
            Generating cards for "{pkg.nugget.title}" ({pkg.nugget.nugget_key}) — {pkg.existing_flashcards.length} existing card(s).
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
            placeholder={GENERATE_FLASHCARDS_JSON_PLACEHOLDER}
          />

          <div style={{ marginTop: 12 }}>
            <button style={primaryBtnStyle} disabled={submitting || !text.trim()} onClick={handleSubmit}>
              {submitting ? 'Submitting…' : 'Submit'}
            </button>
          </div>

          {submitError && <div style={{ marginTop: 12, fontSize: 13, color: '#b00020' }}>{submitError}</div>}

          {results && (
            <div style={{ marginTop: 16 }}>
              <div style={{ fontWeight: 600, marginBottom: 8 }}>
                {results.filter(r => r.ok).length} / {results.length} card(s) saved
              </div>
              {results.map((r, i) => (
                <div key={i} style={{ fontSize: 13, color: r.ok ? '#3a7a3a' : '#b00020', marginBottom: 4 }}>
                  {r.ok ? '✓' : '✗'} {r.q} — {r.message}
                </div>
              ))}
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
