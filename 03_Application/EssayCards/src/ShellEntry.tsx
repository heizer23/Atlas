/**
 * EssayCards — ShellEntry
 *
 * Views:
 *   /essaycards                → EssayListView
 *   /essaycards/essays/:id     → ReaderView
 *   /essaycards/review         → ReviewSessionView (query: essay_id?, section_id?)
 *   /essaycards/ingest         → IngestView (Sprint02: paste-JSON add/update essay)
 *
 * Review session note: the due queue is fetched once at session start and
 * held in local state for the whole session — no mid-session re-fetch, per
 * 00_draft.md "Session ends when the due queue (as loaded at session start)
 * is exhausted; it does not live-poll for newly-due cards mid-session."
 *
 * Exception (Sprint05c): a card graded `again` is re-queued client-side into
 * an in-session relearning sub-queue (RelearnItem) and shown again near the
 * front, after a one-card breather. This is pure local state — still no
 * re-fetch and no live-poll of the server.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Route, Routes, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import { apiFetch, isApiError } from '@platform-ui/api/client';
import ErrorCard from '@platform-ui/components/ErrorCard';
import Skeleton from '@platform-ui/components/Skeleton';
import type { ApiError } from '@platform-ui/api/types';

// ── Types ─────────────────────────────────────────────────────────────────────

interface EssayRow {
  id: string;
  title: string;
  slug: string;
}

interface SectionRow {
  id: string;
  heading: string;
  anchor_slug: string;
  order_index: number;
  body_markdown: string;
}

interface EssayDetailRow extends EssayRow {
  sections: SectionRow[];
}

interface DueCardRow {
  id: string;
  flashcard_id: string;
  question: string;
  answer: string;
  essay_id: string;
  section_id: string;
  anchor_slug: string;
  next_due_at: string;
  is_new: boolean;
  is_recent: boolean;
  scheduled_interval_seconds: number | null;
}

interface ReviewResult {
  flashcard_id: string;
  last_reviewed_at: string;
  next_due_at: string;
}

interface QueueStatRow {
  bucket: string;
  label: string;
  count: number;
}

interface LastExamination {
  examined_at: string;
  score: number;
  feedback: string | null;
}

interface ExaminationPackageSection {
  section_id: string;
  anchor_slug: string;
  heading: string;
  body_markdown: string;
  section_version: string;
  flashcards: { id: string; q: string; a: string }[];
  last_examination: LastExamination | null;
}

interface ExaminationPackage {
  essay_id: string;
  essay_slug: string;
  essay_title: string;
  sections: ExaminationPackageSection[];
}

interface SectionExaminationRow {
  id: string;
  examined_at: string;
  score: number;
  question: string;
  answer_transcript: string;
  feedback: string | null;
  section_version_at: string;
}

interface Dataset<T> {
  meta: { object_type: string; total: number };
  rows: T[];
}

type Grade = 'again' | 'hard' | 'good' | 'easy';

// ── Shared styles ─────────────────────────────────────────────────────────────

const pageStyle: React.CSSProperties = { padding: 16, maxWidth: 720, margin: '0 auto' };

const btnStyle: React.CSSProperties = {
  padding: '6px 14px',
  borderRadius: 6,
  border: '1px solid #ccc',
  background: 'transparent',
  cursor: 'pointer',
  fontSize: 13,
};

const primaryBtnStyle: React.CSSProperties = {
  ...btnStyle,
  background: 'var(--md-sys-color-primary)',
  color: '#fff',
  borderColor: 'transparent',
};

// ── Review screen (Sprint05b redesign) — Material 3 surfaces / tokens ────────

const reviewCardStyle: React.CSSProperties = {
  background: 'var(--md-sys-color-surface)',
  border: '1px solid var(--md-sys-color-outline-variant)',
  borderRadius: 'var(--radius-card, 12px)',
  padding: 24,
  margin: '16px 0',
  minHeight: 140,
  boxShadow: 'var(--elevation-1)',
};

// Full-width primary action after reading the question (goal 1).
const flipBtnStyle: React.CSSProperties = {
  width: '100%',
  height: 52,
  borderRadius: 'var(--radius-button, 20px)',
  border: 'none',
  background: 'var(--md-sys-color-primary)',
  color: 'var(--md-sys-color-on-primary)',
  fontSize: 15,
  fontWeight: 600,
  cursor: 'pointer',
  margin: '8px 0',
};

const gradeBtnStyle: React.CSSProperties = {
  flex: 1,
  height: 48,
  borderRadius: 'var(--radius-button, 20px)',
  border: '1px solid var(--md-sys-color-outline)',
  background: 'var(--md-sys-color-surface)',
  color: 'var(--md-sys-color-on-surface)',
  fontSize: 14,
  fontWeight: 500,
  cursor: 'pointer',
};

const jumpBtnStyle: React.CSSProperties = {
  ...btnStyle,
  marginTop: 16,
  border: 'none',
  background: 'transparent',
  color: 'var(--md-sys-color-primary)',
  padding: '4px 0',
  fontSize: 13,
};

// UPCOMING forecast columns. Keys/edges mirror the backend /stats forward
// bands (STATS_BUCKETS minus due_now); `maxIntervalMs` is the closed upper
// edge used to bucket a card's freshly-scheduled interval client-side for the
// `Session` row. Last column has no upper edge.
const FORECAST_COLUMNS: { key: string; label: string; maxIntervalMs: number | null }[] = [
  { key: 'within_10_min',  label: '≤10m', maxIntervalMs: 10 * 60_000 },
  { key: 'within_1_day',   label: '<1d',  maxIntervalMs: 24 * 60 * 60_000 },
  { key: 'within_7_days',  label: '<7d',  maxIntervalMs: 7 * 24 * 60 * 60_000 },
  { key: 'within_30_days', label: '<30d', maxIntervalMs: 30 * 24 * 60 * 60_000 },
  { key: 'within_90_days', label: '<3mo', maxIntervalMs: 90 * 24 * 60 * 60_000 },
  { key: 'beyond_90_days', label: '≥3mo', maxIntervalMs: null },
];

type Forecast = Record<string, number>;

const emptyForecast = (): Forecast =>
  Object.fromEntries(FORECAST_COLUMNS.map(c => [c.key, 0]));

// Which UPCOMING column a card scheduled `intervalMs` into the future lands in.
// `intervalMs` = next_due_at − last_reviewed_at from the review response, i.e.
// the gap measured from the server's own now() at review time (R-CON-AL-06).
function forecastKeyForInterval(intervalMs: number): string {
  for (const col of FORECAST_COLUMNS) {
    if (col.maxIntervalMs === null || intervalMs <= col.maxIntervalMs) return col.key;
  }
  return 'beyond_90_days';
}

// Compact human interval for the review-screen diagnostics frame.
function formatInterval(seconds: number | null): string {
  if (seconds == null) return 'new card';
  const s = Math.max(0, Math.round(seconds));
  if (s < 90) return `${s}s`;
  const m = s / 60;
  if (m < 90) return `${Math.round(m)}m`;
  const h = m / 60;
  if (h < 36) return `${Math.round(h)}h`;
  const d = h / 24;
  if (d < 60) return `${Math.round(d)}d`;
  return `${Math.round(d / 30)}mo`;
}

// Rendered once by the root component. Keeps a Markdown image inside the
// reading column / review card from overflowing. CSS-only per
// Sprint03_Images/10_architecture.json — no custom img component.
const ESSAYCARDS_IMG_CSS =
  '.essaycards-section-body img, .essaycards-review-card img { max-width: 100%; height: auto; }';

// ── Oral examination prompt ──────────────────────────────────────────────────
//
// Copied to the clipboard together with the fetched examination package (see
// ReaderView's handleExportForExamination). Self-contained: a ChatGPT
// conversation with zero prior knowledge of this app can conduct the exam and
// produce a reply that POST /examinations/import accepts unmodified. Every
// output field named below must stay in sync with backend/examinations.py's
// validate_import_body().

const EXAM_PROMPT_INTRO = `You are conducting an oral philosophical examination for an app called EssayCards. Below this prompt is a JSON "examination package" describing one essay and its sections.

GOAL: test whether I actually understand the ideas in each section — NOT whether I can reproduce the essay's wording. Ask me to explain concepts, draw distinctions, connect ideas, and discuss the position in my own words. Do not accept a paraphrase of the text as evidence of understanding.

PROCESS:
- Examine each section in "sections" one at a time (skip a section only if I ask you to).
- If a section's "last_examination" is present, use its "score" and "examined_at" to calibrate: a recent score of 3+ means you can move faster and probe for depth beyond the original text; no last_examination, or a low score, means start from the fundamentals.
- Ask follow-up questions until you can confidently assess my understanding, then move on — this is a conversation, not a fixed quiz.
- I will answer by typing or by pasting a transcript of a spoken answer.

SCORING (0-6, per section, for my demonstrated understanding — not the essay's quality):
  0-2: insufficient / fragmentary — needs active study
  3:   functional understanding — good enough for now, ready to move on
  4:   strong understanding
  5:   deep/integrated understanding
  6:   generative — able to use, criticize, extend, reinterpret, or connect the ideas independently
A score of 3 is a legitimate, successful stopping point — do not withhold it hoping I reach a higher score later.

WHEN THE EXAMINATION IS COMPLETE, reply with ONLY a JSON object in this exact shape — no markdown code fences, no commentary before or after:

{
  "results": [
    {
      "essay_slug": "copy verbatim from the package's essay_slug",
      "section_anchor_slug": "copy verbatim from this section's anchor_slug",
      "section_version": "copy verbatim from this section's section_version",
      "examined_at": "today's date/time in ISO-8601, e.g. 2026-08-28T14:30:00Z",
      "question": "a summary of what you asked/covered for this section (can be multiple questions, written as one text block)",
      "answer_transcript": "a summary or verbatim transcript of my answer(s) for this section",
      "score": 0,
      "feedback": "one or two sentences of feedback, e.g. \\"Good enough for now — revisit in ~6 months.\\" (optional, use null to omit)"
    }
  ]
}

Include one object per section actually examined. Every string value must be valid JSON — escape any double quote that appears inside a value as \\".

Here is the examination package:

`;

function buildExamClipboardText(pkg: ExaminationPackage): string {
  return EXAM_PROMPT_INTRO + JSON.stringify(pkg, null, 2);
}

// ── Essay List View ───────────────────────────────────────────────────────────

function EssayListView() {
  const navigate = useNavigate();
  const [essays, setEssays] = useState<EssayRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);

  useEffect(() => {
    (async () => {
      setLoading(true);
      const res = await apiFetch<Dataset<EssayRow>>('/essaycards/essays');
      setLoading(false);
      if (isApiError(res)) {
        setError(res);
        return;
      }
      setEssays(res.rows);
    })();
  }, []);

  return (
    <div style={pageStyle}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h2 style={{ margin: 0 }}>Essays</h2>
        <div style={{ display: 'flex', gap: 8 }}>
          <button style={btnStyle} onClick={() => navigate('/essaycards/images')}>
            Images
          </button>
          <button style={btnStyle} onClick={() => navigate('/essaycards/examinations/import')}>
            Import exam results
          </button>
          <button style={primaryBtnStyle} onClick={() => navigate('/essaycards/review')}>
            Due for review
          </button>
        </div>
      </div>

      {loading && <Skeleton />}
      {error && <ErrorCard error={error} />}
      {!loading && !error && essays.length === 0 && (
        <div style={{ color: '#888', fontSize: 14 }}>
          No essays yet. Ingest one with the backend CLI:
          <br />
          <code>docker exec atlas-essaycards python -m backend.ingest /app/content/&lt;file&gt;.md</code>
        </div>
      )}
      {!loading && !error && essays.map(e => (
        <div
          key={e.id}
          onClick={() => navigate(`/essaycards/essays/${e.id}`)}
          style={{
            padding: 12,
            borderRadius: 8,
            border: '1px solid #e0e0e0',
            marginBottom: 8,
            cursor: 'pointer',
          }}
        >
          <div style={{ fontWeight: 600 }}>{e.title}</div>
          <div style={{ fontSize: 12, color: '#888' }}>{e.slug}</div>
        </div>
      ))}
    </div>
  );
}

// ── Reader View ───────────────────────────────────────────────────────────────

function ReaderView() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const [essay, setEssay] = useState<EssayDetailRow | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  const [exportMsg, setExportMsg] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    const res = await apiFetch<Dataset<EssayDetailRow>>(`/essaycards/essays/${id}`);
    setLoading(false);
    if (isApiError(res)) {
      setError(res);
      return;
    }
    setEssay(res.rows[0] ?? null);
  }, [id]);

  useEffect(() => { load(); }, [load]);

  // "Jump to passage" navigates here with a #anchor_slug hash — scroll to it
  // once the essay (and its section DOM anchors) has rendered.
  useEffect(() => {
    if (!loading && essay && location.hash) {
      const el = document.getElementById(location.hash.slice(1));
      el?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [loading, essay, location.hash]);

  const handleExportForExamination = async () => {
    if (!essay) return;
    setExporting(true);
    setExportMsg(null);
    const res = await apiFetch<ExaminationPackage>(`/essaycards/essays/${essay.id}/examination-package`);
    setExporting(false);
    if (isApiError(res)) {
      setExportMsg(`Export failed: ${res.error.message}`);
      return;
    }
    try {
      await navigator.clipboard.writeText(buildExamClipboardText(res));
      setExportMsg(
        'Copied. Paste into ChatGPT (or similar), conduct the examination, then paste its JSON reply into ' +
        '"Import exam results" (from the essay list) to store the results.'
      );
    } catch {
      setExportMsg('Could not access the clipboard — check browser permissions.');
    }
  };

  if (loading) return <div style={pageStyle}><Skeleton /></div>;
  if (error) return <div style={pageStyle}><ErrorCard error={error} /></div>;
  if (!essay) return <div style={pageStyle}>Essay not found.</div>;

  return (
    <div style={pageStyle}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12, flexWrap: 'wrap', gap: 8 }}>
        <button style={btnStyle} onClick={() => navigate('/essaycards')}>
          ← All essays
        </button>
        <button style={btnStyle} disabled={exporting} onClick={handleExportForExamination}>
          {exporting ? 'Preparing…' : 'Export for examination'}
        </button>
      </div>
      {exportMsg && <div style={{ fontSize: 12, color: '#888', marginBottom: 12 }}>{exportMsg}</div>}
      <h1 style={{ marginBottom: 24 }}>{essay.title}</h1>

      {essay.sections.length === 0 && (
        <div style={{ color: '#888', fontSize: 14 }}>This essay has no sections yet.</div>
      )}

      {essay.sections.map(section => (
        <section key={section.id} id={section.anchor_slug} style={{ marginBottom: 32 }}>
          <h2>{section.heading}</h2>
          <div className="essaycards-section-body">
            <ReactMarkdown>{section.body_markdown}</ReactMarkdown>
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button
              style={btnStyle}
              onClick={() => navigate(`/essaycards/review?essay_id=${essay.id}&section_id=${section.id}`)}
            >
              Review this section
            </button>
          </div>
          <SectionExaminationHistory sectionId={section.id} />
        </section>
      ))}
    </div>
  );
}

// ── Section Examination History ────────────────────────────────────────────────
//
// Collapsed by default, fetched on first expand — a plain reverse-chronological
// list of stored results (date/score/feedback). Deliberately not a chart or
// trend analysis — that stays out of scope for now.

function SectionExaminationHistory({ sectionId }: { sectionId: string }) {
  const [open, setOpen] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [rows, setRows] = useState<SectionExaminationRow[]>([]);
  const [error, setError] = useState<ApiError | null>(null);

  const handleToggle = async () => {
    const next = !open;
    setOpen(next);
    if (next && !loaded) {
      const res = await apiFetch<Dataset<SectionExaminationRow>>(`/essaycards/sections/${sectionId}/examinations`);
      if (isApiError(res)) {
        setError(res);
      } else {
        setRows(res.rows);
      }
      setLoaded(true);
    }
  };

  return (
    <div style={{ marginTop: 8 }}>
      <button style={{ ...btnStyle, fontSize: 12 }} onClick={handleToggle}>
        {open ? '▾' : '▸'} Examination history{loaded ? ` (${rows.length})` : ''}
      </button>
      {open && (
        <div style={{ marginTop: 8 }}>
          {error && <ErrorCard error={error} />}
          {loaded && !error && rows.length === 0 && (
            <div style={{ color: '#888', fontSize: 13 }}>Not examined yet.</div>
          )}
          {rows.map(r => (
            <div
              key={r.id}
              style={{
                padding: 8,
                borderRadius: 6,
                border: '1px solid #e0e0e0',
                marginBottom: 6,
                fontSize: 13,
              }}
            >
              <div style={{ fontWeight: 600 }}>
                {new Date(r.examined_at).toLocaleDateString()} — score {r.score}/6
              </div>
              {r.feedback && <div style={{ color: '#555', marginTop: 4 }}>{r.feedback}</div>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Review Stats Panel ───────────────────────────────────────────────────────

// One compact Material 3 surface at the top of the review screen holding two
// labelled sections — CURRENT (immediate queue counts) and UPCOMING (a two-row
// forecast: `All` = every scheduled card, from GET /flashcards/stats; `Session`
// = cards rescheduled during this review session, tallied client-side from each
// review response). Visually secondary to the question card: flat
// surface-variant, no elevation. The section names sit rotated in a narrow left
// gutter beside their numbers, not above them, to keep the panel short. A
// /stats failure only blanks the `All` row — the session numbers still render.

const statMetricLabelStyle: React.CSSProperties = {
  fontSize: 11,
  letterSpacing: 0.4,
  textTransform: 'uppercase',
  color: 'var(--md-sys-color-on-surface-variant)',
};

// "CURRENT" / "UPCOMING" rotated to read bottom-to-top in the left gutter.
const gutterLabelStyle: React.CSSProperties = {
  writingMode: 'vertical-rl',
  transform: 'rotate(180deg)',
  textTransform: 'uppercase',
  fontSize: 10,
  fontWeight: 600,
  letterSpacing: 1.5,
  color: 'var(--md-sys-color-on-surface-variant)',
  flexShrink: 0,
  textAlign: 'center',
};

function ForecastRow({ label, values }: { label: string; values: (number | null)[] }) {
  return (
    <>
      <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--md-sys-color-on-surface-variant)', paddingRight: 8 }}>
        {label}
      </span>
      {values.map((v, i) => (
        <span
          key={i}
          style={{
            fontSize: 13,
            textAlign: 'right',
            fontVariantNumeric: 'tabular-nums',
            color: v ? 'var(--md-sys-color-on-surface)' : 'var(--md-sys-color-outline)',
          }}
        >
          {v == null ? '·' : v}
        </span>
      ))}
    </>
  );
}

function ReviewStatsPanel({
  essayId,
  sectionId,
  refreshToken,
  reviewed,
  backlog,
  newRemaining,
  sessionForecast,
}: {
  essayId: string | null;
  sectionId: string | null;
  refreshToken: number;
  reviewed: number;
  backlog: number;
  newRemaining: number;
  sessionForecast: Forecast;
}) {
  const [stats, setStats] = useState<Record<string, number> | null>(null);

  useEffect(() => {
    (async () => {
      const qs = new URLSearchParams();
      if (essayId) qs.set('essay_id', essayId);
      if (sectionId) qs.set('section_id', sectionId);
      const url = `/essaycards/flashcards/stats${qs.toString() ? `?${qs.toString()}` : ''}`;
      const res = await apiFetch<Dataset<QueueStatRow>>(url);
      if (isApiError(res)) {
        setStats(null);
        return;
      }
      setStats(Object.fromEntries(res.rows.map(r => [r.bucket, r.count])));
    })();
  }, [essayId, sectionId, refreshToken]);

  const metrics: [number, string][] = [
    [reviewed, 'Session'],
    [backlog, 'Backlog'],
    [newRemaining, 'New'],
  ];
  const allRow = FORECAST_COLUMNS.map(c => (stats ? stats[c.key] ?? 0 : null));
  const sessionRow = FORECAST_COLUMNS.map(c => sessionForecast[c.key] ?? 0);

  return (
    <div
      style={{
        background: 'var(--md-sys-color-surface-variant)',
        borderRadius: 'var(--radius-card, 12px)',
        padding: 12,
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
      }}
    >
      <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
        <span style={gutterLabelStyle}>Current</span>
        <div style={{ flex: 1, display: 'flex', gap: 8 }}>
          {metrics.map(([value, label]) => (
            <div key={label} style={{ flex: 1, textAlign: 'center' }}>
              <div style={{ fontSize: 22, fontWeight: 500, lineHeight: 1.1, color: 'var(--md-sys-color-on-surface)' }}>
                {value}
              </div>
              <div style={{ ...statMetricLabelStyle, marginTop: 2 }}>{label}</div>
            </div>
          ))}
        </div>
      </div>

      <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
        <span style={gutterLabelStyle}>Upcoming</span>
        <div style={{ flex: 1, overflowX: 'auto' }}>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: `minmax(44px, auto) repeat(${FORECAST_COLUMNS.length}, minmax(34px, 1fr))`,
              rowGap: 4,
              columnGap: 8,
              alignItems: 'baseline',
              minWidth: 300,
            }}
          >
            <span />
            {FORECAST_COLUMNS.map(c => (
              <span
                key={c.key}
                style={{ fontSize: 11, textAlign: 'right', color: 'var(--md-sys-color-on-surface-variant)' }}
              >
                {c.label}
              </span>
            ))}
            <ForecastRow label="All" values={allRow} />
            <ForecastRow label="Session" values={sessionRow} />
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Review Session View ───────────────────────────────────────────────────────

// A card graded `again` earlier this session, waiting to be shown again. Held
// purely client-side (no re-fetch / no live-poll) — `card` is the original
// queue row with next_due_at / scheduled_interval_seconds patched from the
// review response. Becomes eligible once `index` reaches `showAfterIndex` (a
// one-fresh-card breather) or the main queue is exhausted.
interface RelearnItem {
  card: DueCardRow;
  dueAtMs: number;
  showAfterIndex: number;
}

const diagFrameStyle: React.CSSProperties = {
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

function ReviewSessionView() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const essayId = searchParams.get('essay_id');
  const sectionId = searchParams.get('section_id');

  const [queue, setQueue] = useState<DueCardRow[]>([]);
  const [index, setIndex] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  const [grading, setGrading] = useState(false);
  const [statsRefresh, setStatsRefresh] = useState(0);
  const [reviewedCount, setReviewedCount] = useState(0);
  // UPCOMING `Session` row — histogram of the intervals cards were rescheduled
  // into during this session. Built purely from review responses.
  const [sessionForecast, setSessionForecast] = useState<Forecast>(emptyForecast);
  // In-session relearning sub-queue: cards graded `again` come back near the
  // front (see RelearnItem). New interval of the most recently graded card,
  // for the diagnostics frame.
  const [relearning, setRelearning] = useState<RelearnItem[]>([]);
  const [lastNewIntervalSec, setLastNewIntervalSec] = useState<number | null>(null);

  // Fetch the due queue exactly once at session start — deliberately not a
  // dependency-driven re-fetch loop (see file header note).
  useEffect(() => {
    (async () => {
      setLoading(true);
      setError(null);
      const qs = new URLSearchParams();
      if (essayId) qs.set('essay_id', essayId);
      if (sectionId) qs.set('section_id', sectionId);
      const url = `/essaycards/flashcards/due${qs.toString() ? `?${qs.toString()}` : ''}`;
      const res = await apiFetch<Dataset<DueCardRow>>(url);
      setLoading(false);
      if (isApiError(res)) {
        setError(res);
        return;
      }
      setQueue(res.rows);
      setIndex(0);
      setFlipped(false);
      setSessionForecast(emptyForecast());
      setRelearning([]);
      setReviewedCount(0);
      setLastNewIntervalSec(null);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [essayId, sectionId]);

  // Next card: an eligible relearning card (soonest-due first) preempts the
  // main queue; otherwise the card at `index`.
  const eligibleRelearn = relearning
    .filter(r => index >= r.showAfterIndex || index >= queue.length)
    .sort((a, b) => a.dueAtMs - b.dueAtMs || a.showAfterIndex - b.showAfterIndex);
  const relearnCard = eligibleRelearn[0] ?? null;
  const mainCard = queue[index] ?? null;
  const current = relearnCard?.card ?? mainCard;
  const showingRelearn = current != null && current === relearnCard?.card;

  const handleGrade = async (grade: Grade) => {
    if (!current || grading) return;
    const card = current;
    const fromRelearn = showingRelearn;
    setGrading(true);
    const res = await apiFetch<ReviewResult>(`/essaycards/flashcards/${card.flashcard_id}/review`, {
      method: 'POST',
      body: JSON.stringify({ grade }),
    });
    setGrading(false);
    if (isApiError(res)) {
      setError(res as ApiError);
      return;
    }

    const newIntervalSec = (Date.parse(res.next_due_at) - Date.parse(res.last_reviewed_at)) / 1000;
    setLastNewIntervalSec(newIntervalSec);
    const key = forecastKeyForInterval(newIntervalSec * 1000);
    setSessionForecast(f => ({ ...f, [key]: (f[key] ?? 0) + 1 }));
    setReviewedCount(n => n + 1);
    setFlipped(false);
    setStatsRefresh(n => n + 1);

    // Breather before a failed card returns: one fresh card if we're still in
    // the main queue, immediate once it's exhausted.
    const showAfterIndex = index + (fromRelearn ? 1 : 2);
    const requeued: RelearnItem = {
      card: {
        ...card,
        next_due_at: res.next_due_at,
        scheduled_interval_seconds: Math.round(newIntervalSec),
        is_new: false,
        is_recent: true, // just reviewed -> RECENT category on the next pass
      },
      dueAtMs: Date.parse(res.next_due_at),
      showAfterIndex,
    };
    setRelearning(rs => {
      const rest = rs.filter(r => r.card.flashcard_id !== card.flashcard_id);
      return grade === 'again' ? [...rest, requeued] : rest;
    });
    if (!fromRelearn) setIndex(i => i + 1);
  };

  if (loading) return <div style={pageStyle}><Skeleton /></div>;
  if (error) return <div style={pageStyle}><ErrorCard error={error} /></div>;

  const statsPanel = (
    <ReviewStatsPanel
      essayId={essayId}
      sectionId={sectionId}
      refreshToken={statsRefresh}
      reviewed={reviewedCount}
      backlog={queue.length - index + relearning.length}
      newRemaining={queue.slice(index).filter(c => c.is_new).length}
      sessionForecast={sessionForecast}
    />
  );

  if (!current) {
    return (
      <div style={pageStyle}>
        {statsPanel}
        <div style={{ ...reviewCardStyle, textAlign: 'center', color: 'var(--md-sys-color-on-surface-variant)' }}>
          {queue.length === 0 ? 'Nothing due right now.' : 'Session complete — nothing left in the queue.'}
        </div>
        <button style={{ ...gradeBtnStyle, width: '100%', flex: 'none' }} onClick={() => navigate('/essaycards')}>
          Back to all essays
        </button>
      </div>
    );
  }

  return (
    <div style={pageStyle}>
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
            <button
              style={jumpBtnStyle}
              onClick={() => navigate(`/essaycards/essays/${current.essay_id}#${current.anchor_slug}`)}
            >
              Jump to passage →
            </button>
          </>
        )}
      </div>

      {!flipped ? (
        <button style={flipBtnStyle} onClick={() => setFlipped(true)}>Flip</button>
      ) : (
        <div style={{ display: 'flex', gap: 8, margin: '8px 0' }}>
          {(['again', 'hard', 'good', 'easy'] as Grade[]).map(g => (
            <button key={g} style={gradeBtnStyle} disabled={grading} onClick={() => handleGrade(g)}>
              {g[0].toUpperCase() + g.slice(1)}
            </button>
          ))}
        </div>
      )}

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
            {formatInterval(current.scheduled_interval_seconds)}
          </strong>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
          <span>Last answer — new interval</span>
          <strong style={{ color: 'var(--md-sys-color-on-surface)', fontVariantNumeric: 'tabular-nums' }}>
            {lastNewIntervalSec == null ? '—' : formatInterval(lastNewIntervalSec)}
          </strong>
        </div>
      </div>
    </div>
  );
}

// ── Ingest View ───────────────────────────────────────────────────────────────

// Self-contained fill-in prompt: copied to the clipboard so it can be pasted
// into an LLM (ChatGPT or similar) that has zero prior knowledge of this app.
// It restates the full payload contract from Sprint02_JsonIngestion/00_draft.md
// and 10_architecture.json §invariants — every rule here must stay in sync with
// the backend's actual manual validation in backend/routers/essays.py.
const STUB_PROMPT = `You are generating a JSON payload for an app called EssayCards. It will be submitted verbatim as the raw HTTP body of POST /api/essaycards/essays/ingest. Reply with ONLY the JSON object — no markdown code fences (no \`\`\`), no commentary before or after, nothing but the JSON.

Fill in the template below. Every value is an instruction describing what belongs there — replace each one with real content, and remove these instructions from your reply:

{
  "title": "the essay's display title, e.g. \\"Why Rome Fell\\"",
  "slug": "a url-safe stable id for the essay: letters, digits, underscore, hyphen only, no spaces, e.g. why_rome_fell — submitting this JSON again later with the same slug UPDATES this essay instead of creating a new one",
  "sections": [
    {
      "heading": "this section's display heading, e.g. \\"The Economic Causes\\"",
      "anchor_slug": "a url-safe stable id for this section, unique within the essay, e.g. economic-causes — used for \\"jump to passage\\" links, so keep it short and don't rename it on a later update",
      "body_markdown": "the ACTUAL essay text for this section, written in Markdown, roughly 300-600 words ('about one page') — this is what the reader reads. Do not summarize; write the real prose. Flashcards are NOT marked inline in this text (that inline-fence convention is only used by this app's separate offline markdown-file ingestion path, not this JSON format) — flashcards go in the sibling 'cards' list below instead. You may embed images as Markdown image references here — see the Images rule below.",
      "cards": [
        {
          "id": "a url-safe stable id for this card, UNIQUE ACROSS THE WHOLE ESSAY (not just this section) — e.g. economic-causes-1",
          "q": "a question testing something actually stated in this section's body_markdown above — not generic trivia",
          "a": "the answer to that question"
        }
      ]
    }
  ]
}

Rules that don't fit cleanly inline above:
- This must be valid JSON. Any double-quote character that appears INSIDE a string value (e.g. quoting a word for emphasis, or a quoted phrase in the prose) must be escaped as \\" — e.g. write \\"there is no self\\" not "there is no self". An unescaped " inside a string breaks the JSON the moment it appears. Before replying, check every string value in your output for stray unescaped double quotes.
- A card's section is determined ONLY by which section object's "cards" array it is physically nested inside — there is no id/field that points a card at a section. Put each card directly inside the section whose body_markdown it tests.
- "sections" must have at least 1 entry; a section's "cards" list may be empty, but aim for 2-5 cards per section.
- The order of the "sections" array IS the reading order (there is no separate order field); same for the order you list "cards" within a section.
- This is an upsert, never a wholesale replace: if you're updating an existing essay, sections/cards you omit from the payload are left untouched, not deleted.
- Repeat the section object for every section of the essay — a real essay should have several sections, not just one.
- Images. To place an image, write a standard Markdown image reference ![short alt text](/api/essaycards/images/SLUG) on its own line (a blank line before and after) inside a body_markdown value, or inline inside a card "q" or "a". SLUG must be one of the slugs under "Available images" below. The ingest endpoint does NOT validate image references — an invented or misspelled slug silently renders as a broken image, so use only the slugs listed. Add an image only where it genuinely illustrates the adjacent prose, and keep the alt text short. If "Available images" is empty, do not write any image references.

Available images (slug — what it depicts):
- (none yet — before using this prompt, replace this line with one entry per imported image, e.g. "denarius-debasement-chart — line chart of the denarius's silver content, 0-270 AD". Leave empty to use no images.)

Worked mini-example (2 sections, realistic content, for the topic "Why Rome Fell" — do not reuse this content, it's here only to show the pattern):

{
  "title": "Why Rome Fell",
  "slug": "why_rome_fell",
  "sections": [
    {
      "heading": "The Economic Causes",
      "anchor_slug": "economic-causes",
      "body_markdown": "By the 3rd century, Rome's currency had been debased so many times that contemporaries spoke of a \\"debasement crisis\\" eroding trust in coinage across the empire.\\n\\n![Silver content of the denarius, 0-270 AD](/api/essaycards/images/denarius-debasement-chart)\\n\\nTax revenue fell as trade contracted, while the cost of defending an ever-longer frontier kept rising...",
      "cards": [
        { "id": "economic-causes-1", "q": "What did contemporaries call the currency problem of the 3rd century?", "a": "The \\"debasement crisis\\" — repeated debasement of the currency, which drove inflation." },
        { "id": "economic-causes-2", "q": "Why did tax revenue decline even as military costs rose?", "a": "Trade contracted, shrinking the tax base, while frontier defense grew more expensive." }
      ]
    },
    {
      "heading": "Pressure on the Frontiers",
      "anchor_slug": "frontier-pressure",
      "body_markdown": "Migrating and invading groups pressed on the Rhine and Danube frontiers with increasing frequency from the late 4th century onward...",
      "cards": [
        { "id": "frontier-pressure-1", "q": "Which two rivers marked the frontiers under increasing pressure from the late 4th century?", "a": "The Rhine and the Danube." }
      ]
    }
  ]
}

Now write a complete essay with flashcards on the topic I give you, following every rule above exactly, and reply with only the JSON.`;

// Shown as the textarea's empty-state placeholder — same self-documenting
// style as STUB_PROMPT's template (values ARE the instructions). Shows TWO
// sections deliberately: a card's section is determined only by which
// section object's "cards" array it's nested inside (no separate linking
// field exists), and that's invisible with just one section to look at.
const PLACEHOLDER_JSON = `{
  "title": "title of the essay",
  "slug": "url-safe id, e.g. my_essay (letters/digits/_/- only)",
  "sections": [
    {
      "heading": "first section's heading",
      "anchor_slug": "url-safe id for this section, unique in the essay",
      "body_markdown": "this section's essay text, in Markdown",
      "cards": [
        { "id": "unique id for this card (whole essay, not just section)", "q": "question about THIS section", "a": "answer" }
      ]
    },
    {
      "heading": "second section's heading",
      "anchor_slug": "a different url-safe id",
      "body_markdown": "this section's essay text, in Markdown",
      "cards": [
        { "id": "another unique card id", "q": "question about THIS OTHER section", "a": "answer" }
      ]
    }
  ]
}
// a card belongs to whichever section it's nested inside above — there is no separate section-linking field`;

interface IngestSummary {
  essay_id: string;
  slug: string;
  sections_created: number;
  sections_updated: number;
  cards_created: number;
  cards_updated: number;
}

function IngestView() {
  const navigate = useNavigate();
  const [text, setText] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [result, setResult] = useState<IngestSummary | null>(null);
  const [clipboardMsg, setClipboardMsg] = useState<string | null>(null);

  const handleCopyStub = async () => {
    try {
      await navigator.clipboard.writeText(STUB_PROMPT);
      setClipboardMsg('Copied. Paste into ChatGPT (or similar) with your topic, then use "Paste from clipboard" below to bring its reply back in.');
    } catch {
      setClipboardMsg('Could not access the clipboard — check browser permissions.');
    }
  };

  const handlePasteFromClipboard = async () => {
    try {
      const clip = await navigator.clipboard.readText();
      setText(clip);
      setClipboardMsg(null);
    } catch {
      setClipboardMsg('Could not read the clipboard — check browser permissions, or paste manually (Ctrl/Cmd+V) into the box below.');
    }
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    setError(null);
    setResult(null);
    // Send the textarea's raw string content directly as the POST body — do
    // not JSON.parse/re-stringify client-side; let the backend's manual
    // request.json() parse (or reject) exactly what the user typed.
    const res = await apiFetch<IngestSummary>('/essaycards/essays/ingest', {
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
      <h2 style={{ marginTop: 0 }}>Add / Update Essay</h2>
      <div style={{ color: '#888', fontSize: 13, marginBottom: 12 }}>
        Paste a JSON payload describing an essay, its sections, and their
        flashcards. Each flashcard lives inside its section's own "cards"
        list — that nesting is what ties a question to the passage it tests,
        there's no separate field pointing a card at a section. If the slug
        already exists, its sections and cards are upserted; nothing is
        deleted. No idea how to write that JSON by hand? Copy the fill-in
        prompt below, hand it to an LLM with your topic, and paste its reply
        back in.
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
        <button style={btnStyle} onClick={handleCopyStub}>Copy fill-in prompt</button>
        <button style={btnStyle} onClick={handlePasteFromClipboard}>Paste from clipboard</button>
      </div>
      {clipboardMsg && (
        <div style={{ fontSize: 12, color: '#888', marginBottom: 8 }}>{clipboardMsg}</div>
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
          border: '1px solid #ccc',
          borderRadius: 6,
        }}
        placeholder={PLACEHOLDER_JSON}
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
          border: '1px solid #e0e0e0',
        }}>
          <div style={{ fontWeight: 600, marginBottom: 8 }}>Ingest succeeded</div>
          <div style={{ fontSize: 13, color: '#555' }}>
            Sections: +{result.sections_created} created, ~{result.sections_updated} updated
            <br />
            Cards: +{result.cards_created} created, ~{result.cards_updated} updated
          </div>
          <button
            style={{ ...btnStyle, marginTop: 12 }}
            onClick={() => navigate(`/essaycards/essays/${result.essay_id}`)}
          >
            Open essay in reader
          </button>
        </div>
      )}
    </div>
  );
}

// ── Import Examinations View ───────────────────────────────────────────────────

interface ImportSummary {
  imported: number;
  results: { id: string; essay_id: string; section_id: string; examined_at: string; score: number }[];
}

const EXAM_RESULT_PLACEHOLDER_JSON = `{
  "results": [
    {
      "essay_slug": "the essay's slug, from the examination package",
      "section_anchor_slug": "the section's anchor_slug, from the examination package",
      "section_version": "copied verbatim from the section's section_version in the package",
      "examined_at": "2026-08-28T14:30:00Z",
      "question": "summary of what was asked",
      "answer_transcript": "summary or transcript of the answer given",
      "score": 3,
      "feedback": "optional — one or two sentences, or omit/null"
    }
  ]
}`;

function ImportExaminationsView() {
  const navigate = useNavigate();
  const [text, setText] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [result, setResult] = useState<ImportSummary | null>(null);
  const [clipboardMsg, setClipboardMsg] = useState<string | null>(null);

  const handlePasteFromClipboard = async () => {
    try {
      const clip = await navigator.clipboard.readText();
      setText(clip);
      setClipboardMsg(null);
    } catch {
      setClipboardMsg('Could not read the clipboard — check browser permissions, or paste manually (Ctrl/Cmd+V) into the box below.');
    }
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
      <div style={{ color: '#888', fontSize: 13, marginBottom: 12 }}>
        Paste ChatGPT's JSON reply from an oral examination (started with "Export for examination" on an
        essay's page). Each result is stored as a new historical record — importing never overwrites a
        previous examination, so re-examining a section months later just adds another entry.
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
        <button style={btnStyle} onClick={handlePasteFromClipboard}>Paste from clipboard</button>
      </div>
      {clipboardMsg && (
        <div style={{ fontSize: 12, color: '#888', marginBottom: 8 }}>{clipboardMsg}</div>
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
          border: '1px solid #ccc',
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
          border: '1px solid #e0e0e0',
        }}>
          <div style={{ fontWeight: 600, marginBottom: 8 }}>Import succeeded</div>
          <div style={{ fontSize: 13, color: '#555' }}>
            {result.imported} examination result{result.imported === 1 ? '' : 's'} stored.
          </div>
        </div>
      )}
    </div>
  );
}

// ── Images View ───────────────────────────────────────────────────────────────
//
// Two ways to add an image, both funnelling through the same import core:
//   1. Scan the server-side staging folder (POST /images/scan).
//   2. Add from the browser — paste (Ctrl/Cmd-V), drop onto the drop zone, or
//      pick a file — POST /images/upload per file, then re-list.

interface ImageRow {
  slug: string;
  source_filename: string;
  content_type: string;
  byte_size: number;
  width: number | null;
  height: number | null;
  created_at: string;
  url: string;
}

interface ScanReport {
  imported: {
    slug: string;
    source_filename: string;
    url: string;
    width: number | null;
    height: number | null;
    byte_size: number;
  }[];
  unchanged: number;
  skipped: { filename: string; reason: string }[];
}

const GENERIC_PASTE_NAME_RE = /^image\.(png|jpe?g|gif|webp)$/i;

function ImagesView() {
  const navigate = useNavigate();
  const [images, setImages] = useState<ImageRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  const [scanning, setScanning] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [report, setReport] = useState<ScanReport | null>(null);
  const [copiedSlug, setCopiedSlug] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadImages = useCallback(async () => {
    setLoading(true);
    const res = await apiFetch<Dataset<ImageRow>>('/essaycards/images');
    setLoading(false);
    if (isApiError(res)) {
      setError(res);
      return;
    }
    setError(null);
    setImages(res.rows);
  }, []);

  useEffect(() => { loadImages(); }, [loadImages]);

  const handleScan = async () => {
    setScanning(true);
    setError(null);
    setReport(null);
    const res = await apiFetch<ScanReport>('/essaycards/images/scan', { method: 'POST' });
    setScanning(false);
    if (isApiError(res)) {
      setError(res);
      return;
    }
    setReport(res);
    loadImages();
  };

  // POST each image to /images/upload sequentially (volume is tiny; sequential
  // keeps error reporting simple), then re-list and show the same
  // imported / unchanged / skipped block the scan button uses. apiFetch forces
  // a JSON Content-Type, so multipart goes through a raw fetch.
  const uploadFiles = useCallback(async (files: File[]) => {
    const imageFiles = files.filter(f => f.type.startsWith('image/'));
    if (imageFiles.length === 0) return;

    setUploading(true);
    setError(null);
    setReport(null);
    const agg: ScanReport = { imported: [], unchanged: 0, skipped: [] };

    for (const file of imageFiles) {
      const meaningful = !!file.name && !GENERIC_PASTE_NAME_RE.test(file.name);
      const name = meaningful ? file.name : 'pasted-image';
      const fd = new FormData();
      fd.append('file', file, name);
      fd.append('filename', name);
      try {
        const res = await fetch('/api/essaycards/images/upload', { method: 'POST', body: fd });
        const data = await res.json();
        if (!res.ok) {
          const reason = data?.error?.detail?.reason || data?.error?.code || `HTTP ${res.status}`;
          agg.skipped.push({ filename: name, reason });
        } else if (data.unchanged) {
          agg.unchanged += 1;
        } else {
          agg.imported.push({
            slug: data.slug,
            source_filename: data.source_filename,
            url: data.url,
            width: data.width,
            height: data.height,
            byte_size: data.byte_size,
          });
        }
      } catch (e) {
        agg.skipped.push({ filename: name, reason: String(e) });
      }
    }

    setUploading(false);
    setReport(agg);
    loadImages();
  }, [loadImages]);

  // Catch Ctrl/Cmd-V anywhere on the Images view (a plain div is not a reliable
  // paste target on its own).
  useEffect(() => {
    const onPaste = (e: ClipboardEvent) => {
      const files = e.clipboardData ? Array.from(e.clipboardData.files) : [];
      const imgs = files.filter(f => f.type.startsWith('image/'));
      if (imgs.length > 0) {
        e.preventDefault();
        uploadFiles(imgs);
      }
    };
    window.addEventListener('paste', onPaste);
    return () => window.removeEventListener('paste', onPaste);
  }, [uploadFiles]);

  const handleContainerPaste = (e: React.ClipboardEvent) => {
    const imgs = Array.from(e.clipboardData.files).filter(f => f.type.startsWith('image/'));
    if (imgs.length > 0) {
      e.preventDefault();
      uploadFiles(imgs);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(false);
    uploadFiles(Array.from(e.dataTransfer.files));
  };

  const handleCopy = async (slug: string) => {
    try {
      await navigator.clipboard.writeText(`![](/api/essaycards/images/${slug})`);
      setCopiedSlug(slug);
      setTimeout(() => setCopiedSlug(null), 1500);
    } catch {
      setCopiedSlug(null);
    }
  };

  const busy = scanning || uploading;

  return (
    <div style={pageStyle} onPaste={handleContainerPaste}>
      <button style={{ ...btnStyle, marginBottom: 12 }} onClick={() => navigate('/essaycards')}>
        ← All essays
      </button>
      <h2 style={{ marginTop: 0 }}>Images</h2>
      <div style={{ color: '#888', fontSize: 13, marginBottom: 12 }}>
        Add an image by pasting (Ctrl/Cmd-V), dropping a file below, or picking one —
        or drop files into the server staging folder
        (<code>{'${DATA_ROOT}'}/essaycards/staging</code>) and scan. Reference an
        imported image in essay or card text as ordinary Markdown:{' '}
        <code>![](/api/essaycards/images/&lt;slug&gt;)</code>. Keep your originals —
        the processed images folder (and the <code>originals/</code> upload archive)
        is never backed up automatically.
      </div>

      <div
        onDragOver={e => { e.preventDefault(); setDragActive(true); }}
        onDragLeave={e => { e.preventDefault(); setDragActive(false); }}
        onDrop={handleDrop}
        style={{
          border: `2px dashed ${dragActive ? '#4a90d9' : '#c0c0c0'}`,
          background: dragActive ? '#eef5fc' : '#fafafa',
          borderRadius: 8,
          padding: 20,
          textAlign: 'center',
          color: '#666',
          fontSize: 13,
          marginBottom: 12,
        }}
      >
        {uploading ? 'Uploading…' : 'Paste or drop an image here'}
        <div style={{ marginTop: 8 }}>
          <button style={btnStyle} disabled={busy} onClick={() => fileInputRef.current?.click()}>
            Choose file…
          </button>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          multiple
          style={{ display: 'none' }}
          onChange={e => {
            if (e.target.files) uploadFiles(Array.from(e.target.files));
            e.target.value = '';
          }}
        />
      </div>

      <button style={primaryBtnStyle} disabled={busy} onClick={handleScan}>
        {scanning ? 'Scanning…' : 'Scan staging folder'}
      </button>

      {error && <div style={{ marginTop: 16 }}><ErrorCard error={error} /></div>}

      {report && (
        <div style={{
          marginTop: 16,
          padding: 12,
          borderRadius: 8,
          border: '1px solid #e0e0e0',
          fontSize: 13,
        }}>
          <div style={{ fontWeight: 600, marginBottom: 8 }}>Import complete</div>
          <div>Imported: {report.imported.length}</div>
          {report.imported.map(i => (
            <div key={i.slug} style={{ color: '#555' }}>+ {i.source_filename} → {i.slug}</div>
          ))}
          <div style={{ marginTop: 4 }}>Unchanged: {report.unchanged}</div>
          {report.skipped.length > 0 && (
            <>
              <div style={{ marginTop: 4 }}>Skipped: {report.skipped.length}</div>
              {report.skipped.map((s, idx) => (
                <div key={idx} style={{ color: '#a00' }}>– {s.filename} ({s.reason})</div>
              ))}
            </>
          )}
        </div>
      )}

      <h3 style={{ marginTop: 24 }}>Imported images</h3>
      {loading && <Skeleton />}
      {!loading && images.length === 0 && (
        <div style={{ color: '#888', fontSize: 14 }}>No images imported yet.</div>
      )}
      {!loading && images.map(img => (
        <div
          key={img.slug}
          style={{
            display: 'flex',
            gap: 12,
            padding: 12,
            border: '1px solid #e0e0e0',
            borderRadius: 8,
            marginBottom: 8,
            alignItems: 'center',
          }}
        >
          <img
            src={img.url}
            alt={img.source_filename}
            style={{ width: 96, height: 96, objectFit: 'contain', flexShrink: 0, background: '#f5f5f5' }}
          />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontWeight: 600, wordBreak: 'break-all' }}>{img.source_filename}</div>
            <div style={{ fontSize: 12, color: '#888' }}>
              {img.width ?? '?'}×{img.height ?? '?'} · {(img.byte_size / 1024).toFixed(0)} KB · {img.slug}
            </div>
          </div>
          <button style={btnStyle} onClick={() => handleCopy(img.slug)}>
            {copiedSlug === img.slug ? 'Copied' : 'Copy Markdown'}
          </button>
        </div>
      ))}
    </div>
  );
}

// ── Root ──────────────────────────────────────────────────────────────────────

export default function EssayCardsApp() {
  return (
    <>
      <style>{ESSAYCARDS_IMG_CSS}</style>
      <Routes>
        <Route path="/" element={<EssayListView />} />
        <Route path="/essays/:id" element={<ReaderView />} />
        <Route path="/review" element={<ReviewSessionView />} />
        <Route path="/ingest" element={<IngestView />} />
        <Route path="/examinations/import" element={<ImportExaminationsView />} />
        <Route path="/images" element={<ImagesView />} />
      </Routes>
    </>
  );
}
