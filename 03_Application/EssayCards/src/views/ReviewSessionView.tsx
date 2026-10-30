import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import { apiFetch, isApiError } from '@platform-ui/api/client';
import ErrorCard from '@platform-ui/components/ErrorCard';
import Skeleton from '@platform-ui/components/Skeleton';
import type { ApiError } from '@platform-ui/api/types';
import { ReviewStatsPanel } from '../components/ReviewStatsPanel';
import { formatInterval } from '../format';
import { NuggetPanel } from '../nuggets';
import { buildExploreClipboardText, writeClipboard } from '../prompts';
import { SERIF, eyebrowStyle, flipBtnStyle, gradeBtnAgainStyle, gradeBtnGoodStyle, gradeBtnStyle, gradeStyleFor, iconBtnStyle, jumpBtnStyle, pageStyle, reviewCardStyle } from '../styles';
import type { Dataset, DueCardRow, ExplorationPackage, Grade, GradePreviewRow, ReviewResult } from '../types';

// ── Review Session View ───────────────────────────────────────────────────────

export const diagFrameStyle: React.CSSProperties = {
  marginTop: 12,
  border: '1px solid var(--md-sys-color-outline-variant)',
  borderRadius: 8,
  padding: '8px 12px',
  fontSize: 12,
  color: 'var(--md-sys-color-on-surface-variant)',
  display: 'flex',
  flexDirection: 'column',
  gap: 4,
};

const deckLayer: React.CSSProperties = {
  position: 'absolute', height: 20, borderRadius: '0 0 18px 18px',
  background: 'var(--md-sys-color-surface)', border: '1px solid var(--md-sys-color-outline-variant)',
  boxShadow: '0 3px 8px rgba(20, 35, 70, 0.06)',
};

const iconProps = { width: 22, height: 22, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.6, strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': true } as const;
const BookIcon = () => (<svg {...iconProps}><path d="M12 6.5C10.5 5.3 8 4.8 4 5v13c4-.2 6.5.3 8 1.5 1.5-1.2 4-1.7 8-1.5V5c-4-.2-6.5.3-8 1.5z" /><path d="M12 6.5v13" /></svg>);
const ExternalIcon = () => (<svg {...iconProps}><path d="M14 4h6v6" /><path d="M20 4l-9 9" /><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" /></svg>);

export function ReviewSessionView() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const topic = searchParams.get('topic');
  const essayId = searchParams.get('essay_id');
  const sectionId = searchParams.get('section_id');
  // Sprint14: ?revalidate=1 (+ optional essay_id) = Revalidation mode — the
  // queue comes from GET /flashcards/revalidation (flagged cards, any due date).
  const revalidate = searchParams.get('revalidate') === '1';
  // Scope present -> FOCUS session (all open cards in scope). No scope ->
  // REVIEW session (open AND established). The backend infers this from the
  // params; the caption just reflects it.
  const scopeLabel = revalidate
    ? 'Revalidation'
    : topic
    ? `Focus · ${topic}`
    : essayId
      ? 'Focus · this essay'
      : 'Review';

  const [queue, setQueue] = useState<DueCardRow[]>([]);
  const [flipped, setFlipped] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  const [grading, setGrading] = useState(false);
  const [statsRefresh, setStatsRefresh] = useState(0);
  const [reviewedCount, setReviewedCount] = useState(0);
  const [lastNewIntervalSec, setLastNewIntervalSec] = useState<number | null>(null);
  // flashcard_ids graded `again` at least once this session — drives only the
  // diagnostics-frame label, not queue behaviour. The server's RECENT ordering
  // is what actually brings the card back on the next refetch.
  const [againIds, setAgainIds] = useState<Set<string>>(() => new Set());
  // Sprint06 — "Explore" export on the revealed answer. Read-only: fetches the
  // exploration package and copies it (plus the ChatGPT prompt) to the
  // clipboard; touches no review/scheduling state.
  const [exploring, setExploring] = useState(false);
  const [exploreMsg, setExploreMsg] = useState<string | null>(null);
  // Once the package is on the clipboard, the Explore button becomes an
  // "Import result" button routing to ExploreImportView — reset on the next card.
  const [exported, setExported] = useState(false);
  // Sprint09_Nuggets — source navigation: current.nugget_id set opens
  // NuggetPanel as an overlay (never navigate() — that would unmount this
  // view and interrupt the session); current.nugget_id null keeps the
  // unchanged "Jump to passage" route navigation below.
  const [nuggetPanelOpen, setNuggetPanelOpen] = useState(false);
  // Next-interval labels under the grade buttons (GET /flashcards/{id}/grade-preview), fetched on flip.
  const [preview, setPreview] = useState<Record<string, number> | null>(null);

  const dueUrl = useCallback(() => {
    const qs = new URLSearchParams();
    if (revalidate) {
      if (essayId) qs.set('essay_id', essayId);
      return `/essaycards/flashcards/revalidation${qs.toString() ? `?${qs.toString()}` : ''}`;
    }
    if (topic) qs.set('topic', topic);
    if (essayId) qs.set('essay_id', essayId);
    if (sectionId) qs.set('section_id', sectionId);
    return `/essaycards/flashcards/due${qs.toString() ? `?${qs.toString()}` : ''}`;
  }, [topic, essayId, sectionId, revalidate]);

  // Load the current due queue into state. Called once on mount, after every
  // grade, and from the completion screen's "Check again" — never on a timer.
  const reloadQueue = useCallback(async (): Promise<ApiError | null> => {
    const res = await apiFetch<Dataset<DueCardRow>>(dueUrl());
    if (isApiError(res)) return res;
    setQueue(res.rows);
    return null;
  }, [dueUrl]);

  useEffect(() => {
    (async () => {
      setLoading(true);
      setError(null);
      setFlipped(false);
      setReviewedCount(0);
      setLastNewIntervalSec(null);
      setAgainIds(new Set());
      const err = await reloadQueue();
      setLoading(false);
      if (err) setError(err);
    })();
  }, [reloadQueue]);

  // The server returns the queue already ordered (RECENT closest-due-first,
  // then BACKLOG); always work the head of the list.
  const current = queue[0] ?? null;
  const currentId = current?.flashcard_id ?? null;
  useEffect(() => {
    setPreview(null);
    if (!flipped || !currentId || revalidate) return;
    let cancelled = false;
    (async () => {
      const res = await apiFetch<Dataset<GradePreviewRow>>(`/essaycards/flashcards/${currentId}/grade-preview`);
      if (!cancelled && !isApiError(res)) setPreview(Object.fromEntries(res.rows.map(r => [r.grade, r.interval_seconds])));
    })();
    return () => { cancelled = true; };
  }, [flipped, currentId, revalidate]);
  const showingRelearn = current != null && againIds.has(current.flashcard_id);

  const handleExplore = async () => {
    if (!current || exploring) return;
    setExploring(true);
    setExploreMsg(null);
    const res = await apiFetch<ExplorationPackage>(
      `/essaycards/flashcards/${current.flashcard_id}/exploration-package`,
    );
    setExploring(false);
    if (isApiError(res)) {
      setExploreMsg(`Export failed: ${res.error.message}`);
      return;
    }
    const err = await writeClipboard(buildExploreClipboardText(res));
    if (err) {
      setExploreMsg(err);
    } else {
      setExploreMsg('Copied for ChatGPT');
      setExported(true);
    }
  };

  const handleGrade = async (grade: Grade) => {
    if (!current || grading) return;
    const card = current;
    setGrading(true);
    const res = await apiFetch<ReviewResult>(`/essaycards/flashcards/${card.flashcard_id}/review`, {
      method: 'POST',
      body: JSON.stringify({ grade }),
    });
    if (isApiError(res)) {
      setGrading(false);
      setError(res as ApiError);
      return;
    }

    // A 'preserved' revalidation check changes no schedule, so there is no new interval to report.
    if (res.last_reviewed_at && res.revalidation_outcome !== 'preserved') {
      setLastNewIntervalSec((Date.parse(res.next_due_at) - Date.parse(res.last_reviewed_at)) / 1000);
    }
    setReviewedCount(n => n + 1);
    setFlipped(false);
    setExploreMsg(null);
    setExported(false);
    setNuggetPanelOpen(false);
    setStatsRefresh(n => n + 1);
    if (grade === 'again') setAgainIds(s => new Set(s).add(card.flashcard_id));

    // Re-fetch the due queue after every grade. The card just graded is now
    // scheduled at least 5 s (`again`) / 1 min (floored `hard`) out, so it is
    // absent from this response and reappears only on a later refetch once it
    // comes due — no client-side relearning queue, no timer.
    const err = await reloadQueue();
    setGrading(false);
    if (err) setError(err);
  };

  if (loading) return <div style={pageStyle}><Skeleton /></div>;
  if (error) return <div style={pageStyle}><ErrorCard error={error} /></div>;

  // Revalidation mode shows neither the interval forecast nor the today-metrics row.
  const statsPanel = revalidate ? (
    <div style={{ fontSize: 13, color: 'var(--md-sys-color-on-surface-variant)', marginBottom: 8 }}>
      {queue.length} remaining
    </div>
  ) : (
    <ReviewStatsPanel
      topic={topic}
      essayId={essayId}
      sectionId={sectionId}
      refreshToken={statsRefresh}
      backlog={queue.length}
      newRemaining={queue.filter(c => c.is_new).length}
    />
  );

  // The plain review session has no caption (the Shell header already names
  // the app); focus sessions keep their distinguishing "Focus · ..." caption.
  const scopeCaption = scopeLabel === 'Review' ? null : (
    <div
      style={{
        fontSize: 14,
        fontWeight: 600,
        color: 'var(--md-sys-color-on-surface-variant)',
        marginBottom: 8,
      }}
    >
      {scopeLabel}
    </div>
  );

  if (!current) {
    return (
      <div style={pageStyle}>
        {scopeCaption}
        {statsPanel}
        <div style={{ ...reviewCardStyle, textAlign: 'center', color: 'var(--md-sys-color-on-surface-variant)' }}>
          {revalidate
            ? 'Revalidation complete'
            : reviewedCount === 0 ? 'Nothing due right now.' : 'Session complete — nothing left in the queue.'}
        </div>
        {!revalidate && (
        <button
          style={flipBtnStyle}
          disabled={grading}
          onClick={async () => {
            setGrading(true);
            setError(null);
            const err = await reloadQueue();
            setGrading(false);
            setStatsRefresh(n => n + 1);
            if (err) setError(err);
          }}
        >
          {grading ? 'Checking…' : 'Check again'}
        </button>
        )}
        <button style={{ ...gradeBtnStyle, width: '100%', flex: 'none' }} onClick={() => navigate('/essaycards')}>
          Back to all essays
        </button>
      </div>
    );
  }

  return (
    <div style={pageStyle}>
      {scopeCaption}
      {statsPanel}

      <div style={{ position: 'relative', margin: '16px 0 22px' }}>
        {/* stacked-deck hint: layers shown only while more cards wait */}
        {queue.length > 2 && <div aria-hidden="true" style={{ ...deckLayer, bottom: -12, left: 22, right: 22 }} />}
        {queue.length > 1 && <div aria-hidden="true" style={{ ...deckLayer, bottom: -6, left: 11, right: 11 }} />}
        <div
          className="essaycards-review-card"
          style={{
            ...reviewCardStyle,
            margin: 0,
            position: 'relative',
            boxShadow: '0 6px 20px rgba(20, 35, 70, 0.10)',
            ...(current.is_recent ? { border: '2px solid var(--md-sys-color-primary)' } : null),
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, minHeight: 40 }}>
            <span style={eyebrowStyle}>{current.category ?? current.essay_title}</span>
            {flipped && (
              <span style={{ display: 'inline-flex', gap: 2 }}>
                {current.nugget_id ? (
                  <button style={iconBtnStyle} aria-label="Flashcard → Nugget" title="Flashcard → Nugget" onClick={() => setNuggetPanelOpen(true)}>
                    <BookIcon />
                  </button>
                ) : (
                  <button
                    style={iconBtnStyle}
                    aria-label="Jump to passage"
                    title="Jump to passage"
                    onClick={() => navigate(`/essaycards/essays/${current.essay_id}#${current.anchor_slug}`)}
                  >
                    <BookIcon />
                  </button>
                )}
                {exported ? (
                  <button style={{ ...jumpBtnStyle, margin: 0 }} onClick={() => navigate('/essaycards/explore/import')}>
                    Import result →
                  </button>
                ) : (
                  <button style={iconBtnStyle} aria-label="Explore" title="Explore with ChatGPT" disabled={exploring} onClick={handleExplore}>
                    <ExternalIcon />
                  </button>
                )}
              </span>
            )}
          </div>
          <div
            style={{
              fontFamily: SERIF, fontSize: flipped ? 24 : 30, fontWeight: 500, lineHeight: 1.3,
              color: 'var(--md-sys-color-on-surface)', margin: flipped ? '8px 0 0' : '36px 0 28px',
            }}
          >
            <ReactMarkdown>{current.question}</ReactMarkdown>
          </div>
          {flipped && (
            <div
              style={{
                borderTop: '1px solid var(--md-sys-color-outline-variant)',
                paddingTop: 16,
                marginTop: 16,
                fontSize: 17,
                lineHeight: 1.6,
              }}
            >
              <ReactMarkdown>{current.answer}</ReactMarkdown>
              {exploreMsg && (
                <div style={{ fontSize: 12, color: 'var(--md-sys-color-on-surface-variant)', marginTop: 4 }}>
                  {exploreMsg}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {!flipped ? (
        <button style={{ ...flipBtnStyle, display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 24px' }} onClick={() => setFlipped(true)}>
          <span style={{ flex: 1, textAlign: 'center' }}>Show answer</span><span aria-hidden="true">→</span>
        </button>
      ) : (
        <div style={{ display: 'flex', gap: 8, margin: '8px 0' }}>
          {revalidate ? (
            // Revalidation: exactly two buttons. Correct -> grade 'good' (flag cleared, FSRS
            // untouched); Incorrect -> grade 'again' (genuine FSRS failure).
            <>
              <button style={gradeBtnGoodStyle} disabled={grading} onClick={() => handleGrade('good')}>
                Correct
              </button>
              <button style={gradeBtnAgainStyle} disabled={grading} onClick={() => handleGrade('again')}>
                Incorrect
              </button>
            </>
          ) : (
            (['again', 'hard', 'good', 'easy'] as Grade[]).map(g => (
              <button key={g} style={gradeStyleFor(g)} disabled={grading} onClick={() => handleGrade(g)}>
                <span>{g[0].toUpperCase() + g.slice(1)}</span>
                {preview?.[g] != null && <span style={{ fontSize: 12, fontWeight: 400, opacity: 0.75 }}>{formatInterval(preview[g])}</span>}
              </button>
            ))
          )}
        </div>
      )}

      {!revalidate && (
      <div style={diagFrameStyle}>
        {current.is_recent && (
          <div style={{ color: 'var(--md-sys-color-primary)', fontWeight: 600 }}>
            {showingRelearn
              ? '↩ Failed earlier this session — shown again'
              : '◆ Selected by recency (reviewed in the last 24 h), not by interval'}
          </div>
        )}
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
          <span>This card — last interval</span>
          <strong style={{ color: 'var(--md-sys-color-on-surface)', fontVariantNumeric: 'tabular-nums' }}>
            {formatInterval(current.is_new ? null : current.scheduled_interval_seconds)}
          </strong>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
          <span>Last answer — new interval</span>
          <strong style={{ color: 'var(--md-sys-color-on-surface)', fontVariantNumeric: 'tabular-nums' }}>
            {lastNewIntervalSec == null ? '—' : formatInterval(lastNewIntervalSec)}
          </strong>
        </div>
      </div>
      )}

      {nuggetPanelOpen && current.nugget_id && (
        <NuggetPanel
          initialNuggetId={current.nugget_id}
          essayId={current.essay_id}
          sectionId={current.section_id}
          onClose={() => setNuggetPanelOpen(false)}
        />
      )}
    </div>
  );
}
