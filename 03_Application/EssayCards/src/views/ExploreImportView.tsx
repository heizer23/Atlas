import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiFetch, isApiError } from '@platform-ui/api/client';
import ErrorCard from '@platform-ui/components/ErrorCard';
import type { ApiError } from '@platform-ui/api/types';
import { readClipboard } from '../prompts';
import { btnStyle, pageStyle, primaryBtnStyle } from '../styles';
import type { ExploreImportResult, ExplorePreview } from '../types';

// ── Explore Import View (Sprint06) ───────────────────────────────────────────
//
// Paste ChatGPT's JSON reply from a flashcard exploration. Two server round
// trips: first ?dry_run=true to get a preview (nothing written), then — only
// after the user confirms — the same body without the flag to apply it
// atomically. The pasted text is sent verbatim as the POST body (no client-side
// JSON.parse), same as IngestView / ImportExaminationsView. A rejected import
// returns a complete, copy-pasteable description in error.message.

export const EXPLORE_RESULT_PLACEHOLDER_JSON = `{
  "actions": [
    {
      "type": "save_discussion",
      "card_id": "the card_id from the exploration package",
      "discussion": {
        "exploration_question": "what I was trying to understand",
        "discussion_summary": "compact summary of the useful substance",
        "resolution": "the main conclusion or distinction reached",
        "knowledge_gap": "what I had misunderstood — or null"
      }
    }
  ]
}`;

export function ExploreImportView() {
  const navigate = useNavigate();
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [preview, setPreview] = useState<ExplorePreview | null>(null);
  const [applied, setApplied] = useState<ExploreImportResult | null>(null);
  const [clipboardMsg, setClipboardMsg] = useState<string | null>(null);
  const [errorCopied, setErrorCopied] = useState(false);

  const IMPORT_PATH = '/essaycards/flashcards/exploration/import';

  const onTextChange = (value: string) => {
    setText(value);
    // A stale preview must never be applyable against edited text.
    setPreview(null);
    setApplied(null);
  };

  const handlePasteFromClipboard = async () => {
    const res = await readClipboard();
    if ('error' in res) {
      setClipboardMsg(res.error);
      return;
    }
    onTextChange(res.text);
    setClipboardMsg(null);
  };

  const handlePreview = async () => {
    setBusy(true);
    setError(null);
    setApplied(null);
    setPreview(null);
    const res = await apiFetch<ExploreImportResult>(`${IMPORT_PATH}?dry_run=true`, {
      method: 'POST',
      body: text,
    });
    setBusy(false);
    if (isApiError(res)) {
      setError(res);
      return;
    }
    setPreview(res.preview);
  };

  const handleApply = async () => {
    setBusy(true);
    setError(null);
    const res = await apiFetch<ExploreImportResult>(IMPORT_PATH, {
      method: 'POST',
      body: text,
    });
    setBusy(false);
    if (isApiError(res)) {
      setError(res);
      setPreview(null);
      return;
    }
    setApplied(res);
    setPreview(null);
  };

  const handleCopyError = async () => {
    if (!error) return;
    try {
      await navigator.clipboard.writeText(error.error.message);
      setErrorCopied(true);
      setTimeout(() => setErrorCopied(false), 1500);
    } catch {
      setErrorCopied(false);
    }
  };

  return (
    <div style={pageStyle}>
      <button style={{ ...btnStyle, marginBottom: 12 }} onClick={() => navigate('/essaycards')}>
        ← All essays
      </button>
      <h2 style={{ marginTop: 0 }}>Import Exploration Result</h2>
      <div style={{ color: 'var(--md-sys-color-on-surface-variant)', fontSize: 13, marginBottom: 12 }}>
        Paste ChatGPT's JSON reply from a flashcard exploration (started with
        <strong> Explore </strong> on a revealed answer during review). You'll see
        a preview of exactly what will change; nothing is written until you
        confirm. The discussion is always saved; a card is updated or created only
        if the reply asks for it.
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
        <button style={btnStyle} onClick={handlePasteFromClipboard}>Paste from clipboard</button>
      </div>
      {clipboardMsg && (
        <div style={{ fontSize: 12, color: 'var(--md-sys-color-on-surface-variant)', marginBottom: 8 }}>{clipboardMsg}</div>
      )}

      <textarea
        value={text}
        onChange={e => onTextChange(e.target.value)}
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
        placeholder={EXPLORE_RESULT_PLACEHOLDER_JSON}
      />

      <div style={{ marginTop: 12, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <button style={primaryBtnStyle} disabled={busy || !text.trim()} onClick={handlePreview}>
          {busy && !preview ? 'Checking…' : 'Preview changes'}
        </button>
        {preview && (
          <button style={primaryBtnStyle} disabled={busy} onClick={handleApply}>
            {busy ? 'Applying…' : 'Apply changes'}
          </button>
        )}
      </div>

      {error && (
        <div style={{ marginTop: 16 }}>
          <ErrorCard error={error} />
          <button style={{ ...btnStyle, marginTop: 8 }} onClick={handleCopyError}>
            {errorCopied ? 'Copied' : 'Copy error for ChatGPT'}
          </button>
        </div>
      )}

      {preview && !applied && (
        <div style={{ marginTop: 16, padding: 12, borderRadius: 8, border: '1px solid var(--md-sys-color-outline-variant)', fontSize: 13 }}>
          <div style={{ fontWeight: 600, marginBottom: 8 }}>This import will:</div>

          <div style={{ marginBottom: 10 }}>
            <div style={{ fontWeight: 600 }}>• Save a discussion</div>
            <div style={{ color: 'var(--md-sys-color-on-surface-variant)' }}>
              Card <code>{preview.save_discussion.card_key}</code> — “{preview.save_discussion.exploration_question}”
            </div>
            <div style={{ color: 'var(--md-sys-color-on-surface-variant)', marginTop: 2 }}>
              Snapshots the card's current question &amp; answer.
              {preview.save_discussion.knowledge_gap
                ? ` Knowledge gap: “${preview.save_discussion.knowledge_gap}”.`
                : ' No knowledge gap recorded.'}
            </div>
          </div>

          {preview.update_card.map((u, i) => (
            <div key={`u${i}`} style={{ marginBottom: 10 }}>
              <div style={{ fontWeight: 600 }}>
                • Update card <code>{u.card_key}</code> ({u.changed_fields.join(', ')})
              </div>
              {u.changed_fields.includes('question') && (
                <div style={{ color: 'var(--md-sys-color-on-surface-variant)' }}>
                  Question: <s>{u.old.question}</s> → <strong>{u.new.question}</strong>
                </div>
              )}
              {u.changed_fields.includes('answer') && (
                <div style={{ color: 'var(--md-sys-color-on-surface-variant)' }}>
                  Answer: <s>{u.old.answer}</s> → <strong>{u.new.answer}</strong>
                </div>
              )}
              <div style={{ color: 'var(--md-sys-color-on-surface-variant)', marginTop: 2 }}>
                Reason (kept in history): “{u.reason}”. The previous version is preserved.
              </div>
            </div>
          ))}

          {preview.create_card.map((c, i) => (
            <div key={`c${i}`} style={{ marginBottom: 10 }}>
              <div style={{ fontWeight: 600 }}>
                • Create a new card in section <code>{c.section_anchor_slug}</code>
              </div>
              <div style={{ color: 'var(--md-sys-color-on-surface-variant)' }}>Q: {c.question}</div>
              <div style={{ color: 'var(--md-sys-color-on-surface-variant)' }}>A: {c.answer}</div>
              <div style={{ color: 'var(--md-sys-color-on-surface-variant)', marginTop: 2 }}>New card key <code>{c.card_key}</code>.</div>
            </div>
          ))}

          {preview.update_card.length === 0 && preview.create_card.length === 0 && (
            <div style={{ color: 'var(--md-sys-color-on-surface-variant)' }}>No card changes — the discussion is saved as-is.</div>
          )}
        </div>
      )}

      {applied && (
        <div style={{ marginTop: 16, padding: 12, borderRadius: 8, border: '1px solid var(--md-sys-color-outline-variant)', fontSize: 13 }}>
          <div style={{ fontWeight: 600, marginBottom: 8 }}>Import applied</div>
          <div style={{ color: 'var(--md-sys-color-on-surface-variant)' }}>
            Discussion saved{applied.revisions && applied.revisions.length > 0
              ? `, ${applied.revisions.length} card revision${applied.revisions.length === 1 ? '' : 's'} recorded`
              : ''}{applied.created_cards && applied.created_cards.length > 0
              ? `, ${applied.created_cards.length} new card${applied.created_cards.length === 1 ? '' : 's'} created`
              : ''}.
          </div>
        </div>
      )}
    </div>
  );
}
