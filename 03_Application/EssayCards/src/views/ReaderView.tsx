import React, { useCallback, useEffect, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import { apiFetch, isApiError } from '@platform-ui/api/client';
import ErrorCard from '@platform-ui/components/ErrorCard';
import Skeleton from '@platform-ui/components/Skeleton';
import type { ApiError } from '@platform-ui/api/types';
import { ActionMenu } from '../components/ActionMenu';
import type { ActionMenuItem } from '../components/ActionMenu';
import { EssayExaminationHistory, RecallHistory, SectionExaminationHistory, SectionGuidedHistory } from '../components/ExaminationHistory';
import { EssayRecallMarker, NEXT_STEP_LABELS, SectionProgressDots, recallDetail } from '../components/Progress';
import { NuggetLink, NuggetPanel, loadNuggetIndex, mainSpineTitleMap, nuggetAwareUrlTransform, remarkNuggetRefs } from '../nuggets';
import { buildEssayExportClipboardText, buildExamClipboardText, buildGuidedClipboardText, buildSectionExportClipboardText, buildSectionImproveClipboardText, buildSectionInsertClipboardText, writeClipboard } from '../prompts';
import { btnStyle, pageStyle, studyBtnStyle } from '../styles';
import type { Dataset, EssayDetailRow, EssayExportPackage, ExaminationPackage, GuidedPackage, SectionExportPackage, SectionProgressRow } from '../types';

// ── Sentence feedback (Sprint13_ReviewStatsSentenceFeedback) ─────────────────
//
// Sentence boundaries come ONLY from GET /essays/{id}/sentences (backend
// split_sentences) — never re-split client-side. Each sentence is an
// independent ReactMarkdown instance (paragraph wrapper flattened so sentences
// flow inline). Tapping a sentence opens SentenceFeedbackPopover; links inside
// a sentence stopPropagation (NuggetLink) so they never also open it.

export interface SentenceRow { section_id: string; sentence_index: number; text: string }
export interface SentenceFeedbackRow {
  section_id: string; sentence_index: number; sentence_text: string;
  is_difficult: boolean; is_thumbs_up: boolean;
}
export type FeedbackFlags = { is_difficult: boolean; is_thumbs_up: boolean };
export type FeedbackMap = Record<string, FeedbackFlags>;
export const feedbackKey = (sectionId: string, index: number) => `${sectionId}:${index}`;

export function SectionSentences({ sentences, nuggetTitles, feedback, openIndex, onTap, onOpenNugget }: {
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

export function SentenceFeedbackPopover({ top, left, flags, onToggle }: {
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

export function ReaderView() {
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
    { sectionId: string; kind: 'export' | 'insert' | 'improve'; ok: boolean; text: string } | null
  >(null);

  const sectionActionReady = (sectionId: string, kind: 'export' | 'insert' | 'improve') =>
    sectionActionMsg?.sectionId === sectionId && sectionActionMsg.kind === kind && sectionActionMsg.ok;

  // "Export essay" — same toggle-to-Import pattern as the per-section
  // buttons, one level up (no sectionId to key on; only one essay on this
  // page).
  const [essayExportMsg, setEssayExportMsg] = useState<{ ok: boolean; text: string } | null>(null);

  // Oral-exam export (moved here from EssayListView, internal_flow step 11):
  // copies the essay's examination package + the exam_type-appropriate
  // rubric prompt to the clipboard.
  const [examMsg, setExamMsg] = useState<string | null>(null);
  // Sprint14: busy key is "<scope>:<examType>[:<sectionId>]" so one in-flight export disables the rest.
  const [historyOpenIds, setHistoryOpenIds] = useState<Set<string>>(new Set());
  const [examBusyKey, setExamBusyKey] = useState<string | null>(null);

  const handleExportExam = async (
    scope: 'essay' | 'section',
    examType: 'guided' | 'unguided',
    sectionId?: string,
  ) => {
    if (!essay) return;
    setExamBusyKey(`${scope}:${examType}:${sectionId ?? ''}`);
    setExamMsg(null);
    const sectionParam = scope === 'section' ? `&section_id=${sectionId}` : '';
    const res = await apiFetch<ExaminationPackage>(
      `/essaycards/essays/${essay.id}/examination-package?exam_type=${examType}&scope=${scope}${sectionParam}`,
    );
    setExamBusyKey(null);
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

  // Guided learning (Levels 1-6): the package's level is chosen by the server
  // (next level to conduct). Reply is imported on /essaycards/guided/import.
  const handleExportGuided = async (sectionId: string) => {
    setExamBusyKey(`section:guided:${sectionId}`);
    setExamMsg(null);
    const res = await apiFetch<GuidedPackage>(`/essaycards/sections/${sectionId}/guided-package`);
    setExamBusyKey(null);
    if (isApiError(res)) {
      setExamMsg(`Export failed: ${res.error.message}`);
      return;
    }
    const err = await writeClipboard(buildGuidedClipboardText(res));
    setExamMsg(
      err ??
        `Copied guided Level ${res.level} (${res.level_spec.name}). Paste into ChatGPT (or similar), hold the ` +
          'conversation, then paste its JSON reply into "Import guided session".',
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

  // "Improve section": same package + same reimport path as Export section,
  // plus this section's guided oral history (?include_examinations=true) and
  // an improvement-oriented prompt. Reply is pasted into "Add / Update Essay".
  const handleImproveSection = async (sectionId: string) => {
    if (!essay) return;
    setSectionActionMsg(null);
    const res = await apiFetch<SectionExportPackage>(
      `/essaycards/essays/${essay.id}/sections/${sectionId}/export?include_examinations=true`
    );
    if (isApiError(res)) {
      setSectionActionMsg({ sectionId, kind: 'improve', ok: false, text: `Export failed: ${res.error.message}` });
      return;
    }
    // Same nugget drop-detection stash as handleExportSection.
    try {
      sessionStorage.setItem(
        `essaycards:sectionExport:${sectionId}`,
        JSON.stringify(res.focus_section_nuggets.map(n => n.nugget_key)),
      );
    } catch { /* sessionStorage unavailable — drop-detection degrades gracefully to no-op */ }

    const n = res.focus_section_examinations?.length ?? 0;
    const err = await writeClipboard(buildSectionImproveClipboardText(res));
    setSectionActionMsg({
      sectionId,
      kind: 'improve',
      ok: !err,
      text:
        err ??
        `Copied (${n} guided oral${n === 1 ? '' : 's'} included${n === 0 ? ' — nothing to learn from yet' : ''}). ` +
          'Paste into ChatGPT (or similar), discuss the improvements, then paste its JSON reply into "Add / Update Essay" to save it.',
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

  // Sprint14: per-section traffic light + lock state (GET /progress/sections?essay_id=), by section id.
  const [sectionProgress, setSectionProgress] = useState<Record<string, SectionProgressRow>>({});

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
    const [sentRes, fbRes, progRes] = await Promise.all([
      apiFetch<Dataset<SentenceRow>>(`/essaycards/essays/${id}/sentences`),
      apiFetch<Dataset<SentenceFeedbackRow>>(`/essaycards/essays/${id}/sentence-feedback`),
      apiFetch<Dataset<SectionProgressRow>>(`/essaycards/progress/sections?essay_id=${id}`),
    ]);
    setSectionProgress(
      isApiError(progRes) ? {} : Object.fromEntries(progRes.rows.map(r => [r.section_id, r])),
    );
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
      label: examBusyKey === 'essay:guided:' ? 'Preparing…' : 'Guided oral exam (essay)',
      onClick: () => handleExportExam('essay', 'guided'),
      disabled: essay.status !== 'complete' || examBusyKey !== null,
    },
    {
      label: examBusyKey === 'essay:unguided:' ? 'Preparing…' : 'Oral recall (whole essay)',
      onClick: () => handleExportExam('essay', 'unguided'),
      disabled: essay.status !== 'complete' || examBusyKey !== null,
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
        <EssayRecallMarker essay={essay} />
        {essay.revalidation_pending_count > 0 && (
          <button
            style={studyBtnStyle}
            onClick={() => navigate(`/essaycards/review?revalidate=1&essay_id=${essay.id}`)}
          >
            Revalidate ({essay.revalidation_pending_count})
          </button>
        )}
      </div>
      {essayExportMsg && (
        <div style={{ fontSize: 12, color: 'var(--md-sys-color-on-surface-variant)', marginBottom: 12 }}>{essayExportMsg.text}</div>
      )}
      {examMsg && (
        <div style={{ fontSize: 12, color: 'var(--md-sys-color-on-surface-variant)', marginBottom: 12 }}>{examMsg}</div>
      )}
      <h1 style={{ marginBottom: 12 }}>{essay.title}</h1>
      <EssayExaminationHistory essayId={essay.id} />
      <RecallHistory essayId={essay.id} hideWhenEmpty />

      {essay.main_spine_markdown.trim() !== '' && (
        <div
          className="essaycards-section-body"
          style={{
            marginBottom: 24,
            padding: '16px',
            borderRadius: 'var(--radius-card, 12px)',
            background: 'var(--md-sys-color-surface-variant, transparent)',
          }}
        >
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
        <div style={{ color: 'var(--md-sys-color-on-surface-variant)', fontSize: 14 }}>This essay has no sections yet.</div>
      )}

      {essay.sections.map(section => {
        const prog = sectionProgress[section.id];
        // Locked = the section's guided oral has not passed AND it has cards to unlock.
        const lockedWithCards = !!prog && prog.cards_total > 0 && prog.is_locked;
        return (
        <section key={section.id} id={section.anchor_slug} style={{ marginBottom: 32 }}>
          <h2 style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {prog && <SectionProgressDots sections={[prog]} />}
            {section.heading}
          </h2>
          {prog && prog.next_step && (
            <div style={{ fontSize: 12, color: 'var(--md-sys-color-on-surface-variant)', marginBottom: 6 }}>
              {recallDetail(prog.recall_status, prog.recall_next_due_at)} · Next: {NEXT_STEP_LABELS[prog.next_step]}
              {prog.next_step === 'guided_next' && prog.next_guided_level ? ` (Level ${prog.next_guided_level})` : ''}
            </div>
          )}
          {lockedWithCards && (
            <div style={{ fontSize: 12, color: 'var(--md-sys-color-on-surface-variant)', marginBottom: 6 }}>
              🔒 Flashcards locked — pass the guided oral for this section to unlock them.
            </div>
          )}
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
            items={[
              {
                label: examBusyKey === `section:guided:${section.id}`
                  ? 'Preparing…'
                  : `Guided learning — Level ${Math.min((sectionProgress[section.id]?.guided_level ?? 0) + 1, 6)}`,
                onClick: () => handleExportGuided(section.id),
                disabled: essay.status !== 'complete' || examBusyKey !== null,
              },
              {
                label: 'Import guided session →',
                onClick: () => navigate('/essaycards/guided/import'),
              },
              {
                label: examBusyKey === `section:unguided:${section.id}` ? 'Preparing…' : 'Oral recall (section)',
                onClick: () => handleExportExam('section', 'unguided', section.id),
                disabled: essay.status !== 'complete' || examBusyKey !== null,
              },
              {
                label: 'Import recall result →',
                onClick: () => navigate('/essaycards/examinations/import'),
              },
              {
                label: historyOpenIds.has(section.id) ? 'Hide examination history' : 'Examination history',
                onClick: () =>
                  setHistoryOpenIds(prev => {
                    const next = new Set(prev);
                    if (next.has(section.id)) next.delete(section.id); else next.add(section.id);
                    return next;
                  }),
              },
              {
                label: sectionActionReady(section.id, 'export') ? 'Import section →' : 'Export section',
                onClick: () =>
                  sectionActionReady(section.id, 'export')
                    ? navigate('/essaycards/ingest')
                    : handleExportSection(section.id),
              },
              {
                label: sectionActionReady(section.id, 'improve') ? 'Import improved section →' : 'Improve section',
                onClick: () =>
                  sectionActionReady(section.id, 'improve')
                    ? navigate('/essaycards/ingest')
                    : handleImproveSection(section.id),
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
            <div style={{ fontSize: 12, color: 'var(--md-sys-color-on-surface-variant)', marginTop: 4 }}>{sectionActionMsg.text}</div>
          )}
          {historyOpenIds.has(section.id) && (
            <>
              <SectionGuidedHistory sectionId={section.id} />
              <SectionExaminationHistory sectionId={section.id} />
              <RecallHistory sectionId={section.id} />
            </>
          )}
        </section>
        );
      })}

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
