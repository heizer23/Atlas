import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiFetch, isApiError } from '@platform-ui/api/client';
import ErrorCard from '@platform-ui/components/ErrorCard';
import type { ApiError } from '@platform-ui/api/types';
import { readClipboard } from '../prompts';
import { btnStyle, pageStyle, primaryBtnStyle } from '../styles';

// ── Import Guided Session (Levels 1-6) ────────────────────────────────────────
//
// Two steps so the LEARNER confirms advancement: (1) paste the AI's reply and
// preview its recommendation / strengths / gaps (nothing is stored yet);
// (2) choose "Advance" or "Stay" — the choice is sent as learner_decision.
// Advancing against an AI "continue" recommendation needs one more confirmation.

interface Gap { text: string; serious: boolean }
interface GuidedReply {
  level: number;
  recommendation: 'advance' | 'continue';
  rationale: string;
  demonstrated: string;
  gaps: Gap[];
  unguided_suggested?: boolean;
}

interface GuidedImportResult {
  level: number;
  learner_decision: 'advance' | 'stay';
  advanced_to: number | null;
  completed_level: number;
  unguided_suggested: boolean;
  effects: { effect: string }[];
}

const MAX_LEVEL = 6;

// Returns the parsed reply, or a message. Only a light preview parse: the
// backend validates the full shape when the learner confirms.
function parseReply(text: string): { reply: GuidedReply; raw: unknown } | { problem: string } {
  let raw: unknown;
  try {
    raw = JSON.parse(text);
  } catch {
    return { problem: 'That is not valid JSON.' };
  }
  const s = (raw as { guided_session?: GuidedReply } | null)?.guided_session;
  if (!s || typeof s !== 'object' || typeof s.level !== 'number' || !['advance', 'continue'].includes(s.recommendation)) {
    return { problem: 'Expected an object with a "guided_session" containing level and recommendation.' };
  }
  return { reply: { ...s, gaps: Array.isArray(s.gaps) ? s.gaps : [] }, raw };
}

export function ImportGuidedView() {
  const navigate = useNavigate();
  const [text, setText] = useState('');
  const [parsed, setParsed] = useState<{ reply: GuidedReply; raw: unknown } | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [clipboardMsg, setClipboardMsg] = useState<string | null>(null);
  const [confirmOverride, setConfirmOverride] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [result, setResult] = useState<GuidedImportResult | null>(null);

  const handlePaste = async () => {
    const res = await readClipboard();
    if ('error' in res) {
      setClipboardMsg(res.error);
      return;
    }
    setText(res.text);
    setClipboardMsg(null);
  };

  const handlePreview = () => {
    setError(null);
    setResult(null);
    setConfirmOverride(false);
    const p = parseReply(text);
    if ('problem' in p) {
      setParsed(null);
      setProblem(p.problem);
      return;
    }
    setProblem(null);
    setParsed(p);
  };

  const decide = async (decision: 'advance' | 'stay') => {
    if (!parsed) return;
    setSubmitting(true);
    setError(null);
    const res = await apiFetch<GuidedImportResult>('/essaycards/guided/import', {
      method: 'POST',
      body: JSON.stringify({ ...(parsed.raw as object), learner_decision: decision }),
    });
    setSubmitting(false);
    if (isApiError(res)) {
      setError(res);
      return;
    }
    setResult(res);
    setParsed(null);
    setText('');
  };

  const reply = parsed?.reply ?? null;
  const against = reply?.recommendation === 'continue';
  const hasSerious = !!reply?.gaps.some(g => g.serious);

  return (
    <div style={pageStyle}>
      <button style={{ ...btnStyle, marginBottom: 12 }} onClick={() => navigate('/essaycards')}>
        ← All essays
      </button>
      <h2 style={{ marginTop: 0 }}>Import Guided Session</h2>
      <div style={{ color: 'var(--md-sys-color-on-surface-variant)', fontSize: 13, marginBottom: 12 }}>
        Paste the JSON reply from a guided learning session (started with "Guided learning" in a section's menu).
        You see the AI's recommendation first; nothing is stored until you choose to advance or stay.
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
        <button style={btnStyle} onClick={handlePaste}>Paste from clipboard</button>
      </div>
      {clipboardMsg && (
        <div style={{ fontSize: 12, color: 'var(--md-sys-color-on-surface-variant)', marginBottom: 8 }}>{clipboardMsg}</div>
      )}
      <textarea
        value={text}
        onChange={e => { setText(e.target.value); setParsed(null); }}
        rows={12}
        style={{
          width: '100%', fontFamily: 'monospace', fontSize: 13, padding: 8, boxSizing: 'border-box',
          border: '1px solid var(--md-sys-color-outline)', borderRadius: 6,
        }}
        placeholder='{ "guided_session": { "essay_slug": "...", "section_anchor_slug": "...", "level": 1, ... } }'
      />
      <div style={{ marginTop: 12 }}>
        <button style={primaryBtnStyle} disabled={!text.trim()} onClick={handlePreview}>Review recommendation</button>
      </div>
      {problem && <div role="alert" style={{ marginTop: 12, color: 'var(--md-sys-color-error)', fontSize: 13 }}>{problem}</div>}

      {reply && (
        <div style={{ marginTop: 16, padding: 12, borderRadius: 8, border: '1px solid var(--md-sys-color-outline-variant)' }}>
          <div style={{ fontWeight: 600 }}>
            Level {reply.level} — AI recommends: {reply.recommendation === 'advance'
              ? (reply.level < MAX_LEVEL ? `advance to Level ${reply.level + 1}` : 'level complete')
              : `continue at Level ${reply.level}`}
          </div>
          <div style={{ fontSize: 13, margin: '8px 0' }}>{reply.rationale}</div>
          <div style={{ fontSize: 13 }}><strong>Demonstrated:</strong> {reply.demonstrated}</div>
          {reply.gaps.length > 0 && (
            <ul style={{ fontSize: 13, margin: '8px 0 0', paddingLeft: 18 }}>
              {reply.gaps.map((g, i) => (
                <li key={i}>{g.serious ? <strong>Serious gap: </strong> : 'Gap: '}{g.text}</li>
              ))}
            </ul>
          )}
          {reply.unguided_suggested && (
            <div style={{ fontSize: 13, marginTop: 8 }}>The AI suggests trying an unguided oral.</div>
          )}

          {against && confirmOverride && (
            <div role="alert" style={{ marginTop: 12, fontSize: 13 }}>
              The AI recommended continuing{hasSerious ? ' because of a serious gap' : ''}. Advance anyway?
            </div>
          )}
          <div style={{ display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap' }}>
            {(!against || !confirmOverride) && (
              <button
                style={against ? btnStyle : primaryBtnStyle}
                disabled={submitting}
                onClick={() => (against ? setConfirmOverride(true) : decide('advance'))}
              >
                {reply.level < MAX_LEVEL ? `Advance to Level ${reply.level + 1}` : 'Complete Level 6'}
              </button>
            )}
            {against && confirmOverride && (
              <button style={primaryBtnStyle} disabled={submitting} onClick={() => decide('advance')}>
                Yes, advance anyway
              </button>
            )}
            <button style={against ? primaryBtnStyle : btnStyle} disabled={submitting} onClick={() => decide('stay')}>
              Stay at Level {reply.level}
            </button>
          </div>
        </div>
      )}

      {error && <div style={{ marginTop: 16 }}><ErrorCard error={error} /></div>}

      {result && (
        <div style={{ marginTop: 16, padding: 12, borderRadius: 8, border: '1px solid var(--md-sys-color-outline-variant)' }}>
          <div style={{ fontWeight: 600, marginBottom: 6 }}>
            {result.advanced_to ? `Level ${result.advanced_to} reached` : 'Session recorded'}
          </div>
          <div style={{ fontSize: 13 }}>
            Guided progress: Level {result.completed_level} of {MAX_LEVEL}.
            {result.effects.some(e => e.effect === 'section_guided_unlocked') && ' Section flashcards unlocked.'}
            {result.unguided_suggested && ' An unguided oral is a good next step.'}
          </div>
          <div style={{ marginTop: 8 }}>
            <button style={btnStyle} onClick={() => navigate('/essaycards')}>Back to essays</button>
          </div>
        </div>
      )}
    </div>
  );
}
