import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { apiFetch, isApiError } from '@platform-ui/api/client';
import ErrorCard from '@platform-ui/components/ErrorCard';
import Skeleton from '@platform-ui/components/Skeleton';
import type { ApiError } from '@platform-ui/api/types';
import { buildQuestionExportClipboardText, writeClipboard } from '../prompts';
import { btnStyle, pageStyle, primaryBtnStyle } from '../styles';
import type { Dataset, EssayDetailRow, NuggetListRow, QuestionExportPackage, QuestionRow, QuestionUpsertResult, SectionRow } from '../types';

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

export const LEVEL_DESCRIPTIONS: Record<number, string> = {
  1: 'Foundational / spine',
  2: 'Building / explanatory structure',
  3: 'Decorating — examples, terminology, anecdotes, supporting detail',
};

export function levelLabel(level: number): string {
  const desc = LEVEL_DESCRIPTIONS[level];
  return desc ? `Level ${level} — ${desc}` : `Level ${level}`;
}

// Level 1 reads as the bold load-bearing structure, 2 as the explanatory
// layer, 3+ progressively lighter/supporting — via the existing Material 3
// tokens already used throughout this app, not a new palette.
export function levelBorderColor(level: number): string {
  if (level <= 1) return 'var(--md-sys-color-primary)';
  if (level === 2) return 'var(--md-sys-color-outline)';
  return 'var(--md-sys-color-outline-variant)';
}

export const questionFieldStyle: React.CSSProperties = {
  width: '100%',
  fontSize: 13,
  padding: 6,
  boxSizing: 'border-box',
  border: '1px solid var(--md-sys-color-outline)',
  borderRadius: 6,
  marginBottom: 6,
};

export interface SectionQuestionGroup {
  section: SectionRow;
  levels: { level: number; questions: QuestionRow[] }[];
}

export function groupQuestionsBySection(sections: SectionRow[], questions: QuestionRow[]): SectionQuestionGroup[] {
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

export function QuestionOverviewView() {
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
      <div style={{ fontSize: 13, color: 'var(--md-sys-color-on-surface-variant)', marginBottom: 24 }}>Question overview</div>

      {groups.length === 0 && (
        <div style={{ color: 'var(--md-sys-color-on-surface-variant)', fontSize: 14 }}>This essay has no sections yet.</div>
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

export function SectionQuestionGroupView({ essaySlug, group, nuggets, onChanged }: {
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
            <div style={{ color: 'var(--md-sys-color-on-surface-variant)', fontSize: 13, marginBottom: 6 }}>No questions at this level yet.</div>
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

export function QuestionItem({ essaySlug, question, nuggets, onChanged }: {
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
        {/* Sprint14: lock marker for a locked card, otherwise its maturity state; plus a revalidation marker. */}
        <div data-testid="card-state" style={{ fontSize: 11, color: 'var(--md-sys-color-on-surface-variant)', marginTop: 2 }}>
          {question.is_locked
            ? '🔒 Locked — pass the guided oral for this section to unlock'
            : `State: ${question.card_state}`}
          {question.needs_revalidation && ' · needs revalidation'}
        </div>
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
          <div style={{ fontSize: 12, color: 'var(--md-sys-color-on-surface-variant)', marginTop: 2 }}>{exportMsg.text}</div>
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
          style={{ width: 60, fontSize: 13, padding: 4, border: '1px solid var(--md-sys-color-outline)', borderRadius: 6 }}
        />
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
        <label style={{ fontSize: 12 }}>Nugget</label>
        <select
          value={nuggetId}
          onChange={e => setNuggetId(e.target.value)}
          style={{ fontSize: 13, padding: 4, border: '1px solid var(--md-sys-color-outline)', borderRadius: 6, flex: 1 }}
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

export function AddQuestionForm({ essaySlug, sectionId, defaultLevel, onDone }: {
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
          style={{ width: 60, fontSize: 13, padding: 4, border: '1px solid var(--md-sys-color-outline)', borderRadius: 6 }}
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
