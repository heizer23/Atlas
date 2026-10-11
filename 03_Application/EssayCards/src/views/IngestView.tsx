import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiFetch, isApiError } from '@platform-ui/api/client';
import ErrorCard from '@platform-ui/components/ErrorCard';
import type { ApiError } from '@platform-ui/api/types';
import { extractNuggetKeysClient } from '../nuggets';
import { readClipboard, writeClipboard } from '../prompts';
import { btnStyle, pageStyle, primaryBtnStyle } from '../styles';

// ── Ingest View ───────────────────────────────────────────────────────────────

// Self-contained fill-in prompt: copied to the clipboard so it can be pasted
// into an LLM (ChatGPT or similar) that has zero prior knowledge of this app.
// It restates the full payload contract from Sprint02_JsonIngestion/00_draft.md
// and 10_architecture.json §invariants — every rule here must stay in sync with
// the backend's actual manual validation in backend/routers/essays.py.
export const STUB_PROMPT = `You are generating a JSON payload for an app called EssayCards. It will be submitted verbatim as the raw HTTP body of POST /api/essaycards/essays/ingest. Reply with ONLY the JSON object — no markdown code fences (no \`\`\`), no commentary before or after, nothing but the JSON.

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
export const PLACEHOLDER_JSON = `{
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

export interface IngestSummary {
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
export function detectDroppedNuggetKeys(pastedText: string): string[] | null {
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

export function IngestView() {
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
      <div style={{ color: 'var(--md-sys-color-on-surface-variant)', fontSize: 13, marginBottom: 12 }}>
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
        <div style={{ fontSize: 12, color: 'var(--md-sys-color-on-surface-variant)', marginBottom: 8 }}>{clipboardMsg}</div>
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
          border: '1px solid var(--md-sys-color-outline)',
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
          border: '1px solid var(--md-sys-color-outline-variant)',
        }}>
          <div style={{ fontWeight: 600, marginBottom: 8 }}>Ingest succeeded</div>
          <div style={{ fontSize: 13, color: 'var(--md-sys-color-on-surface-variant)' }}>
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
