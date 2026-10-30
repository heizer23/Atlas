import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiFetch, isApiError } from '@platform-ui/api/client';
import ErrorCard from '@platform-ui/components/ErrorCard';
import Skeleton from '@platform-ui/components/Skeleton';
import type { ApiError } from '@platform-ui/api/types';
import { ActionMenu } from '../components/ActionMenu';
import { EssayRecallMarker, LevelBar, ProgressLegend, SectionProgressDots } from '../components/Progress';
import { SERIF, btnStyle, pageStyle, studyBtnStyle } from '../styles';
import type { Dataset, EssayRow, SectionProgressRow } from '../types';

// ── Essay List View ───────────────────────────────────────────────────────────

// Preferred display order for known overview categories. Anything not listed
// here sorts after these, alphabetically; essays with no category (null) go
// into a trailing "Uncategorized" group. This list is a UI-side convention —
// the backend stores `category` as free text and imposes no fixed set.
export const CATEGORY_ORDER = ['Art', 'History', 'Philosophy'];
export const UNCATEGORIZED = 'Uncategorized';

export function categoryRank(name: string): number {
  const i = CATEGORY_ORDER.indexOf(name);
  if (i !== -1) return i;
  if (name === UNCATEGORIZED) return Number.MAX_SAFE_INTEGER;
  return CATEGORY_ORDER.length;
}

export function groupEssaysByCategory(essays: EssayRow[]): [string, EssayRow[]][] {
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

export function formatExamDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}

// ── Category collapse/expand (Sprint12_FSRSAndUXOverhaul) ──────────────────
//
// Persisted per category name via localStorage, key
// essaycards:categoryCollapsed:<category> ('true'/'false'; UNCATEGORIZED for
// the null-category group). Default expanded (false) when no stored value
// exists. localStorage can throw (private browsing, disabled storage) — both
// helpers degrade gracefully to the default rather than erroring.

export function categoryCollapseKey(category: string): string {
  return `essaycards:categoryCollapsed:${category}`;
}

export function loadCategoryCollapsed(category: string): boolean {
  try {
    return localStorage.getItem(categoryCollapseKey(category)) === 'true';
  } catch {
    return false;
  }
}

export function saveCategoryCollapsed(category: string, collapsed: boolean): void {
  try {
    localStorage.setItem(categoryCollapseKey(category), collapsed ? 'true' : 'false');
  } catch {
    /* localStorage unavailable — collapse state just won't persist across visits */
  }
}

export function CategoryCollapseToggle({ category, collapsed, onToggle }: {
  category: string;
  collapsed: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      style={{
        ...btnStyle,
        border: 'none',
        padding: 0,
        width: 40,
        justifyContent: 'center',
        display: 'inline-flex',
        alignItems: 'center',
        color: 'var(--md-sys-color-on-surface-variant)',
      }}
      aria-expanded={!collapsed}
      aria-label={`${collapsed ? 'Expand' : 'Collapse'} ${category}`}
      onClick={onToggle}
    >
      <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"
        style={{ transform: collapsed ? 'rotate(-90deg)' : 'none', transition: 'transform 150ms ease' }}>
        <path d="M3.5 6 8 10.5 12.5 6" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </button>
  );
}

export function EssayListView() {
  const navigate = useNavigate();
  const [essays, setEssays] = useState<EssayRow[]>([]);
  // Sprint14: section dots, grouped client-side by essay_id (flat Dataset).
  const [sectionsByEssay, setSectionsByEssay] = useState<Record<string, SectionProgressRow[]>>({});
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
      const [res, progress] = await Promise.all([
        apiFetch<Dataset<EssayRow>>('/essaycards/essays'),
        apiFetch<Dataset<SectionProgressRow>>('/essaycards/progress/sections'),
      ]);
      setLoading(false);
      if (isApiError(res)) {
        setError(res);
        return;
      }
      if (isApiError(progress)) {
        setError(progress);
        return;
      }
      setEssays(res.rows);
      const grouped: Record<string, SectionProgressRow[]> = {};
      for (const row of progress.rows) (grouped[row.essay_id] ??= []).push(row);
      setSectionsByEssay(grouped);
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
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <h2 className="type-headline" style={{ margin: 0 }}>Essays</h2>
        <ActionMenu
          align="right"
          items={[
            { label: 'Images', onClick: () => navigate('/essaycards/images') },
            { label: 'Import exam results', onClick: () => navigate('/essaycards/examinations/import') },
            { label: 'Import exploration', onClick: () => navigate('/essaycards/explore/import') },
          ]}
        />
      </div>

      {!loading && !error && essays.length > 0 && <ProgressLegend />}
      {loading && <Skeleton />}
      {error && <ErrorCard error={error} />}
      {!loading && !error && essays.length === 0 && (
        <div style={{ color: 'var(--md-sys-color-on-surface-variant)', fontSize: 14 }}>
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
          const tot = rows.reduce((n, e) => n + e.progress_total, 0);
          const open = rows.reduce((n, e) => n + e.open_count, 0);
          const recallDue = rows.reduce((n, e) => n + e.recall_due_count, 0);
          const categoryCollapsed = showHeadings && isCollapsed(category);
          const secs = (e: EssayRow) => sectionsByEssay[e.id] ?? [];
          const dueIn = (e: EssayRow) => e.recall_due_count > 0;
          return (
            <div
              key={category}
              style={{
                marginBottom: 12, borderRadius: 20, background: 'var(--md-sys-color-surface)',
                border: '1px solid var(--md-sys-color-outline-variant)',
              }}
            >
              {showHeadings && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '12px 12px 12px 4px' }}>
                  <CategoryCollapseToggle
                    category={category}
                    collapsed={categoryCollapsed}
                    onToggle={() => toggleCategory(category)}
                  />
                  <div style={{ flex: '1 1 auto', minWidth: 0 }}>
                    <div style={{ fontFamily: SERIF, fontSize: 24, fontWeight: 500, lineHeight: 1.15, color: 'var(--md-sys-color-on-surface)' }}>
                      {category}
                    </div>
                    <div style={{ fontSize: 14, color: 'var(--md-sys-color-on-surface-variant)', marginTop: 2 }}>
                      {open} open{recallDue > 0 ? ` · ${recallDue} recall due` : ''}
                    </div>
                  </div>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                    {rows.map(e => (
                      <LevelBar key={e.id} sections={secs(e)} recallDue={dueIn(e)} label={e.title} width={7} height={34} />
                    ))}
                  </span>
                  {isTopic && tot > 0 && (
                    <button
                      aria-label="Study"
                      title="Study"
                      style={{
                        width: 48, height: 48, borderRadius: '50%', flexShrink: 0, cursor: 'pointer', padding: 0,
                        border: '1px solid var(--md-sys-color-outline)', background: 'transparent',
                        color: 'var(--md-sys-color-on-surface)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                      }}
                      onClick={() => navigate(`/essaycards/review?topic=${encodeURIComponent(category)}`)}
                    >
                      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" aria-hidden="true">
                        <path d="M8 5.5v13l10.5-6.5z" />
                      </svg>
                    </button>
                  )}
                </div>
              )}
              {!categoryCollapsed && rows.map((e, i) => (
                <div
                  key={e.id}
                  onClick={() => navigate(`/essaycards/essays/${e.id}`)}
                  style={{
                    padding: '14px 16px 14px 20px',
                    margin: showHeadings ? '0 12px' : 0,
                    borderTop: showHeadings || i > 0 ? '1px solid var(--md-sys-color-outline-variant)' : 'none',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'stretch',
                    gap: 12,
                  }}
                >
                  <LevelBar sections={secs(e)} recallDue={dueIn(e)} label={e.title} width={5} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
                      <span style={{ fontFamily: SERIF, fontWeight: 500, fontSize: 18, lineHeight: 1.3 }}>{e.title}</span>
                      {e.revalidation_pending_count > 0 && (
                        <button
                          style={{ ...studyBtnStyle, padding: '2px 8px', fontSize: 12 }}
                          onClick={ev => {
                            ev.stopPropagation();
                            navigate(`/essaycards/review?revalidate=1&essay_id=${e.id}`);
                          }}
                        >
                          Revalidate ({e.revalidation_pending_count})
                        </button>
                      )}
                    </div>
                    <div style={{ marginTop: 6, display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                      <SectionProgressDots sections={secs(e)} />
                      <EssayRecallMarker essay={e} size={20} />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          );
        });
      })()}
    </div>
  );
}
