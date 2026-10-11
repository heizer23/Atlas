import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import ReactMarkdown, { defaultUrlTransform } from 'react-markdown';
import { visit } from 'unist-util-visit';
import { apiFetch, isApiError } from '@platform-ui/api/client';
import ErrorCard from '@platform-ui/components/ErrorCard';
import Skeleton from '@platform-ui/components/Skeleton';
import type { ApiError } from '@platform-ui/api/types';
import { btnStyle } from './styles';
import type { Dataset, EssayDetailRow, NuggetDetailRow, NuggetFlashcardRow, NuggetListRow, NuggetSectionRow } from './types';

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
export const NUGGET_REF_RE_CLIENT = /\[\[nugget:([a-zA-Z0-9_-]+)\]\]/g;

export function extractNuggetKeysClient(markdown: string): Set<string> {
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
export function remarkNuggetRefs(titleMap: Record<string, string>) {
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
export function nuggetAwareUrlTransform(url: string): string {
  return url.startsWith('nugget:') || url.startsWith('nugget-missing:') ? url : defaultUrlTransform(url);
}

// href scheme branch for ReactMarkdown's `a` component override: `nugget:` ->
// in-app overlay open (never a real navigation — a full page nav would break
// reading-position preservation); `nugget-missing:` -> non-clickable, styled
// as broken, key text never silently rendered as if valid; anything else ->
// ordinary <a>, unchanged behavior for normal links/images.
export function NuggetLink({ href, children, onOpenNugget }: {
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
        style={{
          color: 'var(--md-sys-color-primary)',
          textDecoration: 'underline',
          textDecorationThickness: 1,
          textUnderlineOffset: 3,
          cursor: 'pointer',
        }}
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

export function loadNuggetIndex(): Promise<Record<string, { id: string; title: string }>> {
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

export const nuggetPanelOverlayStyle: React.CSSProperties = {
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

export const nuggetPanelStyle: React.CSSProperties = {
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
export function NuggetPanel({ initialNuggetId, essayId, sectionId, onClose }: {
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
                <div style={{ color: 'var(--md-sys-color-on-surface-variant)', fontSize: 13 }}>No flashcards yet for this nugget.</div>
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
                  <div style={{ color: 'var(--md-sys-color-on-surface-variant)', fontSize: 13 }}>Not referenced by any section yet.</div>
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
export function mainSpineTitleMap(essay: EssayDetailRow): Record<string, string> {
  const map: Record<string, string> = {};
  for (const section of essay.sections) for (const n of section.nuggets) map[n.nugget_key] = n.title;
  for (const n of essay.main_spine_nuggets) map[n.nugget_key] = n.title;
  return map;
}
