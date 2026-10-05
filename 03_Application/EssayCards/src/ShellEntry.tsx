/**
 * EssayCards — ShellEntry
 *
 * Views:
 *   /essaycards                → EssayListView
 *   /essaycards/essays/:id     → ReaderView
 *   /essaycards/review         → ReviewSessionView (no query = review/maintenance;
 *                                 query topic? | essay_id? [+ section_id?] = focus session)
 *   /essaycards/ingest         → IngestView (Sprint02: paste-JSON add/update essay)
 *   /essaycards/stats          → ReviewStatsView (study activity, scheduled-reviews
 *                                 forecast, observed recall, scheduled intervals,
 *                                 essay learning progress — see CLAUDE.md "FSRS
 *                                 scheduling" and "Learning progress";
 *                                 Sprint10_DualSchedulerAB's /essaycards/experiment
 *                                 route and its dashboard are retired)
 *
 * Review session note: the due queue is re-fetched from GET /flashcards/due
 * after every grade (and via a manual "Check again" on the completion screen).
 * The just-graded card is scheduled past now() by FSRS so it drops out on its
 * own; a card graded `again` reappears on a later refetch once it comes due,
 * in the server's RECENT-first order. No client-side queue, no timer, no
 * live-poll. The session ends when a refetch returns nothing due — the
 * completion screen's "Check again" re-runs the fetch for the one case that
 * leaves behind (the very last card graded `again`, with nothing else to
 * grade while its interval elapses).
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Route, Routes, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import ReactMarkdown, { defaultUrlTransform } from 'react-markdown';
import { visit } from 'unist-util-visit';
import { apiFetch, isApiError } from '@platform-ui/api/client';
import ErrorCard from '@platform-ui/components/ErrorCard';
import Skeleton from '@platform-ui/components/Skeleton';
import BarChart from '@platform-ui/components/BarChart';
import type { ApiError, Dataset as PlatformDataset } from '@platform-ui/api/types';

// ── Types ─────────────────────────────────────────────────────────────────────

interface EssayRow {
  id: string;
  title: string;
  slug: string;
  category: string | null;
  sort_index: number;
  status: 'planned' | 'complete';
  progress_total: number;
  progress_established: number;
  open_count: number;
  // Sprint12_FSRSAndUXOverhaul — learning-progress fields (see CLAUDE.md
  // "Learning progress"). Replace the removed oral_score/oral_date.
  cards_seen_count: number;
  cards_future_safe_count: number;
  milestone_all_cards_seen: boolean;
  milestone_all_cards_future_safe: boolean;
  milestone_guided_passed: boolean;
  milestone_unguided_passed: boolean;
  guided_passed_at: string | null;
  unguided_passed_at: string | null;
  learning_level: number;
}

// {nugget_key, title} — the light pair shape every nugget-reference field
// carries (never the full body_markdown, to keep list/overview responses
// lightweight). See CLAUDE.md "Nuggets" (Sprint09_Nuggets).
interface NuggetRef {
  nugget_key: string;
  title: string;
}

interface SectionRow {
  id: string;
  heading: string;
  anchor_slug: string;
  order_index: number;
  body_markdown: string;
  nuggets: NuggetRef[];
}

interface EssayDetailRow extends EssayRow {
  main_spine_markdown: string;
  main_spine_nuggets: NuggetRef[];
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
  scheduled_interval_seconds: number;
  nugget_id: string | null;
}

// Sprint12_FSRSAndUXOverhaul — GET /review-stats/activity and
// GET /review-stats/intervals row shapes.
interface ActivityRow {
  date: string;
  reviews: number;
}

interface IntervalBucketRow {
  bucket: string;
  label: string;
  count: number;
}

interface ReviewStatsSummaryRow {
  period: 'day' | 'week' | 'month';
  reviews: number;
  unique_cards: number;
  again_count: number;
  hard_count: number;
  good_count: number;
  easy_count: number;
  failures: number;
  recall_rate: number | null;
  new_count: number;
}

interface ActivityDayRow {
  date: string;
  recalls: number;
  unique_cards_seen: number;
  first_cards_seen: number;
  recall_rate: number | null;
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
  // Sprint12_FSRSAndUXOverhaul — echoes the exam_type the package was
  // requested with.
  exam_type: 'guided' | 'unguided';
  sections: ExaminationPackageSection[];
}

interface SectionExaminationRow {
  id: string;
  examined_at: string;
  score: number;
  // Sprint12_FSRSAndUXOverhaul
  exam_type: 'guided' | 'unguided';
  question: string;
  answer_transcript: string;
  feedback: string | null;
  section_version_at: string;
}

// ── Flashcard exploration (Sprint06) ────────────────────────────────────────

interface ExplorationPackage {
  export_version: number;
  card: {
    card_id: string;
    card_key: string;
    essay_slug: string;
    essay_title: string;
    section_id: string;
    section_anchor_slug: string;
    section_heading: string;
    question: string;
    answer: string;
  };
  // Sprint09_Nuggets: a discriminated union — a nugget-linked card's context
  // is {nugget_body_markdown, nugget_key, nugget_title} INSTEAD OF
  // {section_body_markdown} (a replacement, not an addition). A legacy card
  // (no nugget) keeps the unchanged section-body shape.
  context:
    | { section_body_markdown: string }
    | { nugget_body_markdown: string; nugget_key: string | null; nugget_title: string | null };
}

interface ExplorePreview {
  save_discussion: {
    card_id: string;
    card_key: string;
    exploration_question: string;
    discussion_summary: string;
    resolution: string;
    knowledge_gap: string | null;
    snapshot: { question_at_time: string; answer_at_time: string; section_id_at_time: string };
  };
  update_card: {
    card_id: string;
    card_key: string;
    changed_fields: string[];
    old: { question: string; answer: string };
    new: { question: string; answer: string };
    reason: string;
  }[];
  create_card: {
    section_id: string;
    section_anchor_slug: string;
    essay_id: string;
    question: string;
    answer: string;
    card_key: string;
  }[];
}

interface ExploreImportResult {
  dry_run: boolean;
  applied: boolean;
  discussion_id?: string;
  revisions?: { id: string; card_id: string; card_key: string; changed_fields: string[] }[];
  created_cards?: { id: string; card_key: string; section_id: string; section_anchor_slug: string }[];
  preview: ExplorePreview;
}

// ── Single-section export/import ────────────────────────────────────────────
//
// Same shape as the POST /essays/ingest payload (see IngestView / STUB_PROMPT
// below) — pre-filled from the essay's CURRENT sections, ALL of them, in
// order. POST /essays/ingest assigns each section's order_index from its
// array position, not from any value in the payload, so a partial payload
// would silently reorder the essay on reimport; carrying every section keeps
// an unedited reply's order_index identical to what is already stored. See
// backend/routers/essays.py::export_section.
//
// "Export section" (revise the focus section's own content) and "Insert
// section" (splice a blank-template new section right after the focus one,
// client-side, before copying) both use this same package — only the prompt
// and whether a placeholder is spliced in differ. Both reimport through the
// existing "Add / Update Essay" (IngestView -> POST /essays/ingest); there is
// no separate import endpoint for either.

interface SectionExportPackage {
  export_version: number;
  focus_section_id: string;
  title: string;
  slug: string;
  category: string | null;
  sort_index: number;
  status: string;
  // Sprint09_Nuggets additions: the essay's main spine narrative — a
  // top-level field on POST /essays/ingest, same optional-key/round-trip
  // convention as category/sort_index/status, so an unedited reimport of
  // this package preserves it and an edited one updates it — plus its
  // resolved nuggets (read-only, server-computed) and the focus section's
  // FULL {nugget_key, title, body_markdown} nugget context (richer than the
  // light `nuggets` pairs every section also carries).
  main_spine_markdown: string;
  main_spine_nuggets: NuggetRef[];
  focus_section_nuggets: { nugget_key: string; title: string; body_markdown: string }[];
  sections: {
    section_id: string;
    heading: string;
    anchor_slug: string;
    body_markdown: string;
    cards: { id: string; q: string; a: string }[];
    nuggets: NuggetRef[];
  }[];
}

// ── Single-essay export (Sprint08_QuestionLevelsAndStructure) ──────────────
//
// Sibling of SectionExportPackage — same shape, minus focus_section_id: "any
// number of sections, revise whichever I direct" rather than one named
// section. Reimports through the existing POST /essays/ingest via IngestView.

interface EssayExportPackage {
  export_version: number;
  title: string;
  slug: string;
  category: string | null;
  sort_index: number;
  status: string;
  main_spine_markdown: string;
  main_spine_nuggets: NuggetRef[];
  sections: {
    section_id: string;
    heading: string;
    anchor_slug: string;
    body_markdown: string;
    cards: { id: string; q: string; a: string }[];
    nuggets: NuggetRef[];
  }[];
}

// ── Question overview + single-question export/upsert ──────────────────────
//
// QuestionRow is one flat GET /essays/{id}/questions row — QuestionOverviewView
// groups these by section then by level client-side, the same pattern
// EssayListView already uses to group essays by category from a flat row list.

interface QuestionRow {
  id: string;
  card_key: string;
  question: string;
  answer: string;
  level: number;
  section_id: string;
  section_anchor_slug: string;
  section_heading: string;
  section_order_index: number;
  // Sprint09_Nuggets: the row's own section's referenced nuggets (duplicated
  // per row within the same section — Datasets are flat by contract), and
  // the card's current nugget assignment (nullable).
  section_nuggets: NuggetRef[];
  nugget_id: string | null;
}

// GET /flashcards/{id}/export — essay_slug/essay_title/section_* are
// READ-ONLY CONTEXT for an AI conversation; POST /flashcards/upsert has no
// field to write any of them back to (see buildQuestionUpsertBody below).
interface QuestionExportPackage {
  export_version: number;
  essay_slug: string;
  essay_title: string;
  section_id: string;
  section_anchor_slug: string;
  section_heading: string;
  section_body_markdown: string;
  card: { id: string; level: number; q: string; a: string; nugget_id: string | null };
}

// ── Nuggets (Sprint09_Nuggets) ───────────────────────────────────────────────

interface NuggetListRow {
  id: string;
  nugget_key: string;
  title: string;
  created_at: string;
  updated_at: string;
}

interface NuggetDetailRow extends NuggetListRow {
  body_markdown: string;
}

interface NuggetFlashcardRow {
  id: string;
  card_key: string;
  question: string;
  answer: string;
  level: number;
  essay_id: string;
  section_id: string;
}

interface NuggetSectionRow {
  section_id: string;
  anchor_slug: string;
  heading: string;
  order_index: number;
  essay_id: string;
  essay_title: string;
  essay_slug: string;
}

interface NuggetAuthoringPackage {
  export_version: number;
  essay: { slug: string; title: string; main_spine_markdown: string };
  section: { id: string; anchor_slug: string; heading: string; body_markdown: string };
  nugget: { id: string; nugget_key: string; title: string; body_markdown: string } | null;
  connected_nuggets: NuggetRef[];
}

interface NuggetUpsertResult {
  id: string;
  nugget_key: string;
  title: string;
  created: boolean;
}

interface GenerateFlashcardsPackage {
  export_version: number;
  nugget: { nugget_key: string; title: string; body_markdown: string };
  existing_flashcards: { id: string; card_key: string; question: string; answer: string; level: number }[];
  context: { essay_slug: string; section_id: string };
}

interface QuestionUpsertResult {
  flashcard_id: string;
  card_id: string;
  essay_id: string;
  section_id: string;
  level: number;
  created: boolean;
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

// ── Action menu (Sprint12_FSRSAndUXOverhaul) ────────────────────────────────
//
// Generic primary-button + accessible dropdown, replacing a row of buttons
// at the essay header and at each section's end (10_architecture.json
// internal_flow steps 9-10; see button_nav_inventory for the full pre/post
// mapping). role=menu/menuitem, Escape + click-outside to close, operable by
// keyboard and touch. Reuses existing btnStyle/primaryBtnStyle tokens only —
// no new design tokens.

interface ActionMenuItem {
  label: string;
  onClick: () => void;
  disabled?: boolean;
}

const actionMenuWrapStyle: React.CSSProperties = {
  position: 'relative',
  display: 'inline-flex',
  gap: 8,
};

const actionMenuDropdownStyle: React.CSSProperties = {
  position: 'absolute',
  top: '100%',
  left: 0,
  marginTop: 4,
  background: 'var(--md-sys-color-surface)',
  border: '1px solid var(--md-sys-color-outline-variant)',
  borderRadius: 8,
  boxShadow: 'var(--elevation-1)',
  padding: 4,
  minWidth: 180,
  zIndex: 50,
  display: 'flex',
  flexDirection: 'column',
};

const actionMenuItemStyle: React.CSSProperties = {
  display: 'block',
  width: '100%',
  textAlign: 'left',
  padding: '8px 10px',
  border: 'none',
  background: 'transparent',
  cursor: 'pointer',
  fontSize: 13,
  borderRadius: 6,
  color: 'var(--md-sys-color-on-surface)',
};

function ActionMenu({
  primary,
  items,
}: {
  primary: { label: string; onClick: () => void; disabled?: boolean };
  items: ActionMenuItem[];
}) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDocClick = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onDocClick);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('mousedown', onDocClick);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [open]);

  return (
    <div ref={wrapRef} style={actionMenuWrapStyle}>
      <button
        style={primaryBtnStyle}
        disabled={primary.disabled}
        onClick={primary.onClick}
      >
        {primary.label}
      </button>
      {items.length > 0 && (
        <>
          <button
            style={btnStyle}
            aria-haspopup="menu"
            aria-expanded={open}
            aria-label="More actions"
            onClick={() => setOpen(o => !o)}
          >
            More ▾
          </button>
          {open && (
            <div role="menu" style={actionMenuDropdownStyle}>
              {items.map((item, i) => (
                <button
                  key={i}
                  role="menuitem"
                  style={actionMenuItemStyle}
                  disabled={item.disabled}
                  onClick={() => {
                    setOpen(false);
                    item.onClick();
                  }}
                >
                  {item.label}
                </button>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ── Review screen (Sprint05b redesign) — Material 3 surfaces / tokens ────────

const reviewCardStyle: React.CSSProperties = {
  background: 'var(--md-sys-color-surface)',
  border: '1px solid var(--md-sys-color-outline-variant)',
  borderRadius: 'var(--radius-card, 12px)',
  padding: 24,
  margin: '16px 0',
  minHeight: 140,
  boxShadow: 'var(--elevation-1)',
  position: 'relative',
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

// Interval forecast columns. Keys/edges mirror the backend /stats forward
// bands (STATS_BUCKETS minus due_now); `maxIntervalMs` is the closed upper
// edge of each band. Last column has no upper edge.
const FORECAST_COLUMNS: { key: string; label: string; maxIntervalMs: number | null }[] = [
  { key: 'within_10_min',  label: '≤10m', maxIntervalMs: 10 * 60_000 },
  { key: 'within_1_day',   label: '<1d',  maxIntervalMs: 24 * 60 * 60_000 },
  { key: 'within_7_days',  label: '<7d',  maxIntervalMs: 7 * 24 * 60 * 60_000 },
  { key: 'within_30_days', label: '<30d', maxIntervalMs: 30 * 24 * 60 * 60_000 },
  { key: 'within_90_days', label: '<3mo', maxIntervalMs: 90 * 24 * 60 * 60_000 },
  { key: 'beyond_90_days', label: '≥3mo', maxIntervalMs: null },
];

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

// ── Clipboard helpers ────────────────────────────────────────────────────────
//
// navigator.clipboard.writeText/readText can throw (permissions denied,
// insecure context, etc.). Every export/import view in this app (whole-essay
// ingest, oral-exam export/import, flashcard exploration, section export)
// surfaces that failure the same way, so the two messages live here once
// instead of at each call site.

const CLIPBOARD_WRITE_DENIED = 'Could not access the clipboard — check browser permissions.';
const CLIPBOARD_READ_DENIED =
  'Could not read the clipboard — check browser permissions, or paste manually (Ctrl/Cmd+V) into the box below.';

// Returns null on success, or CLIPBOARD_WRITE_DENIED on failure — the caller
// substitutes its own success message when this returns null.
async function writeClipboard(text: string): Promise<string | null> {
  try {
    await navigator.clipboard.writeText(text);
    return null;
  } catch {
    return CLIPBOARD_WRITE_DENIED;
  }
}

async function readClipboard(): Promise<{ text: string } | { error: string }> {
  try {
    return { text: await navigator.clipboard.readText() };
  } catch {
    return { error: CLIPBOARD_READ_DENIED };
  }
}

// ── Oral examination prompts ─────────────────────────────────────────────────
//
// Copied to the clipboard together with the fetched examination package (see
// ReaderView's handleExportExam). Self-contained: a ChatGPT conversation with
// zero prior knowledge of this app can conduct the exam and produce a reply
// that POST /examinations/import accepts unmodified. Every output field named
// below must stay in sync with backend/examinations.py's validate_import_body().
//
// Sprint12_FSRSAndUXOverhaul splits the single prompt into two variants:
// EXAM_PROMPT_INTRO_GUIDED (unchanged calibration-aware behavior, renamed)
// and EXAM_PROMPT_INTRO_UNGUIDED (explicitly cold-start, no calibration
// context — matches the backend always returning last_examination: null for
// exam_type=unguided). Both bake their own "exam_type" into the described
// reply shape.

const EXAM_PROMPT_INTRO_GUIDED = `You are conducting an oral philosophical examination for an app called EssayCards. Below this prompt is a JSON "examination package" describing one essay and its sections.

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
      "exam_type": "guided",
      "feedback": "one or two sentences of feedback, e.g. \\"Good enough for now — revisit in ~6 months.\\" (optional, use null to omit)"
    }
  ]
}

Include one object per section actually examined. Every string value must be valid JSON — escape any double quote that appears inside a value as \\".

Here is the examination package:

`;

const EXAM_PROMPT_INTRO_UNGUIDED = `You are conducting an UNGUIDED oral philosophical examination for an app called EssayCards. Below this prompt is a JSON "examination package" describing one essay and its sections.

GOAL: test whether I actually understand the ideas in each section — NOT whether I can reproduce the essay's wording. Ask me to explain concepts, draw distinctions, connect ideas, and discuss the position in my own words. Do not accept a paraphrase of the text as evidence of understanding.

IMPORTANT — this is a COLD-START examination: do NOT use any prior-history or calibration context, even if you happen to know it from earlier in this conversation. Start every section from the fundamentals, exactly as you would for a learner with no recorded history, regardless of how well I may have done before.

PROCESS:
- Examine each section in "sections" one at a time (skip a section only if I ask you to).
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
      "exam_type": "unguided",
      "feedback": "one or two sentences of feedback, e.g. \\"Good enough for now — revisit in ~6 months.\\" (optional, use null to omit)"
    }
  ]
}

Include one object per section actually examined. Every string value must be valid JSON — escape any double quote that appears inside a value as \\".

Here is the examination package:

`;

function buildExamClipboardText(pkg: ExaminationPackage, examType: 'guided' | 'unguided'): string {
  const intro = examType === 'guided' ? EXAM_PROMPT_INTRO_GUIDED : EXAM_PROMPT_INTRO_UNGUIDED;
  return intro + JSON.stringify(pkg, null, 2);
}

// ── Flashcard exploration prompt (Sprint06) ─────────────────────────────────
//
// Copied to the clipboard with the exploration package by the "Explore" button
// on the revealed answer in ReviewSessionView. Deliberately action-neutral: the
// user does not decide up front whether the problem is their own
// misunderstanding, a bad question, a wrong answer, or a missing distinction —
// that emerges from the ChatGPT discussion. Every field named here must stay in
// sync with backend/exploration.py::validate_import_body.

const EXPLORE_PROMPT_INTRO = `This is an EssayCards flashcard exploration package.

Use the card and source context below as authoritative local context. "card.answer" is the current canonical answer. The "context" object has one of two shapes: either "context.section_body_markdown" (the essay section the card was written from — EssayCards has no finer-grained paragraph link, so the whole section is the context), or, for a card linked to a reusable "nugget" concept, "context.nugget_body_markdown" plus "context.nugget_key"/"context.nugget_title" (the nugget's own independent explanation, standing in for the section in this case).

I will now discuss this question with you naturally. I may have misunderstood the underlying concept, the question or answer may be poorly formulated, or the discussion may reveal another distinction worth its own card. Do NOT decide in advance which of these is the case — let it emerge from the conversation.

When I explicitly ask you to return the result for EssayCards, reply with ONLY a single valid JSON object — no markdown code fences, no commentary before or after — of this shape:

{
  "actions": [ ... ]
}

Supported actions:

1. save_discussion — ALWAYS include exactly one whenever you return a result, so the useful outcome is retained.
{
  "type": "save_discussion",
  "card_id": "copy verbatim from card.card_id below",
  "discussion": {
    "exploration_question": "what I was actually trying to understand or investigate",
    "discussion_summary": "a compact summary of the useful substance of the conversation — distil it; do NOT paste the transcript or keep conversational filler",
    "resolution": "the main conclusion or distinction we reached",
    "knowledge_gap": "what I had misunderstood, conflated or found unclear — or null if my understanding was fine and the card itself was the problem"
  }
}

2. update_card — add ONLY if the live flashcard should actually change.
{
  "type": "update_card",
  "card_id": "copy verbatim from card.card_id below",
  "changes": { "question": "improved wording", "answer": "improved answer" },
  "reason": "why the change is warranted — MANDATORY; kept as evidence about what makes a flashcard question good or bad"
}
Put only the field(s) that should change inside "changes" — "question", "answer", or both. An omitted field is left untouched.

3. create_card — add when the discussion exposes a separate idea worth testing on its own.
{
  "type": "create_card",
  "section_id": "the target section id — by default card.section_id below, unless the discussion clearly belongs elsewhere",
  "section_anchor_slug": "that section's anchor slug, for validation — card.section_anchor_slug by default",
  "question": "the new flashcard question",
  "answer": "the new flashcard answer"
}
Do NOT include a "reason" for create_card — a new card is created like any other.

You may return several actions together (e.g. save_discussion + update_card + create_card) when one conversation had several outcomes. Every string must be valid JSON — escape any double quote inside a value as \\".

Here is the exploration package:

`;

function buildExploreClipboardText(pkg: ExplorationPackage): string {
  return EXPLORE_PROMPT_INTRO + JSON.stringify(pkg, null, 2);
}

// ── Single-section export / insert prompts ──────────────────────────────────
//
// Copied to the clipboard with the section export package by the "Export
// section" / "Insert section after" buttons in ReaderView. The package IS a
// valid POST /essays/ingest payload (see SectionExportPackage above) — the
// reply is meant to be pasted straight into IngestView ("Add / Update
// Essay") unmodified in shape, only content changed. Both prompts stress
// leaving every non-target section byte-for-byte identical and in place,
// because array order becomes each section's order_index on reimport (see
// export_section's docstring in backend/routers/essays.py).

const SECTION_EXPORT_PROMPT_INTRO = `You are helping revise one section of an essay for an app called EssayCards. Below this prompt is a JSON payload containing EVERY section of the essay, in order, wrapped in the essay-level fields required to save it back. "focus_section_id" names the ONE section to revise — find it in "sections" by matching its "section_id".

Revise ONLY that section as I direct in this conversation — rewrite its "body_markdown", fix errors, tighten prose, or add/edit/remove entries in its "cards". Leave every OTHER entry in "sections" completely untouched, in the same order — the array order is what saves each section's position, so adding, removing or reordering any section you were not asked to change will silently move or lose sections.

RULES (breaking these makes the reply unusable):
- Return exactly the same sections, in the same order — do not add, remove, or reorder any of them. Only the focus section's content changes.
- Do NOT change "slug" (the essay's id) or any section's "anchor_slug" — renaming one breaks links back to that section.
- Do NOT change "title", "category", "sort_index", or "status" unless I explicitly ask you to.
- Each card has a short "id". Keep the "id" of any card you are editing unchanged, so it updates in place instead of creating a duplicate. Only invent a new "id" (letters, digits, "_"/"-" only, unique across the whole essay) for a genuinely new card.
- Removing a card from a section's "cards" does NOT delete it from the app on reimport — it is simply left unchanged. There is no way to delete a card through this mechanism.
- "body_markdown" is the actual essay prose the reader sees — write real text, not a summary.

WHEN I EXPLICITLY ASK YOU TO FINALIZE, reply with ONLY the complete JSON object — no markdown code fences, no commentary before or after — the same shape as below with your revisions applied. Every string must be valid JSON — escape any double quote inside a value as \\".

Here is the section package:

`;

function buildSectionExportClipboardText(pkg: SectionExportPackage): string {
  return SECTION_EXPORT_PROMPT_INTRO + JSON.stringify(pkg, null, 2);
}

const SECTION_INSERT_PROMPT_INTRO = `You are helping write a NEW section for an essay in an app called EssayCards, to be inserted at a specific position. Below this prompt is a JSON payload containing EVERY section of the essay, in order, wrapped in the essay-level fields required to save it back. A placeholder entry has been spliced into "sections" at the position where the new section goes — it is the entry whose "heading" is "NEW SECTION — replace this whole entry"; every field on that entry is an instruction for what to write, not real content.

Write the new section as I direct in this conversation, fitting naturally between its neighbors in the array — read their "body_markdown" for context and continuity, and don't repeat what they already cover. Replace the placeholder entry's "heading", "anchor_slug", "body_markdown" and "cards" with the real content. Leave every OTHER entry in "sections" completely untouched, in the same order.

RULES (breaking these makes the reply unusable):
- Return exactly the same number of sections, in the same order, with ONLY the placeholder entry filled in — do not add, remove, or reorder any other section.
- The new section's "anchor_slug" must be a url-safe id (letters, digits, "_"/"-" only) not matching any anchor_slug already used elsewhere in this payload.
- Do NOT change "slug" (the essay's id) or any EXISTING section's "anchor_slug" — renaming one breaks links back to that section.
- Do NOT change "title", "category", "sort_index", or "status" unless I explicitly ask you to.
- Give each new card a short "id" (letters, digits, "_"/"-" only) not matching any card id already used elsewhere in this payload.
- "body_markdown" is the actual essay prose the reader sees, roughly 300-600 words — write real text, not a summary.

WHEN I EXPLICITLY ASK YOU TO FINALIZE, reply with ONLY the complete JSON object — no markdown code fences, no commentary before or after — the same shape as below, with the placeholder replaced. Every string must be valid JSON — escape any double quote inside a value as \\".

Here is the section package:

`;

// The instructional placeholder entry spliced into the array right after the
// focus section, for the "Insert section after" flow. Its own field values
// ARE the fill-in instructions (same convention as PLACEHOLDER_JSON/
// STUB_PROMPT below) — SECTION_INSERT_PROMPT_INTRO tells the model to find it
// by this exact heading text and replace the whole entry.
function buildInsertPlaceholderSection(): SectionExportPackage['sections'][number] {
  return {
    section_id: '(new — assigned automatically on import)',
    heading: 'NEW SECTION — replace this whole entry',
    anchor_slug: 'a-new-url-safe-id-unique-in-this-essay',
    body_markdown:
      "THE ACTUAL NEW SECTION'S ESSAY TEXT, written in Markdown, roughly 300-600 words, continuing naturally " +
      'from the surrounding sections — replace this instruction text with real prose. Do not summarize.',
    cards: [
      { id: 'a-new-unique-card-id', q: 'a flashcard question drawn from this new section', a: 'its answer' },
    ],
    nuggets: [],
  };
}

function buildSectionInsertClipboardText(pkg: SectionExportPackage): string {
  const focusIdx = pkg.sections.findIndex(s => s.section_id === pkg.focus_section_id);
  const insertAt = focusIdx === -1 ? pkg.sections.length : focusIdx + 1;
  const sections = [...pkg.sections];
  sections.splice(insertAt, 0, buildInsertPlaceholderSection());
  return SECTION_INSERT_PROMPT_INTRO + JSON.stringify({ ...pkg, sections }, null, 2);
}

// ── Single-essay export prompt ──────────────────────────────────────────────
//
// Copied to the clipboard by the "Export essay" button in ReaderView. Same
// package shape as SectionExportPackage minus focus_section_id — the model
// may revise however many sections I direct, not just one named section.

const ESSAY_EXPORT_PROMPT_INTRO = `You are helping revise an essay for an app called EssayCards. Below this prompt is a JSON payload containing EVERY section of the essay, in order, wrapped in the essay-level fields required to save it back.

Revise whichever sections I direct in this conversation — rewrite "body_markdown", fix errors, tighten prose, or add/edit/remove entries in a section's "cards". Leave every section I do NOT ask you to touch completely unchanged, in the same order — the array order is what saves each section's position, so adding, removing, or reordering sections will silently move or lose them.

RULES (breaking these makes the reply unusable):
- Return exactly the same sections, in the same order — do not add, remove, or reorder any of them (ask me explicitly if I want a new section; that is a different workflow).
- Do NOT change "slug" (the essay's id) or any section's "anchor_slug" — renaming one breaks links back to that section.
- Do NOT change "title", "category", "sort_index", or "status" unless I explicitly ask you to.
- Each card has a short "id". Keep the "id" of any card you are editing unchanged, so it updates in place instead of creating a duplicate. Only invent a new "id" (letters, digits, "_"/"-" only, unique across the whole essay) for a genuinely new card.
- Removing a card from a section's "cards" does NOT delete it from the app on reimport — it is simply left unchanged. There is no way to delete a card through this mechanism.
- "body_markdown" is the actual essay prose the reader sees — write real text, not a summary.

WHEN I EXPLICITLY ASK YOU TO FINALIZE, reply with ONLY the complete JSON object — no markdown code fences, no commentary before or after — the same shape as below with your revisions applied. Every string must be valid JSON — escape any double quote inside a value as \\".

Here is the essay package:

`;

function buildEssayExportClipboardText(pkg: EssayExportPackage): string {
  return ESSAY_EXPORT_PROMPT_INTRO + JSON.stringify(pkg, null, 2);
}

// ── Single-question export prompt (Sprint08_QuestionLevelsAndStructure) ────
//
// Copied to the clipboard by the "Export" button on a question row in
// QuestionOverviewView. essay_slug/essay_title/section_* are READ-ONLY
// CONTEXT — POST /flashcards/upsert (the reimport target) has no field to
// write any of them back to, so even a reply that echoes this whole export
// back verbatim cannot touch essay prose. Every field named here must stay
// in sync with backend/routers/flashcards.py::_validate_upsert_body.

const QUESTION_EXPORT_PROMPT_INTRO = `This is an EssayCards single-question export, for discussing and improving one flashcard with you. Below this prompt is a JSON payload. Only "card" is what gets saved — "essay_slug", "essay_title", "section_id", "section_anchor_slug", "section_heading" and "section_body_markdown" are READ-ONLY CONTEXT: use them to understand the surrounding essay, but nothing you write into them has any effect, so don't bother rewriting them.

Discuss and improve the question as I direct in this conversation — rewrite "card.q" and/or "card.a", and change "card.level" if I ask you to reconsider its structural depth (1 = foundational/spine, 2 = building/explanatory structure, 3 = decorating/example/detail — open-ended upward, but 1-3 is the current convention).

RULES (breaking these makes the reply unusable):
- Do NOT change "card.id" — it is this question's stable identity; changing it creates a duplicate question instead of updating this one.
- "card.level" must be a plain integer >= 1.

WHEN I EXPLICITLY ASK YOU TO FINALIZE, reply with ONLY a JSON object of this exact shape — no markdown code fences, no commentary before or after:

{
  "essay_slug": "copy verbatim from this package's essay_slug",
  "section_id": "copy verbatim from this package's section_id",
  "card": { "id": "copy verbatim from card.id", "level": 0, "q": "...", "a": "..." }
}

Every string must be valid JSON — escape any double quote inside a value as \\".

Here is the question package:

`;

function buildQuestionExportClipboardText(pkg: QuestionExportPackage): string {
  return QUESTION_EXPORT_PROMPT_INTRO + JSON.stringify(pkg, null, 2);
}

// ── Nugget authoring / generate-flashcards prompts (Sprint09_Nuggets) ──────
//
// Copied to the clipboard by NuggetAuthoringImportView / GenerateFlashcards-
// ImportView. Every field named here must stay in sync with
// backend/routers/nuggets.py's POST /upsert body shape and
// backend/routers/flashcards.py::_validate_upsert_body's card shape.

const NUGGET_AUTHORING_PROMPT_INTRO = `You are helping write or revise ONE reusable "nugget" — a small, independently-learnable concept — for an app called EssayCards. Below this prompt is a JSON "authoring package": the current essay's title and main spine, the current section and its own spine narrative (context only, for continuity — you are not revising these), the target nugget ("nugget": null if you are drafting a brand-new one), and "connected_nuggets" (other nuggets the target nugget's own text already references, for context).

A nugget must stay INDEPENDENTLY UNDERSTANDABLE — someone who has never read this essay must be able to learn the concept from the nugget's own body_markdown alone. Do NOT reproduce the whole essay or section inside it; write the concept's own explanation, roughly 100-400 words. You may reference another nugget by writing "[[nugget:its-key]]" inline (only for keys that already exist — check "connected_nuggets" and the essay/section context for known keys; never invent a reference to a key you have not been told exists).

WHEN I EXPLICITLY ASK YOU TO FINALIZE, reply with ONLY a JSON object in this exact shape — no markdown code fences, no commentary before or after:

{
  "nugget_key": "a short url-safe id, letters/digits/\\"_\\"/\\"-\\" only — KEEP THE EXISTING KEY if you were revising an existing nugget (copy it verbatim from \\"nugget.nugget_key\\" above); invent a new, not-already-used one only when drafting a brand-new nugget",
  "title": "a short display title",
  "body_markdown": "the nugget's own independent explanation, in Markdown"
}

Every string must be valid JSON — escape any double quote inside a value as \\".

Here is the authoring package:

`;

function buildNuggetAuthoringClipboardText(pkg: NuggetAuthoringPackage): string {
  return NUGGET_AUTHORING_PROMPT_INTRO + JSON.stringify(pkg, null, 2);
}

const GENERATE_FLASHCARDS_PROMPT_INTRO = `You are generating new flashcards for ONE reusable "nugget" in an app called EssayCards. Below this prompt is a JSON package: the nugget's own content ("nugget") and its existing flashcards ("existing_flashcards", for context — do not duplicate what they already test).

Write flashcards that test recall/understanding of THIS nugget's own content only. Each card needs a "level" (1 = foundational/spine, 2 = building/explanatory structure, 3 = decorating/example/detail — 1-3 is the current convention, open-ended upward), a "q" (question) and an "a" (answer).

WHEN I EXPLICITLY ASK YOU TO FINALIZE, reply with ONLY a JSON object in this exact shape — no markdown code fences, no commentary before or after:

{
  "cards": [
    { "level": 2, "q": "a flashcard question", "a": "its answer" }
  ]
}

Every string must be valid JSON — escape any double quote inside a value as \\".

Here is the package:

`;

function buildGenerateFlashcardsClipboardText(pkg: GenerateFlashcardsPackage): string {
  return GENERATE_FLASHCARDS_PROMPT_INTRO + JSON.stringify(pkg, null, 2);
}

// ── Nugget rendering / navigation (Sprint09_Nuggets) ────────────────────────
//
// [[nugget:key]] references inside essay.main_spine_markdown and
// section.body_markdown render as in-app links via remarkNuggetRefs +
// NuggetLink, opening the NuggetPanel overlay instead of navigating — so
// ReaderView/ReviewSessionView never unmount and reading position / review
// session state are preserved (00_draft.md §7).

// TS mirror of backend/ingest.py::extract_nugget_keys — same strip-fences-
// then-match-[[nugget:key]] approach. Used only by IngestView's section
// spine-revision drop-detection (client-side, no DB access).
const NUGGET_REF_RE_CLIENT = /\[\[nugget:([a-zA-Z0-9_-]+)\]\]/g;

function extractNuggetKeysClient(markdown: string): Set<string> {
  const stripped = markdown
    .replace(/```[\s\S]*?```/g, '')
    .replace(/`[^`\n]*`/g, '');
  const keys = new Set<string>();
  let m: RegExpExecArray | null;
  NUGGET_REF_RE_CLIENT.lastIndex = 0;
  while ((m = NUGGET_REF_RE_CLIENT.exec(stripped)) !== null) keys.add(m[1]);
  return keys;
}

// remarkNuggetRefs visits only mdast 'text' nodes — by the time remark hands
// off, fenced code blocks and inline code spans are already separate
// code/inlineCode node types, so a [[nugget:...]] written inside either is
// structurally invisible to a text-node visitor. No hand-written fence/span
// detection needed (unlike extractNuggetKeysClient above, which operates on
// raw text and must strip them itself).
function remarkNuggetRefs(titleMap: Record<string, string>) {
  return (tree: any) => {
    visit(tree, 'text', (node: any, index: number | undefined, parent: any) => {
      if (!parent || index === undefined) return;
      const value: string = node.value;
      const re = /\[\[nugget:([a-zA-Z0-9_-]+)\]\]/g;
      let match: RegExpExecArray | null;
      let lastIndex = 0;
      let found = false;
      const newNodes: any[] = [];
      while ((match = re.exec(value)) !== null) {
        found = true;
        if (match.index > lastIndex) {
          newNodes.push({ type: 'text', value: value.slice(lastIndex, match.index) });
        }
        const key = match[1];
        const title = titleMap[key];
        newNodes.push(
          title
            ? { type: 'link', url: `nugget:${key}`, children: [{ type: 'text', value: title }] }
            : { type: 'link', url: `nugget-missing:${key}`, children: [{ type: 'text', value: key }] },
        );
        lastIndex = match.index + match[0].length;
      }
      if (!found) return;
      if (lastIndex < value.length) newNodes.push({ type: 'text', value: value.slice(lastIndex) });
      parent.children.splice(index, 1, ...newNodes);
      return index + newNodes.length;
    });
  };
}

// react-markdown's default urlTransform only passes through
// https?/ircs?/mailto/xmpp schemes and silently rewrites anything else
// (including our nugget:/nugget-missing: scheme) to '' before NuggetLink ever
// sees it — so every nugget link would fall through to NuggetLink's plain-<a>
// branch with an empty href. Pass nugget refs through untouched; defer to the
// default sanitizer for everything else.
function nuggetAwareUrlTransform(url: string): string {
  return url.startsWith('nugget:') || url.startsWith('nugget-missing:') ? url : defaultUrlTransform(url);
}

// href scheme branch for ReactMarkdown's `a` component override: `nugget:` ->
// in-app overlay open (never a real navigation — a full page nav would break
// reading-position preservation); `nugget-missing:` -> non-clickable, styled
// as broken, key text never silently rendered as if valid; anything else ->
// ordinary <a>, unchanged behavior for normal links/images.
function NuggetLink({ href, children, onOpenNugget }: {
  href?: string;
  children?: React.ReactNode;
  onOpenNugget: (key: string) => void;
}) {
  if (href?.startsWith('nugget:')) {
    const key = href.slice('nugget:'.length);
    return (
      <a
        href="#"
        onClick={e => { e.preventDefault(); e.stopPropagation(); onOpenNugget(key); }}
        style={{ color: 'var(--md-sys-color-primary)', fontWeight: 700, textDecoration: 'underline', cursor: 'pointer' }}
      >
        {children}
      </a>
    );
  }
  if (href?.startsWith('nugget-missing:')) {
    const key = href.slice('nugget-missing:'.length);
    return (
      <span
        title={`Unresolved nugget reference: [[nugget:${key}]]`}
        style={{ color: '#b00020', textDecoration: 'line-through', cursor: 'not-allowed' }}
      >
        {children}
      </span>
    );
  }
  // stopPropagation: a link tap inside a feedback-enabled sentence must never
  // also open the sentence feedback popover (Sprint13 click precedence).
  return <a href={href} target="_blank" rel="noreferrer" onClick={e => e.stopPropagation()}>{children}</a>;
}

// Cached key -> {id, title} index built from GET /nuggets (small, unfiltered
// list — see 10_architecture.json deferred_decisions). Used ONLY to resolve a
// clicked [[nugget:key]] reference's id at click time (never per-render) and
// to render a nugget's OWN body_markdown inside NuggetPanel, which has no
// pre-fetched titleMap of its own the way a section/main-spine render does.
let nuggetIndexCache: Promise<Record<string, { id: string; title: string }>> | null = null;

function loadNuggetIndex(): Promise<Record<string, { id: string; title: string }>> {
  if (!nuggetIndexCache) {
    nuggetIndexCache = (async () => {
      const res = await apiFetch<Dataset<NuggetListRow>>('/essaycards/nuggets');
      if (isApiError(res)) {
        nuggetIndexCache = null;
        return {};
      }
      return Object.fromEntries(res.rows.map(r => [r.nugget_key, { id: r.id, title: r.title }]));
    })();
  }
  return nuggetIndexCache;
}

const nuggetPanelOverlayStyle: React.CSSProperties = {
  position: 'fixed',
  inset: 0,
  background: 'rgba(0,0,0,0.45)',
  display: 'flex',
  justifyContent: 'center',
  alignItems: 'flex-start',
  padding: '5vh 16px',
  zIndex: 1000,
  overflowY: 'auto',
};

const nuggetPanelStyle: React.CSSProperties = {
  background: 'var(--md-sys-color-surface)',
  borderRadius: 'var(--radius-card, 12px)',
  padding: 20,
  maxWidth: 640,
  width: '100%',
  boxShadow: 'var(--elevation-1)',
};

// In-page overlay/panel (component state, never a route change) — ReaderView
// and ReviewSessionView keep rendering underneath while it is open. Owns its
// own id-stack for recursive nugget-to-nugget navigation: pushed on
// click-through inside the panel's own body_markdown, popped on "← Back".
function NuggetPanel({ initialNuggetId, essayId, sectionId, onClose }: {
  initialNuggetId: string;
  essayId: string;
  sectionId: string;
  onClose: () => void;
}) {
  const navigate = useNavigate();
  const [stack, setStack] = useState<string[]>([initialNuggetId]);
  const currentId = stack[stack.length - 1];

  const [nugget, setNugget] = useState<NuggetDetailRow | null>(null);
  const [flashcards, setFlashcards] = useState<NuggetFlashcardRow[]>([]);
  const [sections, setSections] = useState<NuggetSectionRow[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  const [titleMap, setTitleMap] = useState<Record<string, string>>({});

  useEffect(() => {
    (async () => {
      const idx = await loadNuggetIndex();
      setTitleMap(Object.fromEntries(Object.entries(idx).map(([k, v]) => [k, v.title])));
    })();
  }, []);

  useEffect(() => {
    (async () => {
      setLoading(true);
      setError(null);
      setSections(null);
      const [detailRes, flashcardsRes] = await Promise.all([
        apiFetch<Dataset<NuggetDetailRow>>(`/essaycards/nuggets/${currentId}`),
        apiFetch<Dataset<NuggetFlashcardRow>>(`/essaycards/nuggets/${currentId}/flashcards`),
      ]);
      setLoading(false);
      if (isApiError(detailRes)) { setError(detailRes); return; }
      setNugget(detailRes.rows[0] ?? null);
      setFlashcards(isApiError(flashcardsRes) ? [] : flashcardsRes.rows);
    })();
  }, [currentId]);

  const openNested = async (key: string) => {
    const idx = await loadNuggetIndex();
    const entry = idx[key];
    if (entry) setStack(s => [...s, entry.id]);
  };

  const loadReferencedBy = async () => {
    const res = await apiFetch<Dataset<NuggetSectionRow>>(`/essaycards/nuggets/${currentId}/sections`);
    if (!isApiError(res)) setSections(res.rows);
  };

  return (
    <div style={nuggetPanelOverlayStyle} onClick={onClose}>
      <div style={nuggetPanelStyle} onClick={e => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          {stack.length > 1 ? (
            <button style={btnStyle} onClick={() => setStack(s => s.slice(0, -1))}>← Back</button>
          ) : <span />}
          <button style={btnStyle} onClick={onClose}>Close ✕</button>
        </div>

        {loading && <Skeleton />}
        {error && <ErrorCard error={error} />}

        {!loading && !error && nugget && (
          <>
            <h3 style={{ marginTop: 0 }}>{nugget.title}</h3>
            <div className="essaycards-section-body">
              <ReactMarkdown
                remarkPlugins={[[remarkNuggetRefs, titleMap]]}
                urlTransform={nuggetAwareUrlTransform}
                components={{ a: (p: any) => <NuggetLink {...p} onOpenNugget={openNested} /> }}
              >
                {nugget.body_markdown}
              </ReactMarkdown>
            </div>

            <div style={{ marginTop: 16 }}>
              <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 6 }}>Flashcards</div>
              {flashcards.length === 0 ? (
                <div style={{ color: '#888', fontSize: 13 }}>No flashcards yet for this nugget.</div>
              ) : (
                flashcards.map(fc => (
                  <div key={fc.id} style={{ fontSize: 13, marginBottom: 6 }}>
                    <strong>Q:</strong> {fc.question} <br /><strong>A:</strong> {fc.answer}
                  </div>
                ))
              )}
            </div>

            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 16 }}>
              <button style={btnStyle} onClick={loadReferencedBy}>Referenced by…</button>
              <button
                style={btnStyle}
                onClick={() => navigate(
                  `/essaycards/nuggets/authoring?essay_id=${essayId}&section_id=${sectionId}&nugget_id=${nugget.id}`,
                )}
              >
                Edit nugget
              </button>
              <button
                style={btnStyle}
                onClick={() => navigate(
                  `/essaycards/nuggets/${nugget.id}/generate-flashcards?essay_id=${essayId}&section_id=${sectionId}`,
                )}
              >
                Generate flashcards
              </button>
            </div>

            {sections && (
              <div style={{ marginTop: 12 }}>
                <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 6 }}>Referenced by</div>
                {sections.length === 0 ? (
                  <div style={{ color: '#888', fontSize: 13 }}>Not referenced by any section yet.</div>
                ) : (
                  sections.map(s => (
                    <div
                      key={s.section_id}
                      style={{ fontSize: 13, marginBottom: 4, cursor: 'pointer', color: 'var(--md-sys-color-primary)' }}
                      onClick={() => navigate(`/essaycards/essays/${s.essay_id}#${s.anchor_slug}`)}
                    >
                      {s.essay_title} — {s.heading}
                    </div>
                  ))
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

// The main spine's titleMap is the client-side union of every section's own
// `nuggets` field AND the essay's own `main_spine_nuggets` field — so a
// nugget referenced only in main_spine_markdown, never in any section, still
// resolves to a title instead of rendering as nugget-missing (11_design_
// review.md Minimal Change Set item 2).
function mainSpineTitleMap(essay: EssayDetailRow): Record<string, string> {
  const map: Record<string, string> = {};
  for (const section of essay.sections) for (const n of section.nuggets) map[n.nugget_key] = n.title;
  for (const n of essay.main_spine_nuggets) map[n.nugget_key] = n.title;
  return map;
}

// ── Essay List View ───────────────────────────────────────────────────────────

// Preferred display order for known overview categories. Anything not listed
// here sorts after these, alphabetically; essays with no category (null) go
// into a trailing "Uncategorized" group. This list is a UI-side convention —
// the backend stores `category` as free text and imposes no fixed set.
const CATEGORY_ORDER = ['Art', 'History', 'Philosophy'];
const UNCATEGORIZED = 'Uncategorized';

function categoryRank(name: string): number {
  const i = CATEGORY_ORDER.indexOf(name);
  if (i !== -1) return i;
  if (name === UNCATEGORIZED) return Number.MAX_SAFE_INTEGER;
  return CATEGORY_ORDER.length;
}

function groupEssaysByCategory(essays: EssayRow[]): [string, EssayRow[]][] {
  const groups = new Map<string, EssayRow[]>();
  for (const e of essays) {
    const key = e.category ?? UNCATEGORIZED;
    (groups.get(key) ?? groups.set(key, []).get(key)!).push(e);
  }
  for (const list of groups.values()) {
    list.sort((a, b) => a.sort_index - b.sort_index || a.title.localeCompare(b.title));
  }
  return [...groups.entries()].sort(
    ([a], [b]) => categoryRank(a) - categoryRank(b) || a.localeCompare(b),
  );
}

function formatExamDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}

const studyBtnStyle: React.CSSProperties = {
  ...btnStyle,
  padding: '4px 12px',
  fontSize: 12,
  flexShrink: 0,
  whiteSpace: 'nowrap',
};

// ── Category collapse/expand (Sprint12_FSRSAndUXOverhaul) ──────────────────
//
// Persisted per category name via localStorage, key
// essaycards:categoryCollapsed:<category> ('true'/'false'; UNCATEGORIZED for
// the null-category group). Default expanded (false) when no stored value
// exists. localStorage can throw (private browsing, disabled storage) — both
// helpers degrade gracefully to the default rather than erroring.

function categoryCollapseKey(category: string): string {
  return `essaycards:categoryCollapsed:${category}`;
}

function loadCategoryCollapsed(category: string): boolean {
  try {
    return localStorage.getItem(categoryCollapseKey(category)) === 'true';
  } catch {
    return false;
  }
}

function saveCategoryCollapsed(category: string, collapsed: boolean): void {
  try {
    localStorage.setItem(categoryCollapseKey(category), collapsed ? 'true' : 'false');
  } catch {
    /* localStorage unavailable — collapse state just won't persist across visits */
  }
}

// ── Learning-level badge (Sprint12_FSRSAndUXOverhaul) ───────────────────────
//
// Compact 0-4 level with a tooltip/accessible explanation of the four
// milestones and their current true/false state. Keyboard/touch-reachable
// via a native <button> with title (hover/focus tooltip) and aria-label
// (always-available accessible explanation, not hover-only).

const MILESTONE_LABELS: { key: keyof EssayRow; label: string }[] = [
  { key: 'milestone_all_cards_seen', label: 'All active cards seen' },
  { key: 'milestone_all_cards_future_safe', label: 'All active cards reviewed, next due in 24h+' },
  { key: 'milestone_guided_passed', label: 'Guided oral exam passed' },
  { key: 'milestone_unguided_passed', label: 'Unguided oral exam passed' },
];

function learningLevelExplanation(e: EssayRow): string {
  const lines = MILESTONE_LABELS.map(
    m => `${e[m.key] ? '✓' : '✗'} ${m.label}`,
  );
  const extra: string[] = [];
  if (e.guided_passed_at) extra.push(`Guided passed: ${formatExamDate(e.guided_passed_at)}`);
  if (e.unguided_passed_at) extra.push(`Unguided passed: ${formatExamDate(e.unguided_passed_at)}`);
  return [`Learning level ${e.learning_level} / 4`, ...lines, ...extra].join('\n');
}

const learningLevelBadgeStyle: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  minWidth: 36,
  height: 22,
  padding: '0 8px',
  borderRadius: 999,
  border: '1px solid var(--md-sys-color-outline-variant)',
  background: 'var(--md-sys-color-surface-variant)',
  color: 'var(--md-sys-color-on-surface-variant)',
  fontSize: 12,
  fontWeight: 600,
  cursor: 'default',
};

function LearningLevelBadge({ essay }: { essay: EssayRow }) {
  const explanation = learningLevelExplanation(essay);
  return (
    <button
      type="button"
      style={learningLevelBadgeStyle}
      title={explanation}
      aria-label={explanation}
      onClick={e => e.stopPropagation()}
    >
      {essay.learning_level}/4
    </button>
  );
}

function StatusPill({ status }: { status: 'planned' | 'complete' }) {
  const planned = status === 'planned';
  return (
    <span
      style={{
        fontSize: 10,
        fontWeight: 700,
        letterSpacing: 0.5,
        textTransform: 'uppercase',
        padding: '2px 6px',
        borderRadius: 4,
        color: planned ? '#8a6d1f' : '#3a7a3a',
        background: planned ? '#fdf3d8' : '#e6f4e6',
      }}
    >
      {status}
    </span>
  );
}

function CategoryCollapseToggle({ category, collapsed, onToggle }: {
  category: string;
  collapsed: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      style={{ ...btnStyle, padding: '2px 8px', fontSize: 12 }}
      aria-expanded={!collapsed}
      aria-label={`${collapsed ? 'Expand' : 'Collapse'} ${category}`}
      onClick={onToggle}
    >
      {collapsed ? '▸' : '▾'}
    </button>
  );
}

function EssayListView() {
  const navigate = useNavigate();
  const [essays, setEssays] = useState<EssayRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  // Category collapse state, keyed by category name (UNCATEGORIZED for the
  // null-category group) — read from localStorage on first render per
  // category, default expanded. A plain object (not a Set) so toggling one
  // category re-renders predictably via setState.
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

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

  const isCollapsed = (category: string) =>
    category in collapsed ? collapsed[category] : loadCategoryCollapsed(category);

  const toggleCategory = (category: string) => {
    const next = !isCollapsed(category);
    saveCategoryCollapsed(category, next);
    setCollapsed(prev => ({ ...prev, [category]: next }));
  };

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
          <button style={btnStyle} onClick={() => navigate('/essaycards/explore/import')}>
            Import exploration
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
      {!loading && !error && essays.length > 0 && (() => {
        const groups = groupEssaysByCategory(essays);
        const showHeadings = !(groups.length === 1 && groups[0][0] === UNCATEGORIZED);
        return groups.map(([category, rows]) => {
          const isTopic = category !== UNCATEGORIZED;
          const est = rows.reduce((n, e) => n + e.progress_established, 0);
          const tot = rows.reduce((n, e) => n + e.progress_total, 0);
          const open = rows.reduce((n, e) => n + e.open_count, 0);
          const categoryCollapsed = showHeadings && isCollapsed(category);
          return (
            <div key={category} style={{ marginBottom: 24 }}>
              {showHeadings && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, margin: '0 0 8px', padding: '0 12px' }}>
                  <CategoryCollapseToggle
                    category={category}
                    collapsed={categoryCollapsed}
                    onToggle={() => toggleCategory(category)}
                  />
                  <div
                    style={{
                      fontSize: 12,
                      fontWeight: 700,
                      letterSpacing: 0.6,
                      textTransform: 'uppercase',
                      color: '#666',
                    }}
                  >
                    {category}
                  </div>
                  {isTopic && tot > 0 && (
                    <>
                      <div style={{ fontSize: 12, color: '#999' }}>
                        {est} / {tot} established · {open} open
                      </div>
                      <button
                        style={{ ...studyBtnStyle, marginLeft: 'auto' }}
                        onClick={() => navigate(`/essaycards/review?topic=${encodeURIComponent(category)}`)}
                      >
                        Study
                      </button>
                    </>
                  )}
                </div>
              )}
              {!categoryCollapsed && rows.map(e => (
                <div
                  key={e.id}
                  onClick={() => navigate(`/essaycards/essays/${e.id}`)}
                  style={{
                    padding: 12,
                    borderRadius: 8,
                    border: '1px solid #e0e0e0',
                    marginBottom: 8,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: 10,
                  }}
                >
                  <span style={{ fontSize: 12, color: '#bbb', minWidth: 16, textAlign: 'right', lineHeight: '20px' }}>
                    {e.sort_index}
                  </span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
                      <span style={{ fontWeight: 600 }}>{e.title}</span>
                      <StatusPill status={e.status} />
                    </div>
                    <div style={{ fontSize: 12, color: '#888', marginTop: 3 }}>
                      {e.progress_total === 0
                        ? 'No flashcards yet'
                        : `Progress: ${e.progress_established} / ${e.progress_total} · Open: ${e.open_count}`}
                    </div>
                  </div>
                  <LearningLevelBadge essay={e} />
                </div>
              ))}
            </div>
          );
        });
      })()}
    </div>
  );
}

// ── Sentence feedback (Sprint13_ReviewStatsSentenceFeedback) ─────────────────
//
// Sentence boundaries come ONLY from GET /essays/{id}/sentences (backend
// split_sentences) — never re-split client-side. Each sentence is an
// independent ReactMarkdown instance (paragraph wrapper flattened so sentences
// flow inline). Tapping a sentence opens SentenceFeedbackPopover; links inside
// a sentence stopPropagation (NuggetLink) so they never also open it.

interface SentenceRow { section_id: string; sentence_index: number; text: string }
interface SentenceFeedbackRow {
  section_id: string; sentence_index: number; sentence_text: string;
  is_difficult: boolean; is_thumbs_up: boolean;
}
type FeedbackFlags = { is_difficult: boolean; is_thumbs_up: boolean };
type FeedbackMap = Record<string, FeedbackFlags>;
const feedbackKey = (sectionId: string, index: number) => `${sectionId}:${index}`;

function SectionSentences({ sentences, nuggetTitles, feedback, openIndex, onTap, onOpenNugget }: {
  sentences: SentenceRow[];
  nuggetTitles: Record<string, string>;
  feedback: FeedbackMap;
  openIndex: number | null;
  onTap: (index: number, el: HTMLElement) => void;
  onOpenNugget: (key: string) => void;
}) {
  return (
    <p>
      {sentences.map(sn => {
        const fb = feedback[feedbackKey(sn.section_id, sn.sentence_index)];
        return (
          <React.Fragment key={sn.sentence_index}>
            <span
              data-sentence-index={sn.sentence_index}
              onClick={e => onTap(sn.sentence_index, e.currentTarget)}
              style={{
                cursor: 'pointer',
                background: openIndex === sn.sentence_index ? 'var(--md-sys-color-surface-variant)' : undefined,
              }}
            >
              <ReactMarkdown
                remarkPlugins={[[remarkNuggetRefs, nuggetTitles]]}
                urlTransform={nuggetAwareUrlTransform}
                components={{
                  a: (p: any) => <NuggetLink {...p} onOpenNugget={onOpenNugget} />,
                  p: ({ children }: any) => <>{children}</>,
                }}
              >
                {sn.text}
              </ReactMarkdown>
              {fb && (
                <span data-testid="sentence-indicator" style={{ fontSize: 11, marginLeft: 2, opacity: 0.8 }}>
                  {fb.is_difficult && <span title="Marked difficult">⚠</span>}
                  {fb.is_thumbs_up && <span title="Thumbs up">👍</span>}
                </span>
              )}
            </span>{' '}
          </React.Fragment>
        );
      })}
    </p>
  );
}

function SentenceFeedbackPopover({ top, left, flags, onToggle }: {
  top: number;
  left: number;
  flags: FeedbackFlags;
  onToggle: (flag: 'difficult' | 'thumbs_up') => void;
}) {
  const btn = (label: string, icon: string, flag: 'difficult' | 'thumbs_up', active: boolean) => (
    <button
      type="button"
      aria-pressed={active}
      onClick={() => onToggle(flag)}
      style={{
        padding: '6px 10px',
        borderRadius: 8,
        cursor: 'pointer',
        fontSize: 13,
        border: `1px solid ${active ? 'var(--md-sys-color-primary)' : 'var(--md-sys-color-outline)'}`,
        background: active ? 'var(--md-sys-color-primary)' : 'transparent',
        color: active ? 'var(--md-sys-color-on-primary, #fff)' : 'var(--md-sys-color-on-surface)',
      }}
    >
      {icon} {label}
    </button>
  );
  return (
    <div
      data-testid="sentence-feedback-popover"
      style={{
        position: 'fixed', top, left, zIndex: 50, display: 'flex', gap: 8, padding: 8,
        background: 'var(--md-sys-color-surface)', border: '1px solid var(--md-sys-color-outline-variant)',
        borderRadius: 10, boxShadow: '0 2px 8px rgba(0,0,0,0.2)',
      }}
    >
      {btn('Difficult', '⚠', 'difficult', flags.is_difficult)}
      {btn('Thumbs up', '👍', 'thumbs_up', flags.is_thumbs_up)}
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
  // Sprint09_Nuggets: the currently-open NuggetPanel (null = closed), plus
  // the essay/section context it was opened from (needed by the panel's
  // "Edit nugget" / "Generate flashcards" entry points).
  const [activeNugget, setActiveNugget] = useState<{ nuggetId: string; sectionId: string } | null>(null);

  // Resolves a clicked [[nugget:key]] reference's id (via the cached
  // key->id index) and opens the panel — never a route navigation, so
  // ReaderView itself never unmounts and scroll position is preserved.
  const openNuggetByKey = useCallback(async (key: string, sectionId: string) => {
    const idx = await loadNuggetIndex();
    const entry = idx[key];
    if (entry) setActiveNugget({ nuggetId: entry.id, sectionId });
  }, []);
  // "Export section" / "Insert section after" — one message slot, keyed to
  // the section and action it was shown for, since only one is ever in
  // flight at a time. `ok` drives the button's copied -> "Import" toggle;
  // `text` also carries failure messages, which must NOT toggle the button.
  const [sectionActionMsg, setSectionActionMsg] = useState<
    { sectionId: string; kind: 'export' | 'insert'; ok: boolean; text: string } | null
  >(null);

  const sectionActionReady = (sectionId: string, kind: 'export' | 'insert') =>
    sectionActionMsg?.sectionId === sectionId && sectionActionMsg.kind === kind && sectionActionMsg.ok;

  // "Export essay" — same toggle-to-Import pattern as the per-section
  // buttons, one level up (no sectionId to key on; only one essay on this
  // page).
  const [essayExportMsg, setEssayExportMsg] = useState<{ ok: boolean; text: string } | null>(null);

  // Oral-exam export (moved here from EssayListView, internal_flow step 11):
  // copies the essay's examination package + the exam_type-appropriate
  // rubric prompt to the clipboard.
  const [examMsg, setExamMsg] = useState<string | null>(null);
  const [examBusyType, setExamBusyType] = useState<'guided' | 'unguided' | null>(null);

  const handleExportExam = async (examType: 'guided' | 'unguided') => {
    if (!essay) return;
    setExamBusyType(examType);
    setExamMsg(null);
    const res = await apiFetch<ExaminationPackage>(
      `/essaycards/essays/${essay.id}/examination-package?exam_type=${examType}`,
    );
    setExamBusyType(null);
    if (isApiError(res)) {
      setExamMsg(`Export failed: ${res.error.message}`);
      return;
    }
    const err = await writeClipboard(buildExamClipboardText(res, examType));
    setExamMsg(
      err ??
        'Copied. Paste into ChatGPT (or similar), conduct the examination, then paste its JSON reply ' +
          'into "Import exam results" on the essay list page.',
    );
  };

  const handleExportEssay = async () => {
    if (!essay) return;
    setEssayExportMsg(null);
    const res = await apiFetch<EssayExportPackage>(`/essaycards/essays/${essay.id}/export`);
    if (isApiError(res)) {
      setEssayExportMsg({ ok: false, text: `Export failed: ${res.error.message}` });
      return;
    }
    const err = await writeClipboard(buildEssayExportClipboardText(res));
    setEssayExportMsg({
      ok: !err,
      text:
        err ??
        'Copied. Paste into ChatGPT (or similar), have it revise whichever sections you direct, then ' +
          'paste its JSON reply into "Add / Update Essay" to save it.',
    });
  };

  const handleExportSection = async (sectionId: string) => {
    if (!essay) return;
    setSectionActionMsg(null);
    const res = await apiFetch<SectionExportPackage>(
      `/essaycards/essays/${essay.id}/sections/${sectionId}/export`
    );
    if (isApiError(res)) {
      setSectionActionMsg({ sectionId, kind: 'export', ok: false, text: `Export failed: ${res.error.message}` });
      return;
    }
    // Stash this section's CURRENTLY required nugget keys, keyed by
    // section_id, so IngestView can later detect an accidental drop (see
    // extractNuggetKeysClient / internal_flow step 10). Read once and
    // cleared by IngestView on parse.
    try {
      sessionStorage.setItem(
        `essaycards:sectionExport:${sectionId}`,
        JSON.stringify(res.focus_section_nuggets.map(n => n.nugget_key)),
      );
    } catch { /* sessionStorage unavailable — drop-detection degrades gracefully to no-op */ }

    const err = await writeClipboard(buildSectionExportClipboardText(res));
    setSectionActionMsg({
      sectionId,
      kind: 'export',
      ok: !err,
      text:
        err ??
        'Copied. Paste into ChatGPT (or similar), have it revise the section, then paste its JSON ' +
          'reply into "Add / Update Essay" to save it.',
    });
  };

  const handleInsertSection = async (sectionId: string) => {
    if (!essay) return;
    setSectionActionMsg(null);
    const res = await apiFetch<SectionExportPackage>(
      `/essaycards/essays/${essay.id}/sections/${sectionId}/export`
    );
    if (isApiError(res)) {
      setSectionActionMsg({ sectionId, kind: 'insert', ok: false, text: `Export failed: ${res.error.message}` });
      return;
    }
    const err = await writeClipboard(buildSectionInsertClipboardText(res));
    setSectionActionMsg({
      sectionId,
      kind: 'insert',
      ok: !err,
      text:
        err ??
        'Copied. Paste into ChatGPT (or similar), have it write the new section, then paste its JSON ' +
          'reply into "Add / Update Essay" to save it.',
    });
  };

  // Sprint13 sentence feedback: server-computed sentences + saved flags.
  const [sentences, setSentences] = useState<SentenceRow[]>([]);
  const [feedback, setFeedback] = useState<FeedbackMap>({});
  const [openSentence, setOpenSentence] =
    useState<{ sectionId: string; index: number; text: string; top: number; left: number } | null>(null);
  const [feedbackError, setFeedbackError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    const res = await apiFetch<Dataset<EssayDetailRow>>(`/essaycards/essays/${id}`);
    if (isApiError(res)) {
      setLoading(false);
      setError(res);
      return;
    }
    // Sentence endpoints are best-effort: on failure the reader falls back to
    // rendering each section's whole body (see sentencesBySection below).
    const [sentRes, fbRes] = await Promise.all([
      apiFetch<Dataset<SentenceRow>>(`/essaycards/essays/${id}/sentences`),
      apiFetch<Dataset<SentenceFeedbackRow>>(`/essaycards/essays/${id}/sentence-feedback`),
    ]);
    setSentences(isApiError(sentRes) ? [] : sentRes.rows);
    setFeedback(
      isApiError(fbRes)
        ? {}
        : Object.fromEntries(
            fbRes.rows.map(r => [
              feedbackKey(r.section_id, r.sentence_index),
              { is_difficult: r.is_difficult, is_thumbs_up: r.is_thumbs_up },
            ]),
          ),
    );
    setLoading(false);
    setEssay(res.rows[0] ?? null);
  }, [id]);

  useEffect(() => { load(); }, [load]);

  // Close the popover on any press outside it and outside a sentence (a press
  // on a sentence is handled by that sentence's own toggle).
  useEffect(() => {
    if (!openSentence) return;
    const onDown = (e: MouseEvent | TouchEvent) => {
      const t = e.target as HTMLElement | null;
      if (t?.closest('[data-testid="sentence-feedback-popover"], [data-sentence-index]')) return;
      setOpenSentence(null);
    };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('touchstart', onDown);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('touchstart', onDown);
    };
  }, [openSentence]);

  const toggleFlag = async (flag: 'difficult' | 'thumbs_up') => {
    if (!openSentence) return;
    const { sectionId, index, text } = openSentence;
    const key = feedbackKey(sectionId, index);
    const prev = feedback[key] ?? { is_difficult: false, is_thumbs_up: false };
    const value = flag === 'difficult' ? !prev.is_difficult : !prev.is_thumbs_up;
    const next: FeedbackFlags = flag === 'difficult'
      ? { ...prev, is_difficult: value }
      : { ...prev, is_thumbs_up: value };
    const apply = (f: FeedbackFlags | null) =>
      setFeedback(m => {
        const copy = { ...m };
        if (f && (f.is_difficult || f.is_thumbs_up)) copy[key] = f; else delete copy[key];
        return copy;
      });
    setFeedbackError(null);
    apply(next); // optimistic
    const res = await apiFetch<FeedbackFlags>(`/essaycards/sections/${sectionId}/sentence-feedback`, {
      method: 'PATCH',
      body: JSON.stringify({ sentence_index: index, sentence_text: text, flag, value }),
    });
    if (isApiError(res)) {
      apply(prev);
      setFeedbackError(res.error.message);
    }
  };

  const handleSentenceTap = (sectionId: string, index: number, text: string, el: HTMLElement) => {
    if (openSentence && openSentence.sectionId === sectionId && openSentence.index === index) {
      setOpenSentence(null);
      return;
    }
    const r = el.getBoundingClientRect();
    setOpenSentence({
      sectionId, index, text,
      top: Math.min(r.bottom + 4, window.innerHeight - 56),
      left: Math.max(8, Math.min(r.left, window.innerWidth - 220)),
    });
  };

  // "Jump to passage" navigates here with a #anchor_slug hash — scroll to it
  // once the essay (and its section DOM anchors) has rendered.
  useEffect(() => {
    if (!loading && essay && location.hash) {
      const el = document.getElementById(location.hash.slice(1));
      el?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [loading, essay, location.hash]);

  if (loading) return <div style={pageStyle}><Skeleton /></div>;
  if (error) return <div style={pageStyle}><ErrorCard error={error} /></div>;
  if (!essay) return <div style={pageStyle}>Essay not found.</div>;

  const hasCards = essay.progress_total > 0;
  const questionOverviewItem: ActionMenuItem = {
    label: 'Question overview',
    onClick: () => navigate(`/essaycards/essays/${essay.id}/questions`),
  };
  const secondaryItems: ActionMenuItem[] = [
    ...(hasCards ? [questionOverviewItem] : []),
    {
      label: examBusyType === 'guided' ? 'Preparing…' : 'Guided oral exam',
      onClick: () => handleExportExam('guided'),
      disabled: essay.status !== 'complete' || examBusyType !== null,
    },
    {
      label: examBusyType === 'unguided' ? 'Preparing…' : 'Unguided oral exam',
      onClick: () => handleExportExam('unguided'),
      disabled: essay.status !== 'complete' || examBusyType !== null,
    },
    {
      label: essayExportMsg?.ok ? 'Import essay →' : 'Export essay',
      onClick: () => (essayExportMsg?.ok ? navigate('/essaycards/ingest') : handleExportEssay()),
    },
    ...(essay.sections.length > 0
      ? [{
          label: '+ New nugget',
          onClick: () => navigate(
            `/essaycards/nuggets/authoring?essay_id=${essay.id}&section_id=${essay.sections[0].id}`,
          ),
        }]
      : []),
  ];

  return (
    <div style={pageStyle}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
        <button style={btnStyle} onClick={() => navigate('/essaycards')}>
          ← All essays
        </button>
        <ActionMenu
          primary={
            hasCards
              ? { label: 'Study', onClick: () => navigate(`/essaycards/review?essay_id=${essay.id}`) }
              : questionOverviewItem
          }
          items={secondaryItems}
        />
        <LearningLevelBadge essay={essay} />
      </div>
      {essayExportMsg && (
        <div style={{ fontSize: 12, color: '#888', marginBottom: 12 }}>{essayExportMsg.text}</div>
      )}
      {examMsg && (
        <div style={{ fontSize: 12, color: '#888', marginBottom: 12 }}>{examMsg}</div>
      )}
      <h1 style={{ marginBottom: 12 }}>{essay.title}</h1>

      {essay.main_spine_markdown.trim() !== '' && (
        <div
          className="essaycards-section-body"
          style={{
            marginBottom: 24,
            padding: '12px 16px',
            borderLeft: '3px solid var(--md-sys-color-primary)',
            background: 'var(--md-sys-color-surface-variant, transparent)',
          }}
        >
          <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: 0.5, textTransform: 'uppercase', color: '#888', marginBottom: 4 }}>
            Main spine
          </div>
          <ReactMarkdown
            remarkPlugins={[[remarkNuggetRefs, mainSpineTitleMap(essay)]]}
            urlTransform={nuggetAwareUrlTransform}
            components={{ a: (p: any) => <NuggetLink {...p} onOpenNugget={key => openNuggetByKey(key, essay.sections[0]?.id ?? '')} /> }}
          >
            {essay.main_spine_markdown}
          </ReactMarkdown>
        </div>
      )}

      {essay.sections.length === 0 && (
        <div style={{ color: '#888', fontSize: 14 }}>This essay has no sections yet.</div>
      )}

      {essay.sections.map(section => (
        <section key={section.id} id={section.anchor_slug} style={{ marginBottom: 32 }}>
          <h2>{section.heading}</h2>
          <div className="essaycards-section-body">
            {(() => {
              const titles = Object.fromEntries(section.nuggets.map(n => [n.nugget_key, n.title]));
              const sectionSentences = sentences.filter(sn => sn.section_id === section.id);
              if (sectionSentences.length === 0) {
                // No server sentences (empty section or sentence fetch failed): plain render.
                return (
                  <ReactMarkdown
                    remarkPlugins={[[remarkNuggetRefs, titles]]}
                    urlTransform={nuggetAwareUrlTransform}
                    components={{ a: (p: any) => <NuggetLink {...p} onOpenNugget={key => openNuggetByKey(key, section.id)} /> }}
                  >
                    {section.body_markdown}
                  </ReactMarkdown>
                );
              }
              return (
                <SectionSentences
                  sentences={sectionSentences}
                  nuggetTitles={titles}
                  feedback={feedback}
                  openIndex={openSentence?.sectionId === section.id ? openSentence.index : null}
                  onTap={(index, el) =>
                    handleSentenceTap(section.id, index, sectionSentences[index].text, el)
                  }
                  onOpenNugget={key => openNuggetByKey(key, section.id)}
                />
              );
            })()}
          </div>
          <ActionMenu
            primary={{
              label: 'Review this section',
              onClick: () => navigate(`/essaycards/review?essay_id=${essay.id}&section_id=${section.id}`),
            }}
            items={[
              {
                label: sectionActionReady(section.id, 'export') ? 'Import section →' : 'Export section',
                onClick: () =>
                  sectionActionReady(section.id, 'export')
                    ? navigate('/essaycards/ingest')
                    : handleExportSection(section.id),
              },
              {
                label: sectionActionReady(section.id, 'insert') ? 'Import insertion →' : 'Insert section after',
                onClick: () =>
                  sectionActionReady(section.id, 'insert')
                    ? navigate('/essaycards/ingest')
                    : handleInsertSection(section.id),
              },
            ]}
          />
          {sectionActionMsg && sectionActionMsg.sectionId === section.id && (
            <div style={{ fontSize: 12, color: '#888', marginTop: 4 }}>{sectionActionMsg.text}</div>
          )}
          <SectionExaminationHistory sectionId={section.id} />
        </section>
      ))}

      {openSentence && (
        <SentenceFeedbackPopover
          top={openSentence.top}
          left={openSentence.left}
          flags={feedback[feedbackKey(openSentence.sectionId, openSentence.index)] ?? { is_difficult: false, is_thumbs_up: false }}
          onToggle={toggleFlag}
        />
      )}
      {feedbackError && (
        <div role="alert" style={{ position: 'fixed', bottom: 8, left: 8, right: 8, fontSize: 12, color: '#b00020' }}>
          {feedbackError}
        </div>
      )}

      {activeNugget && (
        <NuggetPanel
          initialNuggetId={activeNugget.nuggetId}
          essayId={essay.id}
          sectionId={activeNugget.sectionId}
          onClose={() => setActiveNugget(null)}
        />
      )}
    </div>
  );
}

// ── Question Overview (Sprint08_QuestionLevelsAndStructure) ─────────────────
//
// Editorial/narrative overview of one essay's questions — NOT a review
// screen. Hierarchy: essay -> sections (essay order) -> questions grouped by
// level (ascending). Purpose: let the reader see the essay's question
// skeleton at a glance — a section with no Level 1 entries visibly lacks a
// foundational question; too many Level 3 entries and too few Level 1/2
// visibly signals "too much detail, not enough structure".
//
// Levels 1/2/3 always render (even empty, with a muted "none yet" line) so a
// gap is something you SEE, not something you have to infer from a missing
// heading; any level beyond 3 present in the data renders after them,
// ascending — the schema is intentionally open-ended upward (schema.sql
// ck_flashcards_level only enforces >= 1).

const LEVEL_DESCRIPTIONS: Record<number, string> = {
  1: 'Foundational / spine',
  2: 'Building / explanatory structure',
  3: 'Decorating — examples, terminology, anecdotes, supporting detail',
};

function levelLabel(level: number): string {
  const desc = LEVEL_DESCRIPTIONS[level];
  return desc ? `Level ${level} — ${desc}` : `Level ${level}`;
}

// Level 1 reads as the bold load-bearing structure, 2 as the explanatory
// layer, 3+ progressively lighter/supporting — via the existing Material 3
// tokens already used throughout this app, not a new palette.
function levelBorderColor(level: number): string {
  if (level <= 1) return 'var(--md-sys-color-primary)';
  if (level === 2) return 'var(--md-sys-color-outline)';
  return 'var(--md-sys-color-outline-variant)';
}

const questionFieldStyle: React.CSSProperties = {
  width: '100%',
  fontSize: 13,
  padding: 6,
  boxSizing: 'border-box',
  border: '1px solid #ccc',
  borderRadius: 6,
  marginBottom: 6,
};

interface SectionQuestionGroup {
  section: SectionRow;
  levels: { level: number; questions: QuestionRow[] }[];
}

function groupQuestionsBySection(sections: SectionRow[], questions: QuestionRow[]): SectionQuestionGroup[] {
  const bySection = new Map<string, QuestionRow[]>();
  for (const q of questions) {
    const list = bySection.get(q.section_id);
    if (list) list.push(q); else bySection.set(q.section_id, [q]);
  }
  return sections.map(section => {
    const inSection = bySection.get(section.id) ?? [];
    const byLevel = new Map<number, QuestionRow[]>();
    for (const q of inSection) {
      const list = byLevel.get(q.level);
      if (list) list.push(q); else byLevel.set(q.level, [q]);
    }
    const levelKeys = Array.from(new Set([1, 2, 3, ...byLevel.keys()])).sort((a, b) => a - b);
    return {
      section,
      levels: levelKeys.map(level => ({ level, questions: byLevel.get(level) ?? [] })),
    };
  });
}

function QuestionOverviewView() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [essay, setEssay] = useState<EssayDetailRow | null>(null);
  const [questions, setQuestions] = useState<QuestionRow[]>([]);
  const [nuggets, setNuggets] = useState<NuggetListRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    const [essayRes, questionsRes] = await Promise.all([
      apiFetch<Dataset<EssayDetailRow>>(`/essaycards/essays/${id}`),
      apiFetch<Dataset<QuestionRow>>(`/essaycards/essays/${id}/questions`),
    ]);
    setLoading(false);
    if (isApiError(essayRes)) { setError(essayRes); return; }
    if (isApiError(questionsRes)) { setError(questionsRes); return; }
    setEssay(essayRes.rows[0] ?? null);
    setQuestions(questionsRes.rows);
  }, [id]);

  useEffect(() => { load(); }, [load]);

  // Nugget options for the edit form's nugget <select> — fetched once per
  // view mount (not per question), per 11_design_review.md Minimal Change
  // Set item 3.
  useEffect(() => {
    (async () => {
      const res = await apiFetch<Dataset<NuggetListRow>>('/essaycards/nuggets');
      if (!isApiError(res)) setNuggets(res.rows);
    })();
  }, []);

  if (loading) return <div style={pageStyle}><Skeleton /></div>;
  if (error) return <div style={pageStyle}><ErrorCard error={error} /></div>;
  if (!essay) return <div style={pageStyle}>Essay not found.</div>;

  const groups = groupQuestionsBySection(essay.sections, questions);

  return (
    <div style={pageStyle}>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
        <button style={btnStyle} onClick={() => navigate(`/essaycards/essays/${essay.id}`)}>
          ← Reader
        </button>
        <button style={btnStyle} onClick={() => navigate('/essaycards/questions/import')}>
          Import question
        </button>
      </div>
      <h1 style={{ marginBottom: 4 }}>{essay.title}</h1>
      <div style={{ fontSize: 13, color: '#888', marginBottom: 24 }}>Question overview</div>

      {groups.length === 0 && (
        <div style={{ color: '#888', fontSize: 14 }}>This essay has no sections yet.</div>
      )}

      {groups.map(group => (
        <SectionQuestionGroupView
          key={group.section.id}
          essaySlug={essay.slug}
          group={group}
          nuggets={nuggets}
          onChanged={load}
        />
      ))}
    </div>
  );
}

function SectionQuestionGroupView({ essaySlug, group, nuggets, onChanged }: {
  essaySlug: string;
  group: SectionQuestionGroup;
  nuggets: NuggetListRow[];
  onChanged: () => void;
}) {
  const [addingLevel, setAddingLevel] = useState<number | null>(null);

  return (
    <section style={{ marginBottom: 32 }}>
      <h2 style={{ marginBottom: 8 }}>{group.section.heading}</h2>
      {group.levels.map(({ level, questions }) => (
        <div
          key={level}
          style={{ marginBottom: 16, paddingLeft: 12, borderLeft: `3px solid ${levelBorderColor(level)}` }}
        >
          <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 6 }}>{levelLabel(level)}</div>
          {questions.length === 0 ? (
            <div style={{ color: '#aaa', fontSize: 13, marginBottom: 6 }}>No questions at this level yet.</div>
          ) : (
            questions.map(q => (
              <QuestionItem key={q.id} essaySlug={essaySlug} question={q} nuggets={nuggets} onChanged={onChanged} />
            ))
          )}
          <button
            style={{ ...btnStyle, fontSize: 12, padding: '2px 10px' }}
            onClick={() => setAddingLevel(addingLevel === level ? null : level)}
          >
            {addingLevel === level ? 'Cancel' : '+ Add question'}
          </button>
          {addingLevel === level && (
            <AddQuestionForm
              essaySlug={essaySlug}
              sectionId={group.section.id}
              defaultLevel={level}
              onDone={() => { setAddingLevel(null); onChanged(); }}
            />
          )}
        </div>
      ))}
    </section>
  );
}

function QuestionItem({ essaySlug, question, nuggets, onChanged }: {
  essaySlug: string;
  question: QuestionRow;
  nuggets: NuggetListRow[];
  onChanged: () => void;
}) {
  const navigate = useNavigate();
  const [editing, setEditing] = useState(false);
  const [q, setQ] = useState(question.question);
  const [a, setA] = useState(question.answer);
  const [level, setLevel] = useState(question.level);
  // '' represents "No nugget" in the <select> — mapped to explicit null on
  // save, never omitted (R-CON-AL-05 round trip: UI representation of the
  // cleared state = the selectable "No nugget" option; payload = explicit
  // id or null, never omission).
  const [nuggetId, setNuggetId] = useState<string>(question.nugget_id ?? '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [exportMsg, setExportMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const handleStartEdit = () => {
    setQ(question.question);
    setA(question.answer);
    setLevel(question.level);
    setNuggetId(question.nugget_id ?? '');
    setError(null);
    setEditing(true);
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    const res = await apiFetch<QuestionUpsertResult>('/essaycards/flashcards/upsert', {
      method: 'POST',
      body: JSON.stringify({
        essay_slug: essaySlug,
        section_id: question.section_id,
        card: { id: question.card_key, level, q, a, nugget_id: nuggetId === '' ? null : nuggetId },
      }),
    });
    setSaving(false);
    if (isApiError(res)) {
      setError(res);
      return;
    }
    setEditing(false);
    onChanged();
  };

  const handleExport = async () => {
    setExportMsg(null);
    const res = await apiFetch<QuestionExportPackage>(`/essaycards/flashcards/${question.id}/export`);
    if (isApiError(res)) {
      setExportMsg({ ok: false, text: `Export failed: ${res.error.message}` });
      return;
    }
    const err = await writeClipboard(buildQuestionExportClipboardText(res));
    setExportMsg({
      ok: !err,
      text:
        err ??
        'Copied. Paste into ChatGPT (or similar), discuss and improve the question, then paste its ' +
          'JSON reply into "Import question" to save it.',
    });
  };

  if (!editing) {
    return (
      <div style={{ marginBottom: 8 }}>
        <div style={{ fontSize: 14 }}>{question.question}</div>
        <div style={{ display: 'flex', gap: 6, marginTop: 2 }}>
          <button style={{ ...btnStyle, fontSize: 12, padding: '2px 10px' }} onClick={handleStartEdit}>
            Edit
          </button>
          <button
            style={{ ...btnStyle, fontSize: 12, padding: '2px 10px' }}
            onClick={() =>
              exportMsg?.ok ? navigate('/essaycards/questions/import') : handleExport()
            }
          >
            {exportMsg?.ok ? 'Import →' : 'Export'}
          </button>
        </div>
        {exportMsg && (
          <div style={{ fontSize: 12, color: '#888', marginTop: 2 }}>{exportMsg.text}</div>
        )}
      </div>
    );
  }

  return (
    <div style={{ marginBottom: 12, padding: 8, background: 'var(--md-sys-color-surface)', borderRadius: 6 }}>
      <textarea value={q} onChange={e => setQ(e.target.value)} rows={2} style={questionFieldStyle} placeholder="Question" />
      <textarea value={a} onChange={e => setA(e.target.value)} rows={2} style={questionFieldStyle} placeholder="Answer" />
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
        <label style={{ fontSize: 12 }}>Level</label>
        <input
          type="number"
          min={1}
          value={level}
          onChange={e => setLevel(Math.max(1, parseInt(e.target.value, 10) || 1))}
          style={{ width: 60, fontSize: 13, padding: 4, border: '1px solid #ccc', borderRadius: 6 }}
        />
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
        <label style={{ fontSize: 12 }}>Nugget</label>
        <select
          value={nuggetId}
          onChange={e => setNuggetId(e.target.value)}
          style={{ fontSize: 13, padding: 4, border: '1px solid #ccc', borderRadius: 6, flex: 1 }}
        >
          <option value="">No nugget</option>
          {nuggets.map(n => (
            <option key={n.id} value={n.id}>{n.title}</option>
          ))}
        </select>
      </div>
      <div style={{ display: 'flex', gap: 6 }}>
        <button style={primaryBtnStyle} disabled={saving || !q.trim() || !a.trim()} onClick={handleSave}>
          {saving ? 'Saving…' : 'Save'}
        </button>
        <button style={btnStyle} onClick={() => setEditing(false)}>Cancel</button>
      </div>
      {error && <div style={{ marginTop: 8 }}><ErrorCard error={error} /></div>}
    </div>
  );
}

function AddQuestionForm({ essaySlug, sectionId, defaultLevel, onDone }: {
  essaySlug: string;
  sectionId: string;
  defaultLevel: number;
  onDone: () => void;
}) {
  const [q, setQ] = useState('');
  const [a, setA] = useState('');
  const [level, setLevel] = useState(defaultLevel);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  const handleAdd = async () => {
    setSaving(true);
    setError(null);
    // card.id omitted -> backend auto-generates a fresh id.
    const res = await apiFetch<QuestionUpsertResult>('/essaycards/flashcards/upsert', {
      method: 'POST',
      body: JSON.stringify({ essay_slug: essaySlug, section_id: sectionId, card: { level, q, a } }),
    });
    setSaving(false);
    if (isApiError(res)) {
      setError(res);
      return;
    }
    onDone();
  };

  return (
    <div style={{ marginTop: 8, padding: 8, background: 'var(--md-sys-color-surface)', borderRadius: 6 }}>
      <textarea value={q} onChange={e => setQ(e.target.value)} rows={2} style={questionFieldStyle} placeholder="New question" />
      <textarea value={a} onChange={e => setA(e.target.value)} rows={2} style={questionFieldStyle} placeholder="Answer" />
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
        <label style={{ fontSize: 12 }}>Level</label>
        <input
          type="number"
          min={1}
          value={level}
          onChange={e => setLevel(Math.max(1, parseInt(e.target.value, 10) || 1))}
          style={{ width: 60, fontSize: 13, padding: 4, border: '1px solid #ccc', borderRadius: 6 }}
        />
      </div>
      <div style={{ display: 'flex', gap: 6 }}>
        <button style={primaryBtnStyle} disabled={saving || !q.trim() || !a.trim()} onClick={handleAdd}>
          {saving ? 'Adding…' : 'Add question'}
        </button>
      </div>
      {error && <div style={{ marginTop: 8 }}><ErrorCard error={error} /></div>}
    </div>
  );
}

// ── Question Import View ─────────────────────────────────────────────────────
//
// Paste ChatGPT's JSON reply from a single-question export (see
// QUESTION_EXPORT_PROMPT_INTRO). Same paste/submit pattern as
// IngestView/ImportExaminationsView/ExploreImportView: the raw pasted text
// goes straight to POST /flashcards/upsert as the request body — no
// client-side JSON.parse/re-stringify — so the backend's own manual
// request.json() parse (or reject) sees exactly what was pasted.

const QUESTION_IMPORT_PLACEHOLDER_JSON = `{
  "essay_slug": "what_can_we_know",
  "section_id": "7402691f-edbd-4408-8f1c-dbd23916e5a6",
  "card": {
    "id": "plato-appearances-6",
    "level": 3,
    "q": "In Plato's Meno, what was he trying to demonstrate with the example of the road to Larissa?",
    "a": "That a true belief can guide action just as successfully as knowledge, but knowledge is more secure because the true belief is tethered by an account of why it is correct."
  }
}`;

function QuestionImportView() {
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
      <div style={{ fontSize: 13, color: '#888', marginBottom: 12 }}>
        Paste ChatGPT's JSON reply from a single-question export (started with "Export" on a question
        in that essay's question overview). Only the named card is created or updated — everything else
        in the essay is left untouched.
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
        rows={14}
        style={{
          width: '100%',
          fontFamily: 'monospace',
          fontSize: 13,
          padding: 8,
          boxSizing: 'border-box',
          border: '1px solid #ccc',
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
        <div style={{ marginTop: 16, padding: 12, border: '1px solid #ccc', borderRadius: 8 }}>
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
                {' · '}
                <span style={{ textTransform: 'capitalize', fontWeight: 400, color: '#888' }}>{r.exam_type}</span>
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

// ── Forecast grid (Sprint12_FSRSAndUXOverhaul) ──────────────────────────────
//
// Extracted from ReviewStatsPanel's inline "Upcoming" markup so the same
// grid (header row + one ForecastRow per `rows` entry) can be reused by the
// stats page's "Scheduled reviews (forecast)" zone. Deliberately decoupled
// from any session state — only `rows` (label + values, one entry per
// FORECAST_COLUMNS column) is accepted.
function ForecastGrid({ rows }: { rows: { label: string; values: (number | null)[] }[] }) {
  return (
    <div style={{ overflowX: 'auto' }}>
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
        {rows.map(row => <ForecastRow key={row.label} label={row.label} values={row.values} />)}
      </div>
    </div>
  );
}

interface TodayRow { recalls: number; unique_cards_seen: number; first_cards_seen: number }

function ReviewStatsPanel({
  topic,
  essayId,
  sectionId,
  refreshToken,
  backlog,
  newRemaining,
}: {
  topic: string | null;
  essayId: string | null;
  sectionId: string | null;
  refreshToken: number;
  backlog: number;
  newRemaining: number;
}) {
  const [stats, setStats] = useState<Record<string, number> | null>(null);
  const [today, setToday] = useState<TodayRow | null>(null);

  useEffect(() => {
    (async () => {
      const qs = new URLSearchParams();
      if (topic) qs.set('topic', topic);
      if (essayId) qs.set('essay_id', essayId);
      if (sectionId) qs.set('section_id', sectionId);
      const suffix = qs.toString() ? `?${qs.toString()}` : '';
      const res = await apiFetch<Dataset<QueueStatRow>>(`/essaycards/flashcards/stats${suffix}`);
      if (isApiError(res)) {
        setStats(null);
      } else {
        setStats(Object.fromEntries(res.rows.map(r => [r.bucket, r.count])));
      }
      const todayRes = await apiFetch<Dataset<TodayRow>>(`/essaycards/review-stats/today${suffix}`);
      setToday(isApiError(todayRes) ? null : todayRes.rows[0] ?? null);
    })();
  }, [topic, essayId, sectionId, refreshToken]);

  // Recalls/Unique/First are backend-owned (GET /review-stats/today, UTC day);
  // Due/New are derived from the already-scoped due queue.
  const metrics: [string, string][] = [
    [today ? String(today.recalls) : '·', 'Recalls'],
    [today ? String(today.unique_cards_seen) : '·', 'Unique'],
    [today ? String(today.first_cards_seen) : '·', 'First'],
    [String(backlog), 'Due'],
    [String(newRemaining), 'New'],
  ];
  const allRow = FORECAST_COLUMNS.map(c => (stats ? stats[c.key] ?? 0 : null));

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
      <div data-testid="review-daily-metrics" style={{ display: 'flex', gap: 8 }}>
        {metrics.map(([value, label]) => (
          <div key={label} style={{ flex: 1, textAlign: 'center' }}>
            <div style={{ fontSize: 22, fontWeight: 500, lineHeight: 1.1, color: 'var(--md-sys-color-on-surface)' }}>
              {value}
            </div>
            <div style={{ ...statMetricLabelStyle, marginTop: 2 }}>{label}</div>
          </div>
        ))}
      </div>

      <div data-testid="review-interval-row">
        <ForecastGrid rows={[{ label: '', values: allRow }]} />
      </div>
    </div>
  );
}

// ── Review Session View ───────────────────────────────────────────────────────

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
  const topic = searchParams.get('topic');
  const essayId = searchParams.get('essay_id');
  const sectionId = searchParams.get('section_id');
  // Scope present -> FOCUS session (all open cards in scope). No scope ->
  // REVIEW session (open AND established). The backend infers this from the
  // params; the caption just reflects it.
  const scopeLabel = topic
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
    if (topic) qs.set('topic', topic);
    if (essayId) qs.set('essay_id', essayId);
    if (sectionId) qs.set('section_id', sectionId);
    return `/essaycards/flashcards/due${qs.toString() ? `?${qs.toString()}` : ''}`;
  }, [topic, essayId, sectionId]);

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

    const newIntervalSec = (Date.parse(res.next_due_at) - Date.parse(res.last_reviewed_at)) / 1000;
    setLastNewIntervalSec(newIntervalSec);
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

  const statsPanel = (
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
        fontSize: 12,
        fontWeight: 700,
        letterSpacing: 0.6,
        textTransform: 'uppercase',
        color: '#888',
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
          {reviewedCount === 0 ? 'Nothing due right now.' : 'Session complete — nothing left in the queue.'}
        </div>
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
                style={{ ...jumpBtnStyle, marginLeft: 20 }}
                onClick={() => navigate('/essaycards/explore/import')}
              >
                Import result →
              </button>
            ) : (
              <button
                style={{ ...jumpBtnStyle, marginLeft: 20 }}
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

// ── Ingest View ───────────────────────────────────────────────────────────────

// Self-contained fill-in prompt: copied to the clipboard so it can be pasted
// into an LLM (ChatGPT or similar) that has zero prior knowledge of this app.
// It restates the full payload contract from Sprint02_JsonIngestion/00_draft.md
// and 10_architecture.json §invariants — every rule here must stay in sync with
// the backend's actual manual validation in backend/routers/essays.py.
const STUB_PROMPT = `You are generating a JSON payload for an app called EssayCards. It will be submitted verbatim as the raw HTTP body of POST /api/essaycards/essays/ingest. Reply with ONLY the JSON object — no markdown code fences (no \`\`\`), no commentary before or after, nothing but the JSON.

Fill in the template below. Every value is an instruction describing what belongs there — replace each one with real content, and remove these instructions from your reply. This is a FULL PACKAGE: the main spine, every nugget it needs, every section, and every flashcard, all in one JSON object, so one submit creates the whole essay in one step.

{
  "title": "the essay's display title, e.g. \\"Why Rome Fell\\" — do NOT put a leading sequence number in here; use sort_index for ordering",
  "slug": "a url-safe stable id for the essay: letters, digits, underscore, hyphen only, no spaces, e.g. why_rome_fell — submitting this JSON again later with the same slug UPDATES this essay instead of creating a new one",
  "category": "the overview-page group this essay belongs under — one of \\"Art\\", \\"History\\", \\"Philosophy\\" (omit the key entirely if none applies)",
  "sort_index": "integer position of this essay within its category, ascending (e.g. 1, 2, 3) — this replaces writing a number into the title; omit for 0",
  "status": "\\"complete\\" for a finished essay (the default — omit the key), or \\"planned\\" if this is a stub whose body is just planning notes",
  "main_spine_markdown": "a short (roughly 100-250 word) overview in Markdown tying the whole essay's sections together into one narrative arc — read on its own, before any section. May reference a nugget from the \\"nuggets\\" list below via [[nugget:key]] the same way section body_markdown does. Omit the key, or use an empty string, if the essay doesn't need a spine overview.",
  "nuggets": [
    {
      "nugget_key": "a url-safe stable id for this ONE standalone concept: letters, digits, underscore, hyphen only, GLOBALLY unique across the whole app, not just this essay — e.g. cogito. Check \\"Existing nugget keys\\" below before inventing one, so you don't accidentally create a near-duplicate of a concept that already exists.",
      "title": "the nugget's short display title, e.g. \\"Cogito\\"",
      "body_markdown": "a self-contained explanation of this ONE concept in Markdown, written so it makes sense read on its own — independent of whichever essay/section links to it. This is what a reader sees when they click the concept anywhere it's referenced."
    }
  ],
  "sections": [
    {
      "heading": "this section's display heading, e.g. \\"The Economic Causes\\"",
      "anchor_slug": "a url-safe stable id for this section, unique within the essay, e.g. economic-causes — used for \\"jump to passage\\" links, so keep it short and don't rename it on a later update",
      "body_markdown": "the ACTUAL essay text for this section, written in Markdown, roughly 300-600 words ('about one page') — this is what the reader reads. Do not summarize; write the real prose. Flashcards are NOT marked inline in this text (that inline-fence convention is only used by this app's separate offline markdown-file ingestion path, not this JSON format) — flashcards go in the sibling 'cards' list below instead. Reference a nugget from the \\"nuggets\\" list above inline via [[nugget:key]] instead of re-explaining a substantial, independently-meaningful concept in place — see the Nuggets rule below. You may also embed images as Markdown image references here — see the Images rule below.",
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
- "category", "sort_index" and "status" are optional essay-level metadata for the overview page. Never encode a sequence number in "title" — put it in "sort_index". Omit "category" entirely if the topic given doesn't clearly fit one. Use "status": "planned" only for a stub essay whose body is just planning notes; a normal finished essay omits "status".
- The order of the "sections" array IS the reading order (there is no separate order field); same for the order you list "cards" within a section.
- This is an upsert, never a wholesale replace: if you're updating an existing essay, sections/cards you omit from the payload are left untouched, not deleted. The same is true of "nuggets": reusing an existing nugget_key here UPDATES that nugget's title/body_markdown in place, which affects every essay/section that already links to it — only reuse a key you actually intend to revise.
- Repeat the section object for every section of the essay — a real essay should have several sections, not just one.
- Nuggets. "nuggets" is optional — omit it, or use an empty list, if this essay doesn't need any standalone/reusable concepts. Every [[nugget:key]] you write anywhere in "main_spine_markdown" or any section's "body_markdown" MUST have a matching entry in "nuggets" in THIS SAME payload, unless that key already exists from an earlier import — an unresolved reference fails the entire import, nothing gets saved. Don't create a nugget for something discussed in only one place that isn't independently meaningful on its own — plain prose in body_markdown is fine for that; nuggets are specifically for concepts substantial and reusable enough to deserve their own standalone explanation.
- Images. To place an image, write a standard Markdown image reference ![short alt text](/api/essaycards/images/SLUG) on its own line (a blank line before and after) inside a body_markdown value, or inline inside a card "q" or "a". SLUG must be one of the slugs under "Available images" below. The ingest endpoint does NOT validate image references — an invented or misspelled slug silently renders as a broken image, so use only the slugs listed. Add an image only where it genuinely illustrates the adjacent prose, and keep the alt text short. If "Available images" is empty, do not write any image references.

Existing nugget keys (key — title), so you don't accidentally duplicate one that already exists elsewhere in the app:
- (none yet — before using this prompt, replace this line with one entry per existing nugget you want available for reuse, e.g. "cogito — Cogito". Leave empty if none should be reused.)

Available images (slug — what it depicts):
- (none yet — before using this prompt, replace this line with one entry per imported image, e.g. "denarius-debasement-chart — line chart of the denarius's silver content, 0-270 AD". Leave empty to use no images.)

Worked mini-example (2 sections, one nugget, realistic content, for the topic "Why Rome Fell" — do not reuse this content, it's here only to show the pattern):

{
  "title": "Why Rome Fell",
  "slug": "why_rome_fell",
  "category": "History",
  "sort_index": 1,
  "status": "complete",
  "main_spine_markdown": "Rome's fall was not one event but a slow compounding of pressures: a currency crisis that undercut trust and trade, met by frontier pressure the state could no longer afford to answer. Central to both is the [[nugget:fiscal-military-spiral]] that made each problem worsen the other.",
  "nuggets": [
    {
      "nugget_key": "fiscal-military-spiral",
      "title": "The Fiscal-Military Spiral",
      "body_markdown": "A self-reinforcing cycle: falling tax revenue forces debasement of the currency to pay the army, debasement drives inflation and further erodes real tax revenue, and the shrinking real budget cannot fund the frontier defense that rising external pressure demands — each turn of the cycle leaves the state weaker going into the next."
    }
  ],
  "sections": [
    {
      "heading": "The Economic Causes",
      "anchor_slug": "economic-causes",
      "body_markdown": "By the 3rd century, Rome's currency had been debased so many times that contemporaries spoke of a \\"debasement crisis\\" eroding trust in coinage across the empire.\\n\\n![Silver content of the denarius, 0-270 AD](/api/essaycards/images/denarius-debasement-chart)\\n\\nTax revenue fell as trade contracted, while the cost of defending an ever-longer frontier kept rising — the [[nugget:fiscal-military-spiral]] driving both at once.",
      "cards": [
        { "id": "economic-causes-1", "q": "What did contemporaries call the currency problem of the 3rd century?", "a": "The \\"debasement crisis\\" — repeated debasement of the currency, which drove inflation." },
        { "id": "economic-causes-2", "q": "Why did tax revenue decline even as military costs rose?", "a": "Trade contracted, shrinking the tax base, while frontier defense grew more expensive." }
      ]
    },
    {
      "heading": "Pressure on the Frontiers",
      "anchor_slug": "frontier-pressure",
      "body_markdown": "Migrating and invading groups pressed on the Rhine and Danube frontiers with increasing frequency from the late 4th century onward, straining a treasury already caught in the [[nugget:fiscal-military-spiral]]...",
      "cards": [
        { "id": "frontier-pressure-1", "q": "Which two rivers marked the frontiers under increasing pressure from the late 4th century?", "a": "The Rhine and the Danube." }
      ]
    }
  ]
}

Now write a complete essay — main spine, nuggets, sections, and flashcards — on the topic I give you, following every rule above exactly, and reply with only the JSON.`;

// Shown as the textarea's empty-state placeholder — same self-documenting
// style as STUB_PROMPT's template (values ARE the instructions). Shows TWO
// sections deliberately: a card's section is determined only by which
// section object's "cards" array it's nested inside (no separate linking
// field exists), and that's invisible with just one section to look at.
const PLACEHOLDER_JSON = `{
  "title": "title of the essay (no leading sequence number)",
  "slug": "url-safe id, e.g. my_essay (letters/digits/_/- only)",
  "category": "Art | History | Philosophy (optional)",
  "sort_index": 1,
  "status": "complete | planned (optional, default complete)",
  "main_spine_markdown": "optional short overview tying the sections together, in Markdown — may use [[nugget:key]]",
  "nuggets": [
    { "nugget_key": "url-safe id, globally unique across the app", "title": "short display title", "body_markdown": "self-contained explanation of this one concept" }
  ],
  "sections": [
    {
      "heading": "first section's heading",
      "anchor_slug": "url-safe id for this section, unique in the essay",
      "body_markdown": "this section's essay text, in Markdown — may reference [[nugget:key]] from the nuggets list above",
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
// a card belongs to whichever section it's nested inside above — there is no separate section-linking field
// "nuggets" is optional — every [[nugget:key]] used above must have a matching entry here (or already exist)`;

interface IngestSummary {
  essay_id: string;
  slug: string;
  nuggets_created: number;
  nuggets_updated: number;
  sections_created: number;
  sections_updated: number;
  cards_created: number;
  cards_updated: number;
}

// Sprint09_Nuggets — section spine revision drop-detection (internal_flow
// step 10): when a pasted payload has a focus_section_id, compares the
// stashed key set from ReaderView.handleExportSection (stored in
// sessionStorage, read once and cleared here) against the returned focus
// section's CURRENT nugget keys. A non-empty difference is surfaced as a
// non-blocking warning — submission is never blocked by this check, only a
// warning is shown (00_draft.md §8 "surfaces, not silently blocks").
function detectDroppedNuggetKeys(pastedText: string): string[] | null {
  let parsed: any;
  try {
    parsed = JSON.parse(pastedText);
  } catch {
    return null;
  }
  const focusSectionId = parsed?.focus_section_id;
  if (typeof focusSectionId !== 'string' || !Array.isArray(parsed?.sections)) return null;

  let stashed: string | null;
  try {
    stashed = sessionStorage.getItem(`essaycards:sectionExport:${focusSectionId}`);
    if (stashed !== null) sessionStorage.removeItem(`essaycards:sectionExport:${focusSectionId}`);
  } catch {
    return null;
  }
  if (!stashed) return null;

  let previouslyRequired: unknown;
  try {
    previouslyRequired = JSON.parse(stashed);
  } catch {
    return null;
  }
  if (!Array.isArray(previouslyRequired) || previouslyRequired.length === 0) return null;

  const focusSection = parsed.sections.find((s: any) => s?.section_id === focusSectionId);
  if (!focusSection || typeof focusSection.body_markdown !== 'string') return null;

  const currentKeys = extractNuggetKeysClient(focusSection.body_markdown);
  const dropped = (previouslyRequired as string[]).filter(k => !currentKeys.has(k));
  return dropped.length > 0 ? dropped : null;
}

function IngestView() {
  const navigate = useNavigate();
  const [text, setText] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [result, setResult] = useState<IngestSummary | null>(null);
  const [clipboardMsg, setClipboardMsg] = useState<string | null>(null);
  const [dropWarning, setDropWarning] = useState<string | null>(null);

  const checkNuggetDrop = (pastedText: string) => {
    const dropped = detectDroppedNuggetKeys(pastedText);
    setDropWarning(
      dropped
        ? `Warning: this section previously required nugget${dropped.length > 1 ? 's' : ''} ` +
          `${dropped.map(k => `[[nugget:${k}]]`).join(', ')}, which no longer appear${dropped.length === 1 ? 's' : ''} ` +
          'in the returned text. If this was intentional, ignore this — submission is not blocked.'
        : null,
    );
  };

  const handleCopyStub = async () => {
    const err = await writeClipboard(STUB_PROMPT);
    setClipboardMsg(
      err ??
        'Copied. Paste into ChatGPT (or similar) with your topic, then use "Paste from clipboard" below to bring its reply back in.',
    );
  };

  const handlePasteFromClipboard = async () => {
    const res = await readClipboard();
    if ('error' in res) {
      setClipboardMsg(res.error);
      return;
    }
    setText(res.text);
    setClipboardMsg(null);
    checkNuggetDrop(res.text);
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
        Paste one JSON payload with the whole essay: its main spine, any new
        nuggets it needs, its sections, and their flashcards — one submit
        creates or updates all of it together. Each flashcard lives inside
        its section's own "cards" list — that nesting is what ties a question
        to the passage it tests, there's no separate field pointing a card at
        a section. A section may reference a nugget defined in this same
        payload's "nuggets" list via [[nugget:key]] — nuggets are upserted
        first, so the reference always resolves. If the slug already exists,
        its sections and cards are upserted; nothing is deleted. No idea how
        to write that JSON by hand? Copy the fill-in prompt below, hand it to
        an LLM with your topic, and paste its reply back in.
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
        onPaste={e => {
          const pasted = e.clipboardData?.getData('text');
          if (pasted) checkNuggetDrop(pasted);
        }}
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

      {dropWarning && (
        <div style={{ fontSize: 12, color: '#b06a00', marginTop: 8 }}>{dropWarning}</div>
      )}

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
            Nuggets: +{result.nuggets_created} created, ~{result.nuggets_updated} updated
            <br />
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

// ── Explore Import View (Sprint06) ───────────────────────────────────────────
//
// Paste ChatGPT's JSON reply from a flashcard exploration. Two server round
// trips: first ?dry_run=true to get a preview (nothing written), then — only
// after the user confirms — the same body without the flag to apply it
// atomically. The pasted text is sent verbatim as the POST body (no client-side
// JSON.parse), same as IngestView / ImportExaminationsView. A rejected import
// returns a complete, copy-pasteable description in error.message.

const EXPLORE_RESULT_PLACEHOLDER_JSON = `{
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

function ExploreImportView() {
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
      <div style={{ color: '#888', fontSize: 13, marginBottom: 12 }}>
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
        <div style={{ fontSize: 12, color: '#888', marginBottom: 8 }}>{clipboardMsg}</div>
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
          border: '1px solid #ccc',
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
        <div style={{ marginTop: 16, padding: 12, borderRadius: 8, border: '1px solid #e0e0e0', fontSize: 13 }}>
          <div style={{ fontWeight: 600, marginBottom: 8 }}>This import will:</div>

          <div style={{ marginBottom: 10 }}>
            <div style={{ fontWeight: 600 }}>• Save a discussion</div>
            <div style={{ color: '#555' }}>
              Card <code>{preview.save_discussion.card_key}</code> — “{preview.save_discussion.exploration_question}”
            </div>
            <div style={{ color: '#888', marginTop: 2 }}>
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
                <div style={{ color: '#555' }}>
                  Question: <s>{u.old.question}</s> → <strong>{u.new.question}</strong>
                </div>
              )}
              {u.changed_fields.includes('answer') && (
                <div style={{ color: '#555' }}>
                  Answer: <s>{u.old.answer}</s> → <strong>{u.new.answer}</strong>
                </div>
              )}
              <div style={{ color: '#888', marginTop: 2 }}>
                Reason (kept in history): “{u.reason}”. The previous version is preserved.
              </div>
            </div>
          ))}

          {preview.create_card.map((c, i) => (
            <div key={`c${i}`} style={{ marginBottom: 10 }}>
              <div style={{ fontWeight: 600 }}>
                • Create a new card in section <code>{c.section_anchor_slug}</code>
              </div>
              <div style={{ color: '#555' }}>Q: {c.question}</div>
              <div style={{ color: '#555' }}>A: {c.answer}</div>
              <div style={{ color: '#888', marginTop: 2 }}>New card key <code>{c.card_key}</code>.</div>
            </div>
          ))}

          {preview.update_card.length === 0 && preview.create_card.length === 0 && (
            <div style={{ color: '#888' }}>No card changes — the discussion is saved as-is.</div>
          )}
        </div>
      )}

      {applied && (
        <div style={{ marginTop: 16, padding: 12, borderRadius: 8, border: '1px solid #e0e0e0', fontSize: 13 }}>
          <div style={{ fontWeight: 600, marginBottom: 8 }}>Import applied</div>
          <div style={{ color: '#555' }}>
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

const NUGGET_JSON_PLACEHOLDER = `{
  "nugget_key": "...",
  "title": "...",
  "body_markdown": "..."
}`;

function NuggetAuthoringImportView() {
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
          <div style={{ color: '#888', fontSize: 13, marginBottom: 12 }}>
            {pkg.nugget
              ? `Revising "${pkg.nugget.title}" (${pkg.nugget.nugget_key}).`
              : 'Drafting a brand-new nugget, in the context of this essay/section.'}
            {' '}Copy the prompt, discuss/draft with ChatGPT (or similar), then paste its JSON reply below.
          </div>
          <div style={{ display: 'flex', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
            <button style={btnStyle} onClick={handleCopyPrompt}>Copy prompt</button>
            <button style={btnStyle} onClick={handlePasteFromClipboard}>Paste from clipboard</button>
          </div>
          {clipboardMsg && <div style={{ fontSize: 12, color: '#888', marginBottom: 8 }}>{clipboardMsg}</div>}

          <textarea
            value={text}
            onChange={e => setText(e.target.value)}
            rows={12}
            style={{
              width: '100%', fontFamily: 'monospace', fontSize: 13, padding: 8,
              boxSizing: 'border-box', border: '1px solid #ccc', borderRadius: 6,
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
            <div style={{ marginTop: 16, padding: 12, borderRadius: 8, border: '1px solid #e0e0e0' }}>
              <div style={{ fontWeight: 600, marginBottom: 8 }}>
                {result.created ? 'Nugget created' : 'Nugget updated'}
              </div>
              <div style={{ fontSize: 13, color: '#555' }}>
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

// ── Generate flashcards from a nugget (Sprint09_Nuggets) ────────────────────
//
// Self-contained, same shape as NuggetAuthoringImportView above. Import
// issues one POST /flashcards/upsert per generated card, SEQUENTIALLY, each
// with nugget_id pre-set to the source nugget — no new bulk/atomic backend
// endpoint (10_architecture.json risks: not atomic across the batch). Reports
// per-card success/failure so the user can retry only the failed ones.

const GENERATE_FLASHCARDS_JSON_PLACEHOLDER = `{
  "cards": [
    { "level": 2, "q": "...", "a": "..." }
  ]
}`;

interface GeneratedCardResult {
  q: string;
  ok: boolean;
  message: string;
}

function GenerateFlashcardsImportView() {
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
          <div style={{ color: '#888', fontSize: 13, marginBottom: 12 }}>
            Generating cards for "{pkg.nugget.title}" ({pkg.nugget.nugget_key}) — {pkg.existing_flashcards.length} existing card(s).
          </div>
          <div style={{ display: 'flex', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
            <button style={btnStyle} onClick={handleCopyPrompt}>Copy prompt</button>
            <button style={btnStyle} onClick={handlePasteFromClipboard}>Paste from clipboard</button>
          </div>
          {clipboardMsg && <div style={{ fontSize: 12, color: '#888', marginBottom: 8 }}>{clipboardMsg}</div>}

          <textarea
            value={text}
            onChange={e => setText(e.target.value)}
            rows={12}
            style={{
              width: '100%', fontFamily: 'monospace', fontSize: 13, padding: 8,
              boxSizing: 'border-box', border: '1px solid #ccc', borderRadius: 6,
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

// ── Review stats (Sprint11_ReviewStats, reworked Sprint12_FSRSAndUXOverhaul) ─
//
// "How did I do" — three rolling-window (day/week/month) cards over
// GET /review-stats/summary. Same apiFetch<Dataset<T>>/isApiError/ErrorCard/
// Skeleton convention. The Sprint10 experiment dashboard that used to sit
// alongside this (GET /experiment/summary, the Classic-vs-FSRS comparison)
// is retired along with the dual-scheduler mechanism — see CLAUDE.md "FSRS
// scheduling".

const REVIEW_STATS_WINDOW_LABELS: Record<ReviewStatsSummaryRow['period'], string> = {
  day: 'Day',
  week: 'Week',
  month: 'Month',
};

function ReviewStatsCard({ row }: { row: ReviewStatsSummaryRow }) {
  const figure = (label: string, value: string) => (
    <div style={{ marginTop: 8 }}>
      <div style={{ fontSize: 13, color: 'var(--md-sys-color-on-surface-variant)' }}>{label}</div>
      <div style={{ fontSize: 20, fontVariantNumeric: 'tabular-nums' }}>{value}</div>
    </div>
  );
  return (
    <div
      style={{
        background: 'var(--md-sys-color-surface-variant)',
        borderRadius: 12,
        padding: 16,
        flex: '1 1 200px',
        minWidth: 180,
      }}
    >
      <h3 style={{ margin: '0 0 8px' }}>{REVIEW_STATS_WINDOW_LABELS[row.period]}</h3>
      {figure('Cards Seen', String(row.reviews))}
      {figure('Unique Cards Seen', String(row.unique_cards))}
      {figure('New Cards Seen', String(row.new_count))}
      {figure('Recall Rate', row.recall_rate == null ? 'No reviews yet' : `${Math.round(row.recall_rate * 100)}%`)}
      <table style={{ width: '100%', marginTop: 12, borderCollapse: 'collapse' }}>
        <tbody>
          <tr>
            <td style={{ padding: '2px 4px', fontSize: 13 }}>Again</td>
            <td style={{ padding: '2px 4px', fontSize: 13, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{row.again_count}</td>
          </tr>
          <tr>
            <td style={{ padding: '2px 4px', fontSize: 13 }}>Hard</td>
            <td style={{ padding: '2px 4px', fontSize: 13, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{row.hard_count}</td>
          </tr>
          <tr>
            <td style={{ padding: '2px 4px', fontSize: 13 }}>Good</td>
            <td style={{ padding: '2px 4px', fontSize: 13, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{row.good_count}</td>
          </tr>
          <tr>
            <td style={{ padding: '2px 4px', fontSize: 13 }}>Easy</td>
            <td style={{ padding: '2px 4px', fontSize: 13, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{row.easy_count}</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

const statsZoneHeadingStyle: React.CSSProperties = {
  margin: '28px 0 4px',
  fontSize: 15,
};

const statsZoneSubtextStyle: React.CSSProperties = {
  color: 'var(--md-sys-color-on-surface-variant)',
  fontSize: 12,
  margin: '0 0 12px',
};

// Levels 0-4, in that fixed order — the x-axis of the "Essay learning
// progress" histogram.
const LEARNING_LEVELS = [0, 1, 2, 3, 4];

// Study activity: one stacked column per UTC day (Repeat / Unique / First),
// total height = recalls, recall-rate percentage above each column. Local,
// CSS-only (platform-ui BarChart has no per-bar label slot — see
// Sprint13 10_architecture.json internal_flow step 11). Segment formulas:
// repeat = recalls - unique; unique = unique - first; first = first.
const ACTIVITY_COLORS = {
  repeat: 'var(--md-sys-color-outline)',
  unique: 'var(--md-sys-color-secondary, #6b7a8f)',
  first: 'var(--md-sys-color-primary)',
};

function DailyActivityChart({ rows }: { rows: ActivityDayRow[] }) {
  const maxRecalls = Math.max(1, ...rows.map(r => r.recalls));
  const barArea = 120;
  const seg = (n: number, color: string, label: string) =>
    n > 0 ? <div title={`${label}: ${n}`} style={{ height: (n / maxRecalls) * barArea, background: color }} /> : null;
  return (
    <div data-testid="daily-activity-chart">
      <div style={{ overflowX: 'auto' }}>
        <div style={{ display: 'flex', gap: 4, alignItems: 'flex-end', minWidth: rows.length * 30 }}>
          {rows.map(r => (
            <div
              key={r.date}
              data-testid="activity-column"
              style={{ width: 26, flexShrink: 0, display: 'flex', flexDirection: 'column', alignItems: 'center' }}
            >
              <div
                data-testid="activity-rate"
                style={{ fontSize: 9, height: 14, color: 'var(--md-sys-color-on-surface-variant)', whiteSpace: 'nowrap' }}
              >
                {r.recall_rate == null ? '—' : `${Math.round(r.recall_rate * 100)}%`}
              </div>
              <div style={{ width: '100%', height: barArea, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end' }}>
                {seg(r.recalls - r.unique_cards_seen, ACTIVITY_COLORS.repeat, 'Repeat')}
                {seg(r.unique_cards_seen - r.first_cards_seen, ACTIVITY_COLORS.unique, 'Unique')}
                {seg(r.first_cards_seen, ACTIVITY_COLORS.first, 'First')}
              </div>
              <div style={{ fontSize: 9, color: 'var(--md-sys-color-on-surface-variant)' }}>{r.date.slice(8)}</div>
            </div>
          ))}
        </div>
      </div>
      <div style={{ fontSize: 12, marginTop: 8, display: 'flex', gap: 12 }}>
        <span><span style={{ color: ACTIVITY_COLORS.repeat }}>■</span> Repeat</span>
        <span>·</span>
        <span><span style={{ color: ACTIVITY_COLORS.unique }}>■</span> Unique</span>
        <span>·</span>
        <span><span style={{ color: ACTIVITY_COLORS.first }}>■</span> First</span>
      </div>
    </div>
  );
}

function ReviewStatsView() {
  const navigate = useNavigate();
  const [summaryRows, setSummaryRows] = useState<ReviewStatsSummaryRow[]>([]);
  const [activityRows, setActivityRows] = useState<ActivityDayRow[] | null>(null);
  const [period, setPeriod] = useState<ReviewStatsSummaryRow['period']>('day');
  const [intervalsDataset, setIntervalsDataset] = useState<PlatformDataset | null>(null);
  const [forecastRow, setForecastRow] = useState<(number | null)[] | null>(null);
  const [essays, setEssays] = useState<EssayRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);

  useEffect(() => {
    (async () => {
      setLoading(true);
      const [summaryRes, activityRes, intervalsRes, forecastRes, essaysRes] = await Promise.all([
        apiFetch<Dataset<ReviewStatsSummaryRow>>('/essaycards/review-stats/summary'),
        apiFetch<Dataset<ActivityDayRow>>('/essaycards/review-stats/activity'),
        apiFetch<PlatformDataset>('/essaycards/review-stats/intervals'),
        apiFetch<Dataset<QueueStatRow>>('/essaycards/flashcards/stats'),
        apiFetch<Dataset<EssayRow>>('/essaycards/essays'),
      ]);
      setLoading(false);

      if (isApiError(summaryRes)) {
        setError(summaryRes);
        return;
      }
      setError(null);
      setSummaryRows(summaryRes.rows);
      setActivityRows(isApiError(activityRes) ? null : activityRes.rows);
      setIntervalsDataset(isApiError(intervalsRes) ? null : intervalsRes);
      if (!isApiError(forecastRes)) {
        const byBucket = Object.fromEntries(forecastRes.rows.map(r => [r.bucket, r.count]));
        setForecastRow(FORECAST_COLUMNS.map(c => byBucket[c.key] ?? 0));
      }
      if (!isApiError(essaysRes)) setEssays(essaysRes.rows);
    })();
  }, []);

  const levelHistogramDataset: PlatformDataset = {
    meta: { object_type: 'learning_level_bucket', label: 'Essay Learning Progress', total: LEARNING_LEVELS.length, page: 1, page_size: LEARNING_LEVELS.length, row_actions: [] },
    schema: [
      { key: 'level', label: 'Level', type: 'string', sortable: false, filterable: false },
      { key: 'count', label: 'Essays', type: 'number', sortable: false, filterable: false },
    ],
    rows: LEARNING_LEVELS.map(level => ({
      id: String(level),
      level: `${level}/4`,
      count: essays.filter(e => e.learning_level === level).length,
    })),
  };

  return (
    <div style={pageStyle}>
      <button style={jumpBtnStyle} onClick={() => navigate('/essaycards')}>← Back to all essays</button>
      <h2 style={{ marginTop: 16 }}>Stats</h2>

      {loading && <Skeleton />}
      {error && <ErrorCard error={error} />}

      {!loading && !error && (
        <>
          <h3 style={statsZoneHeadingStyle}>Study activity</h3>
          <p style={statsZoneSubtextStyle}>
            Recalls per UTC day, trailing 30 days; recall rate shown above each day.
          </p>
          {activityRows
            ? <DailyActivityChart rows={activityRows} />
            : <div style={{ color: '#888', fontSize: 13 }}>Activity data unavailable.</div>}

          <h3 style={statsZoneHeadingStyle}>Scheduled reviews (forecast)</h3>
          <p style={statsZoneSubtextStyle}>
            A schedule FORECAST, not an observed fact — when currently-scheduled cards will next come due,
            predicted by FSRS. Distinct from "Observed recall" below.
          </p>
          <div
            style={{
              background: 'var(--md-sys-color-surface-variant)',
              borderRadius: 'var(--radius-card, 12px)',
              padding: 12,
            }}
          >
            <ForecastGrid rows={[{ label: 'All', values: forecastRow ?? FORECAST_COLUMNS.map(() => null) }]} />
          </div>

          <h3 style={statsZoneHeadingStyle}>Observed recall</h3>
          <p style={statsZoneSubtextStyle}>
            What actually happened over the trailing day/week/month — OBSERVED, not predicted. Sample size is
            Cards Seen.
          </p>
          <div role="group" aria-label="Observed recall period" style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
            {(['day', 'week', 'month'] as const).map(p => (
              <button
                key={p}
                type="button"
                aria-pressed={period === p}
                onClick={() => setPeriod(p)}
                style={{
                  padding: '6px 14px',
                  borderRadius: 16,
                  cursor: 'pointer',
                  border: '1px solid var(--md-sys-color-outline)',
                  background: period === p ? 'var(--md-sys-color-primary)' : 'transparent',
                  color: period === p ? 'var(--md-sys-color-on-primary, #fff)' : 'var(--md-sys-color-on-surface)',
                }}
              >
                {REVIEW_STATS_WINDOW_LABELS[p]}
              </button>
            ))}
          </div>
          {summaryRows.find(r => r.period === period) && (
            <ReviewStatsCard row={summaryRows.find(r => r.period === period)!} />
          )}

          <h3 style={statsZoneHeadingStyle}>Scheduled intervals</h3>
          <p style={statsZoneSubtextStyle}>How mature the deck is — current review_interval distribution across every scheduled card.</p>
          {intervalsDataset
            ? <BarChart dataset={intervalsDataset} mapping={{ x: 'label', y: 'count', aggregation: 'sum' }} />
            : <div style={{ color: '#888', fontSize: 13 }}>Interval data unavailable.</div>}

          <h3 style={statsZoneHeadingStyle}>Essay learning progress</h3>
          <p style={statsZoneSubtextStyle}>Number of essays at each learning level, 0-4.</p>
          <BarChart dataset={levelHistogramDataset} mapping={{ x: 'level', y: 'count', aggregation: 'sum' }} />
        </>
      )}
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
        <Route path="/essays/:id/questions" element={<QuestionOverviewView />} />
        <Route path="/questions/import" element={<QuestionImportView />} />
        <Route path="/review" element={<ReviewSessionView />} />
        <Route path="/ingest" element={<IngestView />} />
        <Route path="/examinations/import" element={<ImportExaminationsView />} />
        <Route path="/explore/import" element={<ExploreImportView />} />
        <Route path="/images" element={<ImagesView />} />
        <Route path="/nuggets/authoring" element={<NuggetAuthoringImportView />} />
        <Route path="/nuggets/:id/generate-flashcards" element={<GenerateFlashcardsImportView />} />
        <Route path="/stats" element={<ReviewStatsView />} />
      </Routes>
    </>
  );
}
