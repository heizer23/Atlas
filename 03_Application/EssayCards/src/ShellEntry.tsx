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
 */

import React, { useCallback, useEffect, useState } from 'react';
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
        <button style={primaryBtnStyle} onClick={() => navigate('/essaycards/review')}>
          Due for review
        </button>
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

  if (loading) return <div style={pageStyle}><Skeleton /></div>;
  if (error) return <div style={pageStyle}><ErrorCard error={error} /></div>;
  if (!essay) return <div style={pageStyle}>Essay not found.</div>;

  return (
    <div style={pageStyle}>
      <button style={{ ...btnStyle, marginBottom: 12 }} onClick={() => navigate('/essaycards')}>
        ← All essays
      </button>
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
          <button
            style={btnStyle}
            onClick={() => navigate(`/essaycards/review?essay_id=${essay.id}&section_id=${section.id}`)}
          >
            Review this section
          </button>
        </section>
      ))}
    </div>
  );
}

// ── Review Session View ───────────────────────────────────────────────────────

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
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [essayId, sectionId]);

  const current = queue[index] ?? null;

  const handleGrade = async (grade: Grade) => {
    if (!current || grading) return;
    setGrading(true);
    const res = await apiFetch(`/essaycards/flashcards/${current.flashcard_id}/review`, {
      method: 'POST',
      body: JSON.stringify({ grade }),
    });
    setGrading(false);
    if (isApiError(res)) {
      setError(res as ApiError);
      return;
    }
    setFlipped(false);
    setIndex(i => i + 1);
  };

  if (loading) return <div style={pageStyle}><Skeleton /></div>;
  if (error) return <div style={pageStyle}><ErrorCard error={error} /></div>;

  if (!current) {
    return (
      <div style={pageStyle}>
        <h2>Review session</h2>
        <div style={{ color: '#888', fontSize: 14 }}>
          {queue.length === 0 ? 'Nothing due right now.' : 'Session complete — nothing left in the queue.'}
        </div>
        <button style={{ ...btnStyle, marginTop: 12 }} onClick={() => navigate('/essaycards')}>
          ← All essays
        </button>
      </div>
    );
  }

  return (
    <div style={pageStyle}>
      <div style={{ fontSize: 12, color: '#888', marginBottom: 12 }}>
        Card {index + 1} of {queue.length}
      </div>

      <div style={{
        padding: 20,
        borderRadius: 8,
        border: '1px solid #e0e0e0',
        marginBottom: 16,
        minHeight: 100,
      }}>
        <div style={{ fontWeight: 600 }}>{current.question}</div>
        {flipped && (
          <>
            <div style={{ borderTop: '1px solid #e0e0e0', paddingTop: 12, marginTop: 12 }}>
              {current.answer}
            </div>
            <button
              style={{ ...btnStyle, marginTop: 12 }}
              onClick={() => navigate(`/essaycards/essays/${current.essay_id}#${current.anchor_slug}`)}
            >
              Jump to passage
            </button>
          </>
        )}
      </div>

      {!flipped && (
        <button style={primaryBtnStyle} onClick={() => setFlipped(true)}>Flip</button>
      )}

      {flipped && (
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button style={btnStyle} disabled={grading} onClick={() => handleGrade('again')}>Again</button>
          <button style={btnStyle} disabled={grading} onClick={() => handleGrade('hard')}>Hard</button>
          <button style={btnStyle} disabled={grading} onClick={() => handleGrade('good')}>Good</button>
          <button style={btnStyle} disabled={grading} onClick={() => handleGrade('easy')}>Easy</button>
        </div>
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

Fill in the template below. Every value is an instruction describing what belongs there — replace each one with real content, and remove these instructions from your reply:

{
  "title": "the essay's display title, e.g. \\"Why Rome Fell\\"",
  "slug": "a url-safe stable id for the essay: letters, digits, underscore, hyphen only, no spaces, e.g. why_rome_fell — submitting this JSON again later with the same slug UPDATES this essay instead of creating a new one",
  "sections": [
    {
      "heading": "this section's display heading, e.g. \\"The Economic Causes\\"",
      "anchor_slug": "a url-safe stable id for this section, unique within the essay, e.g. economic-causes — used for \\"jump to passage\\" links, so keep it short and don't rename it on a later update",
      "body_markdown": "the ACTUAL essay text for this section, written in Markdown, roughly 300-600 words ('about one page') — this is what the reader reads. Do not summarize; write the real prose. Flashcards are NOT marked inline in this text (that inline-fence convention is only used by this app's separate offline markdown-file ingestion path, not this JSON format) — flashcards go in the sibling 'cards' list below instead.",
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

Worked mini-example (2 sections, realistic content, for the topic "Why Rome Fell" — do not reuse this content, it's here only to show the pattern):

{
  "title": "Why Rome Fell",
  "slug": "why_rome_fell",
  "sections": [
    {
      "heading": "The Economic Causes",
      "anchor_slug": "economic-causes",
      "body_markdown": "By the 3rd century, Rome's currency had been debased so many times that contemporaries spoke of a \\"debasement crisis\\" eroding trust in coinage across the empire. Tax revenue fell as trade contracted, while the cost of defending an ever-longer frontier kept rising...",
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

// ── Root ──────────────────────────────────────────────────────────────────────

export default function EssayCardsApp() {
  return (
    <Routes>
      <Route path="/" element={<EssayListView />} />
      <Route path="/essays/:id" element={<ReaderView />} />
      <Route path="/review" element={<ReviewSessionView />} />
      <Route path="/ingest" element={<IngestView />} />
    </Routes>
  );
}
