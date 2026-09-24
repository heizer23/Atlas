/**
 * StoryReader ShellEntry — Sprint 01
 *
 * Views:
 *   /storyreader                          → StoryListView
 *   /storyreader/stories/:id              → ReaderView       (?version=, ?highlight=)
 *   /storyreader/stories/:id/feedback     → FeedbackListView  (?version=)
 *
 * Selection/reaction/toggle decision tree implements
 * 10_architecture.json §internal_flow step 10 exactly; the Feedback-list
 * jump implements step 11.
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Routes, Route, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { apiFetch, isApiError } from '@platform-ui/api/client';
import ErrorCard from '@platform-ui/components/ErrorCard';
import Skeleton from '@platform-ui/components/Skeleton';
import type { Row, ApiError } from '@platform-ui/api/types';

// ── Types ─────────────────────────────────────────────────────────────────────

type Reaction = 'positive' | 'negative' | 'neutral' | 'unclear';

const REACTIONS: { key: Reaction; icon: string; label: string }[] = [
  { key: 'positive', icon: '👍', label: 'Positive' },
  { key: 'negative', icon: '👎', label: 'Negative' },
  { key: 'neutral',  icon: '😐', label: 'Neutral' },
  { key: 'unclear',  icon: '❓', label: 'Unclear' },
];
const REACTION_ICON: Record<Reaction, string> = Object.fromEntries(REACTIONS.map(r => [r.key, r.icon])) as Record<Reaction, string>;

interface StoryRow extends Row {
  id: string;
  slug: string;
  title: string;
  latest_version: number;
  marked_passage_count: number;
  created_at: string;
  updated_at: string;
}

interface StoryDetailRow extends Row {
  id: string;
  slug: string;
  title: string;
  latest_version: number;
  versions: number[];
}

interface ParagraphPayload {
  paragraph_index: number;
  text: string;
}

interface VersionContentRow extends Row {
  story_id: string;
  version: number;
  title: string;
  paragraphs: ParagraphPayload[];
  last_read_paragraph_index: number | null;
}

interface AnnotationRow extends Row {
  story_id: string;
  version: number;
  paragraph_index: number;
  char_start: number;
  char_end: number;
  selected_text: string;
  context_before: string;
  context_after: string;
  reaction: Reaction;
  created_at: string;
  updated_at: string;
}

interface Dataset<T> {
  meta: { object_type: string; total: number };
  rows: T[];
}

const CONTEXT_WINDOW = 200;
/** Reading-line offset shared by the position-save scan and the resume
 * restore below: a paragraph counts as "current" once its top is at or
 * above this many pixels from the viewport top, not literally 0 — so
 * restoring it must land it at this same offset, not the very top, or the
 * resumed view ends up a couple of lines further down than you left it. */
const READING_LINE_OFFSET = 96;

// ── Small shared pieces ────────────────────────────────────────────────────────

const btnStyle: React.CSSProperties = {
  padding:      '6px 12px',
  borderRadius: 8,
  border:       '1px solid #ccc',
  background:   '#fff',
  cursor:       'pointer',
  fontSize:     14,
};

function ReactionIcon({ reaction }: { reaction: Reaction }) {
  return <span aria-label={reaction} title={reaction}>{REACTION_ICON[reaction]}</span>;
}

function VersionSwitcher({
  versions,
  current,
  onChange,
}: {
  versions: number[];
  current: number;
  onChange: (v: number) => void;
}) {
  if (versions.length <= 1) return null;
  return (
    <select
      value={current}
      onChange={e => onChange(Number(e.target.value))}
      style={{ padding: '4px 8px', borderRadius: 6, border: '1px solid #ccc', fontSize: 13 }}
    >
      {versions.map(v => (
        <option key={v} value={v}>v{v}{v === Math.max(...versions) ? ' (latest)' : ''}</option>
      ))}
    </select>
  );
}

/** Resolves the effective version number for a story: the ?version= query
 * param if present, else the story's latest_version. Used by both the
 * Reader (which also needs paragraph content) and the Feedback list (which
 * only needs annotations, so never fetches paragraph content).
 */
async function fetchStoryDetail(storyId: string): Promise<StoryDetailRow | ApiError> {
  const res = await apiFetch<Dataset<StoryDetailRow>>(`/storyreader/stories/${storyId}`);
  if (isApiError(res)) return res;
  return res.rows[0];
}

/** Fire-and-forget: records the reading position for one (story, version)
 * and, server-side, marks the story as most recently active. */
function savePosition(storyId: string, version: number, paragraphIndex: number) {
  apiFetch(`/storyreader/stories/${storyId}/versions/${version}/position`, {
    method: 'PUT',
    body: JSON.stringify({ paragraph_index: paragraphIndex }),
  });
}

// ── Story List View ────────────────────────────────────────────────────────────

function StoryListView() {
  const navigate = useNavigate();
  const [stories, setStories] = useState<StoryRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      setLoading(true);
      const res = await apiFetch<Dataset<StoryRow>>('/storyreader/stories');
      setLoading(false);
      if (isApiError(res)) { setError(res.error.message); return; }
      setStories(res.rows);
    })();
  }, []);

  return (
    <div style={{ padding: 16, maxWidth: 640, margin: '0 auto' }}>
      <h2 style={{ margin: '0 0 12px' }}>Stories</h2>
      {loading && <Skeleton />}
      {error && <ErrorCard message={error} />}
      {!loading && !error && stories.length === 0 && (
        <div style={{ color: '#888', fontSize: 14 }}>
          No stories yet — publish one with the ingestion CLI.
        </div>
      )}
      {!loading && !error && stories.map(s => (
        <div
          key={s.id}
          onClick={() => navigate(`/storyreader/stories/${s.id}`)}
          style={{
            padding: 14, borderRadius: 10, border: '1px solid #e0e0e0',
            marginBottom: 10, background: '#fff', cursor: 'pointer',
          }}
        >
          <div style={{ fontWeight: 600, fontSize: 16 }}>{s.title}</div>
          <div style={{ fontSize: 13, color: '#777', marginTop: 4 }}>
            v{s.latest_version} · {s.marked_passage_count} marked passage{s.marked_passage_count === 1 ? '' : 's'}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Reader View ─────────────────────────────────────────────────────────────────

interface PopoverState {
  paragraphIndex: number;
  charStart:      number;
  charEnd:        number;
  /** Tap-cycle depth this span was produced at: 1 = word, 2 = sentence, 3 = paragraph. */
  level:          1 | 2 | 3;
  selectedText:   string;
  contextBefore:  string;
  contextAfter:   string;
  existingId:     string | null;
  existingReaction: Reaction | null;
  x: number;
  /** Bottom edge of the span's bounding rect (viewport coords) — the reaction bar renders below this. */
  y: number;
}

function getOffsetWithinParagraph(paragraphEl: Node, node: Node, offset: number): number {
  let charCount = 0;
  const walker = document.createTreeWalker(paragraphEl, NodeFilter.SHOW_TEXT);
  let current: Node | null;
  while ((current = walker.nextNode())) {
    if (current === node) return charCount + offset;
    charCount += current.textContent?.length ?? 0;
  }
  return charCount;
}

/** Scrolls the nearest scrollable ancestor of `el` so `el`'s top edge lands
 * `offsetFromTop` pixels below that ancestor's own top edge — the mirror
 * image of the position-save scan's "top <= offset" rule (see
 * READING_LINE_OFFSET). Falls back to `window.scrollBy` if no scrollable
 * ancestor is found (matches Atlas Shell's actual layout — its content area
 * scrolls, not the page — without hardcoding that shell-internal class). */
function scrollElementToOffset(el: HTMLElement, offsetFromTop: number) {
  let node = el.parentElement;
  while (node) {
    const style = window.getComputedStyle(node);
    if ((style.overflowY === 'auto' || style.overflowY === 'scroll') && node.scrollHeight > node.clientHeight) {
      const delta = el.getBoundingClientRect().top - node.getBoundingClientRect().top - offsetFromTop;
      node.scrollTop += delta;
      return;
    }
    node = node.parentElement;
  }
  window.scrollBy(0, el.getBoundingClientRect().top - offsetFromTop);
}

function closestParagraphEl(node: Node | null): HTMLElement | null {
  let el: Node | null = node;
  while (el) {
    if (el instanceof HTMLElement && el.dataset.paragraphIndex !== undefined) return el;
    el = el.parentNode;
  }
  return null;
}

/** Inverse of getOffsetWithinParagraph: builds a DOM Range spanning [start, end)
 * plain-text characters within paragraphEl, by walking the same text nodes. */
function rangeForCharSpan(paragraphEl: Node, start: number, end: number): Range | null {
  const walker = document.createTreeWalker(paragraphEl, NodeFilter.SHOW_TEXT);
  let charCount = 0;
  let startNode: Node | null = null, startOffset = 0;
  let endNode:   Node | null = null, endOffset   = 0;
  let current: Node | null;
  while ((current = walker.nextNode())) {
    const len = current.textContent?.length ?? 0;
    if (startNode === null && charCount + len >= start) {
      startNode = current;
      startOffset = start - charCount;
    }
    if (charCount + len >= end) {
      endNode = current;
      endOffset = end - charCount;
      break;
    }
    charCount += len;
  }
  if (!startNode || !endNode) return null;
  const range = document.createRange();
  range.setStart(startNode, startOffset);
  range.setEnd(endNode, endOffset);
  return range;
}

/** Resolves a viewport point to a DOM (node, offset) text position. Tries the
 * standard `caretPositionFromPoint` (Firefox, modern Chrome) first, falling
 * back to the WebKit-only `caretRangeFromPoint` (Safari) — between the two,
 * every mobile browser this app targets is covered. */
function caretOffsetFromPoint(x: number, y: number): { node: Node; offset: number } | null {
  const doc = document as Document & {
    caretPositionFromPoint?: (x: number, y: number) => { offsetNode: Node; offset: number } | null;
    caretRangeFromPoint?: (x: number, y: number) => Range | null;
  };
  if (doc.caretPositionFromPoint) {
    const pos = doc.caretPositionFromPoint(x, y);
    if (pos) return { node: pos.offsetNode, offset: pos.offset };
  }
  if (doc.caretRangeFromPoint) {
    const range = doc.caretRangeFromPoint(x, y);
    if (range) return { node: range.startContainer, offset: range.startOffset };
  }
  return null;
}

const WORD_RE = /[A-Za-z0-9''-]+/g;

/** Finds the word span containing `offset`, or the nearest word at-or-after
 * it, or the last word before it, in that order. English-only, best-effort —
 * matches the app's Out of Scope for other scripts/punctuation. */
function findWordRange(text: string, offset: number): { start: number; end: number } {
  WORD_RE.lastIndex = 0;
  let m: RegExpExecArray | null;
  let firstAfter: { start: number; end: number } | null = null;
  let last: { start: number; end: number } | null = null;
  while ((m = WORD_RE.exec(text))) {
    const start = m.index, end = start + m[0].length;
    if (offset >= start && offset < end) return { start, end };
    if (firstAfter === null && start >= offset) firstAfter = { start, end };
    last = { start, end };
  }
  return firstAfter ?? last ?? { start: 0, end: text.length };
}

const SENTENCE_END_RE = /[.!?]+(?=\s|$)/g;

/** Finds the sentence span containing `offset` (same containing/nearest rule
 * as findWordRange), splitting on runs of `.!?` followed by whitespace or
 * end-of-text, trimmed of surrounding whitespace. */
function findSentenceRange(text: string, offset: number): { start: number; end: number } {
  const boundaries: number[] = [0];
  let m: RegExpExecArray | null;
  SENTENCE_END_RE.lastIndex = 0;
  while ((m = SENTENCE_END_RE.exec(text))) boundaries.push(m.index + m[0].length);
  if (boundaries[boundaries.length - 1] !== text.length) boundaries.push(text.length);

  let firstAfter: { start: number; end: number } | null = null;
  let last: { start: number; end: number } | null = null;
  for (let i = 0; i < boundaries.length - 1; i++) {
    const raw = text.slice(boundaries[i], boundaries[i + 1]);
    const start = boundaries[i] + (raw.length - raw.trimStart().length);
    const end   = boundaries[i + 1] - (raw.length - raw.trimEnd().length);
    if (end <= start) continue;
    const range = { start, end };
    if (offset >= start && offset < end) return range;
    if (firstAfter === null && start >= offset) firstAfter = range;
    last = range;
  }
  return firstAfter ?? last ?? { start: 0, end: text.length };
}

function sameCoverSet(a: string[], b: string[]): boolean {
  if (a.length !== b.length) return false;
  return [...a].sort().join(',') === [...b].sort().join(',');
}

const PENDING_KEY = '__pending__';

function renderParagraph(
  text: string,
  paragraphIndex: number,
  annotationsForParagraph: AnnotationRow[],
  highlightId: string | null,
  pendingSpan: { charStart: number; charEnd: number } | null,
) {
  const n = text.length;
  if (annotationsForParagraph.length === 0 && !pendingSpan) {
    return (
      <p key={paragraphIndex} data-paragraph-index={paragraphIndex} className="sr-paragraph" style={paragraphStyle}>
        {text}
      </p>
    );
  }

  const annById: Record<string, AnnotationRow> = {};
  const covering: string[][] = Array.from({ length: n }, () => [] as string[]);
  for (const a of annotationsForParagraph) {
    annById[a.id] = a;
    const end = Math.min(a.char_end, n);
    for (let i = a.char_start; i < end; i++) covering[i].push(a.id);
  }
  if (pendingSpan) {
    const end = Math.min(pendingSpan.charEnd, n);
    for (let i = pendingSpan.charStart; i < end; i++) covering[i].push(PENDING_KEY);
  }

  const segments: { start: number; end: number; keys: string[] }[] = [];
  let i = 0;
  while (i < n) {
    const keys = covering[i];
    let j = i + 1;
    while (j < n && sameCoverSet(covering[j], keys)) j++;
    segments.push({ start: i, end: j, keys });
    i = j;
  }

  return (
    <p key={paragraphIndex} data-paragraph-index={paragraphIndex} className="sr-paragraph" style={paragraphStyle}>
      {segments.map((seg, idx) => {
        const chunk = text.slice(seg.start, seg.end);
        const isPending = seg.keys.includes(PENDING_KEY);
        const savedAnns = seg.keys.filter(k => k !== PENDING_KEY).map(id => annById[id]);
        if (savedAnns.length === 0 && !isPending) {
          return <React.Fragment key={idx}>{chunk}</React.Fragment>;
        }
        const isJumpTarget = highlightId !== null && savedAnns.some(a => a.id === highlightId);
        return (
          <mark
            key={idx}
            title={savedAnns.length > 0 ? savedAnns.map(a => a.reaction).join(', ') : 'selected'}
            style={{
              ...(savedAnns.length > 0 ? highlightStyle : {}),
              ...(isPending && savedAnns.length === 0 ? pendingOnlyStyle : {}),
              ...(isPending ? pendingOutlineStyle : {}),
              ...(isJumpTarget ? jumpHighlightStyle : {}),
            }}
          >
            {chunk}
            {savedAnns.length > 0 && (
              <span style={{ fontSize: 12, marginLeft: 2 }}>{REACTION_ICON[savedAnns[0].reaction]}</span>
            )}
          </mark>
        );
      })}
    </p>
  );
}

const paragraphStyle: React.CSSProperties = { fontSize: 17, lineHeight: 1.7, marginBottom: 18 };
const highlightStyle: React.CSSProperties = {
  background: '#fff3c4',
  color: 'inherit',
  padding: '0 1px',
  borderRadius: 3,
};
const jumpHighlightStyle: React.CSSProperties = {
  background: '#ffd76a',
  boxShadow: '0 0 0 2px #f5a623',
};
/** Live tap-in-progress span with no saved reaction underneath it yet. */
const pendingOnlyStyle: React.CSSProperties = {
  background: '#e3ebf5',
  color: 'inherit',
  padding: '0 1px',
  borderRadius: 3,
};
/** Layered on top of either style above while a tap-cycle selection is active,
 * saved or not — a quiet outline showing exactly what's currently selected. */
const pendingOutlineStyle: React.CSSProperties = {
  boxShadow: '0 0 0 2px #6b93c7',
};

function ReactionPopover({
  popover,
  onReact,
}: {
  popover: PopoverState;
  onReact: (reaction: Reaction) => void;
}) {
  return (
    <div
      style={{
        position: 'fixed',
        left: Math.max(8, Math.min(popover.x - 90, window.innerWidth - 188)),
        top: Math.max(8, Math.min(popover.y + 8, window.innerHeight - 60)),
        background: '#222',
        borderRadius: 10,
        padding: 8,
        display: 'flex',
        gap: 6,
        zIndex: 1000,
        boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
      }}
    >
      {REACTIONS.map(r => (
        <button
          key={r.key}
          onClick={() => onReact(r.key)}
          title={r.label}
          style={{
            fontSize: 20,
            padding: '4px 8px',
            borderRadius: 8,
            border: popover.existingReaction === r.key ? '2px solid #fff' : '1px solid transparent',
            background: popover.existingReaction === r.key ? '#444' : 'transparent',
            cursor: 'pointer',
          }}
        >
          {r.icon}
        </button>
      ))}
    </div>
  );
}

function ReaderView() {
  const { id } = useParams<{ id: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  const [detail, setDetail]         = useState<StoryDetailRow | null>(null);
  const [content, setContent]       = useState<VersionContentRow | null>(null);
  const [annotations, setAnnotations] = useState<AnnotationRow[]>([]);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState<string | null>(null);
  const [popover, setPopover]       = useState<PopoverState | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const versionParam = searchParams.get('version');
  const highlightId  = searchParams.get('highlight');

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);

    const detailRes = await fetchStoryDetail(id);
    if (isApiError(detailRes)) { setLoading(false); setError(detailRes.error.message); return; }
    setDetail(detailRes);

    const versionSegment = versionParam ?? 'latest';
    const contentRes = await apiFetch<Dataset<VersionContentRow>>(`/storyreader/stories/${id}/versions/${versionSegment}`);
    if (isApiError(contentRes)) { setLoading(false); setError(contentRes.error.message); return; }
    const contentRow = contentRes.rows[0];
    setContent(contentRow);

    const annRes = await apiFetch<Dataset<AnnotationRow>>(`/storyreader/stories/${id}/versions/${contentRow.version}/annotations`);
    setLoading(false);
    if (isApiError(annRes)) { setError(annRes.error.message); return; }
    setAnnotations(annRes.rows);
  }, [id, versionParam]);

  useEffect(() => { load(); }, [load]);

  // Feedback-list jump: scroll the highlighted passage into view once loaded.
  useEffect(() => {
    if (!highlightId || !content) return;
    const t = setTimeout(() => {
      const target = containerRef.current?.querySelector('mark[title]');
      const paragraphs = containerRef.current?.querySelectorAll('[data-paragraph-index]');
      const ann = annotations.find(a => a.id === highlightId);
      if (ann && paragraphs) {
        const p = paragraphs[ann.paragraph_index] as HTMLElement | undefined;
        p?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      } else {
        target?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }, 50);
    return () => clearTimeout(t);
  }, [highlightId, content, annotations]);

  // Resume: jump instantly to the remembered position for this version, but
  // only when there's no explicit feedback-list jump target — that always
  // wins. Instant (not smooth) because this is a resume, not an in-app nav.
  //
  // On a true cold start, the shell's web fonts (Google Fonts, loaded from
  // index.html) can still be loading when this first fires; once they swap
  // in a moment later every paragraph's height shifts, which drags the
  // scroll position back toward the top right after we set it. Re-applying
  // once more after `document.fonts.ready` (falling back to a fixed delay
  // if the Font Loading API isn't available) corrects for that.
  useEffect(() => {
    // `loading` is in the guard AND the dep array on purpose: `load()` calls
    // setContent() before setLoading(false), so on a real (non-instant)
    // network there is an intermediate render where `content` is already
    // set but the ref-bearing JSX below (gated on `!loading`) hasn't mounted
    // yet — containerRef.current would be null. Depending only on `content`
    // means this effect fires once during that unmounted moment and never
    // gets a reason to fire again once loading finishes, since `content`
    // itself doesn't change a second time. Depending on `loading` too makes
    // it re-run exactly when the ref actually becomes available.
    if (loading || highlightId || !content || content.last_read_paragraph_index == null) return;
    const target = content.last_read_paragraph_index;
    const jump = () => {
      const paragraphs = containerRef.current?.querySelectorAll('[data-paragraph-index]');
      const p = paragraphs?.[target] as HTMLElement | undefined;
      if (p) scrollElementToOffset(p, READING_LINE_OFFSET);
    };
    const t = setTimeout(jump, 50);
    let cancelled = false;
    const fontsReady = (document as Document & { fonts?: { ready: Promise<unknown> } }).fonts?.ready
      ?? new Promise(resolve => setTimeout(resolve, 400));
    fontsReady.then(() => { if (!cancelled) jump(); });
    return () => { cancelled = true; clearTimeout(t); };
  }, [loading, highlightId, content]);

  // "Mount touch": records this story as most recently active even on a
  // short visit, not only after the debounced scroll-save below fires.
  useEffect(() => {
    if (!content) return;
    savePosition(content.story_id, content.version, content.last_read_paragraph_index ?? 0);
  }, [content]);

  // Any scroll clears the active tap-cycle selection (it was anchored at tap
  // time and would otherwise drift out of alignment with the text), and
  // debounces a position save keyed on whichever paragraph now sits at the
  // top of the viewport. A `scroll` event does not bubble, so listening on
  // `document` in the CAPTURE phase (not bubble) is what actually catches
  // it regardless of which nested element scrolled — Atlas Shell scrolls
  // its own inner content area, not the page itself, and relying on a
  // specific ancestor here would just re-couple this app to shell internals.
  useEffect(() => {
    if (!content) return;
    let debounce: number | undefined;
    const onScroll = () => {
      setPopover(p => (p ? null : p));
      window.clearTimeout(debounce);
      debounce = window.setTimeout(() => {
        const paragraphs = containerRef.current?.querySelectorAll<HTMLElement>('[data-paragraph-index]');
        if (!paragraphs || paragraphs.length === 0) return;
        let current = 0;
        for (const el of Array.from(paragraphs)) {
          if (el.getBoundingClientRect().top <= READING_LINE_OFFSET) current = Number(el.dataset.paragraphIndex);
          else break;
        }
        savePosition(content.story_id, content.version, current);
      }, 600);
    };
    document.addEventListener('scroll', onScroll, { capture: true, passive: true });
    return () => { document.removeEventListener('scroll', onScroll, { capture: true }); window.clearTimeout(debounce); };
  }, [content]);

  // Tap-cycle: 1st tap on a spot selects its word, a 2nd tap inside that
  // selection grows it to the sentence, a 3rd to the whole paragraph, a 4th
  // clears it. A tap outside the current selection (or with nothing active)
  // starts a fresh word-level cycle at the new spot.
  const handleParagraphTap = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!content) return;
    const resolved = caretOffsetFromPoint(e.clientX, e.clientY);
    const paragraphEl = resolved ? closestParagraphEl(resolved.node) : null;
    if (!resolved || !paragraphEl) { setPopover(null); return; }

    const paragraphIndex = Number(paragraphEl.dataset.paragraphIndex);
    const paragraphText  = content.paragraphs[paragraphIndex]?.text ?? '';
    const charOffset = getOffsetWithinParagraph(paragraphEl, resolved.node, resolved.offset);

    const withinCurrent =
      !!popover &&
      popover.paragraphIndex === paragraphIndex &&
      charOffset >= popover.charStart &&
      charOffset < popover.charEnd;

    if (withinCurrent && popover!.level >= 3) { setPopover(null); return; }
    const level: 1 | 2 | 3 = withinCurrent ? ((popover!.level + 1) as 2 | 3) : 1;

    let charStart: number, charEnd: number;
    if (level === 1)      ({ start: charStart, end: charEnd } = findWordRange(paragraphText, charOffset));
    else if (level === 2) ({ start: charStart, end: charEnd } = findSentenceRange(paragraphText, charOffset));
    else                  { charStart = 0; charEnd = paragraphText.length; }
    if (charEnd <= charStart) { setPopover(null); return; }

    let contextBefore = paragraphText.slice(Math.max(0, charStart - CONTEXT_WINDOW), charStart);
    if (charStart === 0 && paragraphIndex > 0) {
      const prevText = content.paragraphs[paragraphIndex - 1]?.text ?? '';
      contextBefore = prevText.slice(Math.max(0, prevText.length - CONTEXT_WINDOW));
    }
    let contextAfter = paragraphText.slice(charEnd, charEnd + CONTEXT_WINDOW);
    if (charEnd === paragraphText.length && paragraphIndex < content.paragraphs.length - 1) {
      const nextText = content.paragraphs[paragraphIndex + 1]?.text ?? '';
      contextAfter = nextText.slice(0, CONTEXT_WINDOW);
    }

    const existing = annotations.find(
      a => a.paragraph_index === paragraphIndex && a.char_start === charStart && a.char_end === charEnd,
    );

    const range = rangeForCharSpan(paragraphEl, charStart, charEnd);
    if (!range) { setPopover(null); return; }
    const rect = range.getBoundingClientRect();
    setPopover({
      paragraphIndex, charStart, charEnd, level,
      selectedText: paragraphText.slice(charStart, charEnd),
      contextBefore, contextAfter,
      existingId: existing?.id ?? null,
      existingReaction: existing?.reaction ?? null,
      x: rect.left + rect.width / 2,
      y: rect.bottom,
    });
  };

  const handleReact = async (reaction: Reaction) => {
    if (!popover || !content || !id) return;

    if (popover.existingId && popover.existingReaction === reaction) {
      await apiFetch(`/storyreader/annotations/${popover.existingId}`, { method: 'DELETE' });
    } else {
      await apiFetch('/storyreader/annotations', {
        method: 'POST',
        body: JSON.stringify({
          story_id: id,
          version: content.version,
          paragraph_index: popover.paragraphIndex,
          char_start: popover.charStart,
          char_end: popover.charEnd,
          selected_text: popover.selectedText,
          context_before: popover.contextBefore,
          context_after: popover.contextAfter,
          reaction,
        }),
      });
    }
    setPopover(null);

    const annRes = await apiFetch<Dataset<AnnotationRow>>(`/storyreader/stories/${id}/versions/${content.version}/annotations`);
    if (!isApiError(annRes)) setAnnotations(annRes.rows);
  };

  const handleVersionChange = (v: number) => {
    setPopover(null);
    const next = new URLSearchParams();
    next.set('version', String(v));
    setSearchParams(next);
  };

  if (loading) return <div style={{ padding: 16 }}><Skeleton /></div>;
  if (error)   return <div style={{ padding: 16 }}><ErrorCard message={error} /></div>;
  if (!content || !detail) return null;

  const annotationsByParagraph: Record<number, AnnotationRow[]> = {};
  for (const a of annotations) {
    (annotationsByParagraph[a.paragraph_index] ??= []).push(a);
  }

  return (
    <div style={{ padding: '16px 20px', maxWidth: 680, margin: '0 auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10, gap: 8, flexWrap: 'wrap' }}>
        <button onClick={() => navigate('/storyreader')} style={btnStyle}>← Stories</button>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <VersionSwitcher versions={detail.versions} current={content.version} onChange={handleVersionChange} />
          <button onClick={() => navigate(`/storyreader/stories/${id}/feedback?version=${content.version}`)} style={btnStyle}>
            Feedback
          </button>
        </div>
      </div>

      <h2 style={{ margin: '0 0 16px' }}>{content.title}</h2>

      <div
        ref={containerRef}
        onClick={handleParagraphTap}
        style={{
          userSelect: 'none',
          WebkitUserSelect: 'none',
          WebkitTouchCallout: 'none',
          touchAction: 'manipulation',
        }}
      >
        {content.paragraphs.length === 0 && (
          <div style={{ color: '#888' }}>This version has no content.</div>
        )}
        {content.paragraphs.map(p =>
          renderParagraph(
            p.text, p.paragraph_index,
            annotationsByParagraph[p.paragraph_index] ?? [],
            highlightId,
            popover && popover.paragraphIndex === p.paragraph_index
              ? { charStart: popover.charStart, charEnd: popover.charEnd }
              : null,
          ),
        )}
      </div>

      {popover && <ReactionPopover popover={popover} onReact={handleReact} />}
    </div>
  );
}

// ── Feedback List View ────────────────────────────────────────────────────────

function FeedbackListView() {
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const [detail, setDetail]         = useState<StoryDetailRow | null>(null);
  const [version, setVersion]       = useState<number | null>(null);
  const [annotations, setAnnotations] = useState<AnnotationRow[]>([]);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState<string | null>(null);

  const versionParam = searchParams.get('version');

  useEffect(() => {
    if (!id) return;
    (async () => {
      setLoading(true);
      setError(null);

      const detailRes = await fetchStoryDetail(id);
      if (isApiError(detailRes)) { setLoading(false); setError(detailRes.error.message); return; }
      setDetail(detailRes);

      const resolvedVersion = versionParam ? Number(versionParam) : detailRes.latest_version;
      setVersion(resolvedVersion);

      const annRes = await apiFetch<Dataset<AnnotationRow>>(`/storyreader/stories/${id}/versions/${resolvedVersion}/annotations`);
      setLoading(false);
      if (isApiError(annRes)) { setError(annRes.error.message); return; }
      setAnnotations(annRes.rows);
    })();
  }, [id, versionParam]);

  if (loading) return <div style={{ padding: 16 }}><Skeleton /></div>;
  if (error)   return <div style={{ padding: 16 }}><ErrorCard message={error} /></div>;
  if (!detail || version === null) return null;

  return (
    <div style={{ padding: 16, maxWidth: 680, margin: '0 auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12, gap: 8, flexWrap: 'wrap' }}>
        <button onClick={() => navigate(`/storyreader/stories/${id}?version=${version}`)} style={btnStyle}>← Reader</button>
        <h2 style={{ margin: 0 }}>{detail.title} — Feedback (v{version})</h2>
      </div>

      {annotations.length === 0 && (
        <div style={{ color: '#888', fontSize: 14 }}>No marked passages on this version yet.</div>
      )}

      {annotations.map(a => (
        <div
          key={a.id}
          onClick={() => navigate(`/storyreader/stories/${id}?version=${version}&highlight=${a.id}`)}
          style={{
            padding: 12, borderRadius: 10, border: '1px solid #e0e0e0',
            marginBottom: 8, background: '#fff', cursor: 'pointer',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <ReactionIcon reaction={a.reaction} />
            <span style={{ fontSize: 12, color: '#999' }}>paragraph {a.paragraph_index}</span>
          </div>
          <div style={{ fontSize: 14 }}>
            <span style={{ color: '#999' }}>{a.context_before}</span>
            <mark style={highlightStyle}>{a.selected_text}</mark>
            <span style={{ color: '#999' }}>{a.context_after}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Root ──────────────────────────────────────────────────────────────────────

// Module-level, not component state: survives RootRedirect unmounting and
// remounting as you navigate around the app within the same page load, so
// the resume-check only ever fires once per genuine app start — not every
// time you click "← Stories" back to the root route (which would otherwise
// immediately bounce you right back into whatever story you just left, since
// leaving it is what made it "most recently active").
let resumeCheckedThisPageLoad = false;

/** App-restart resume: on a genuine fresh load, if any story has ever been
 * opened, jump straight into it (which then restores its own last position)
 * instead of the list. Deliberate in-app navigation back to "/" afterward
 * shows the list normally. */
function RootRedirect() {
  const navigate = useNavigate();
  const [checking, setChecking] = useState(!resumeCheckedThisPageLoad);

  useEffect(() => {
    if (resumeCheckedThisPageLoad) return;
    resumeCheckedThisPageLoad = true;
    (async () => {
      const res = await apiFetch<{ story_id: string | null }>('/storyreader/last-read');
      if (!isApiError(res) && res.story_id) {
        navigate(`/storyreader/stories/${res.story_id}`, { replace: true });
        return;
      }
      setChecking(false);
    })();
  }, [navigate]);

  if (checking) return <div style={{ padding: 16 }}><Skeleton /></div>;
  return <StoryListView />;
}

export default function StoryReaderApp() {
  return (
    <Routes>
      <Route path="/"                      element={<RootRedirect />} />
      <Route path="/stories/:id"           element={<ReaderView />} />
      <Route path="/stories/:id/feedback"  element={<FeedbackListView />} />
    </Routes>
  );
}
