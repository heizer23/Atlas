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
import { flipBtnStyle, gradeBtnAgainStyle, gradeBtnGoodStyle, gradeBtnStyle, gradeStyleFor, jumpBtnStyle, pageStyle, reviewCardStyle } from '../styles';
import type { Dataset, DueCardRow, ExplorationPackage, Grade, ReviewResult } from '../types';

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

      <div
        className="essaycards-review-card"
        style={
          current.is_recent
            ? { ...reviewCardStyle, border: '2px solid var(--md-sys-color-primary)' }
            : reviewCardStyle
        }
      >
        <div className="type-title" style={{ lineHeight: 1.5 }}>
          <ReactMarkdown>{current.question}</ReactMarkdown>
        </div>
        {flipped && (
          <>
            <div
              style={{
                borderTop: '1px solid var(--md-sys-color-outline-variant)',
                paddingTop: 16,
                marginTop: 16,
                lineHeight: 1.6,
              }}
            >
              <ReactMarkdown>{current.answer}</ReactMarkdown>
            </div>
            {current.nugget_id ? (
              <button style={jumpBtnStyle} onClick={() => setNuggetPanelOpen(true)}>
                Flashcard → Nugget
              </button>
            ) : (
              <button
                style={jumpBtnStyle}
                onClick={() => navigate(`/essaycards/essays/${current.essay_id}#${current.anchor_slug}`)}
              >
                Jump to passage →
              </button>
            )}
            {exported ? (
              <button
                style={{ ...jumpBtnStyle, marginLeft: 12 }}
                onClick={() => navigate('/essaycards/explore/import')}
              >
                Import result →
              </button>
            ) : (
              <button
                style={{ ...jumpBtnStyle, marginLeft: 12 }}
                disabled={exploring}
                onClick={handleExplore}
              >
                {exploring ? 'Preparing…' : 'Explore'}
              </button>
            )}
            {exploreMsg && (
              <div style={{ fontSize: 12, color: 'var(--md-sys-color-on-surface-variant)', marginTop: 4 }}>
                {exploreMsg}
              </div>
            )}
          </>
        )}
      </div>

      {!flipped ? (
        <button style={flipBtnStyle} onClick={() => setFlipped(true)}>Flip</button>
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
                {g[0].toUpperCase() + g.slice(1)}
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
