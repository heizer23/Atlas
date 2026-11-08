/**
 * Types and pure helpers for the finish celebration (FinishModal). Types mirror the
 * Snapshot / Celebration records in backend/routers/workout.py; the backend owns all statistics.
 */

export interface RankedStreak {
  rank: number;
  start: string;
  end: string;
  length: number;
  current: boolean;
}

export interface Snapshot {
  today: string;
  years: number[];
  monthly: Record<string, (number | null)[]>;
  frequency: Record<string, (number | null)[]>;
  month: {
    year: number;
    month: number;
    day: number;
    count: number;
    last_year_count: number | null;
    last_year_through: string;
    ahead: number | null;
  };
  today_counts: boolean;
  ranking: RankedStreak[];
  ranking_year: RankedStreak[];
  current: { length: number; rank: number | null; total: number; rank_year: number | null; total_year: number };
}

export interface Celebration {
  before: Snapshot;
  after: Snapshot;
  changed: boolean;
  note: string | null;
  crossed_champions: boolean;
}

export interface ExerciseSummary {
  exercise: string;
  reps: number;
  weight_kg: number | null;
  prev_reps: number | null;
  prev_weight_kg: number | null;
  prev_date: string | null;
  weight_changed: boolean;
}

export interface SessionSummary {
  duration_sec: number | null;
  avg_duration_sec: number | null;
  avg_count: number;
  exercises: ExerciseSummary[];
}

export function formatDuration(sec: number): string {
  const m = Math.round(sec / 60);
  return m < 60 ? `${m} min` : `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, "0")} min`;
}

export interface CompletionResult {
  celebration: Celebration | null;
  summary?: SessionSummary | null;
  already_finished: boolean;
}

export type StreakView = "all" | "year";

export const CHAMPIONS_MIN = 10;

// ── Ranking layout ────────────────────────────────────────────────────────────

export const HEADER_H = 26;
export const CHAMP_H = 24;
export const CURRENT_H = 38;
export const READABLE_H = 24;
export const LABEL_H = 14; // compact rows that carry a rank/length label need room for the text

export interface LayoutItem {
  key: string;
  kind: "header" | "row";
  y: number;
  h: number;
  streak?: RankedStreak;
  /** Compact rows only: whether the rank/length labels are drawn. */
  labelled?: boolean;
}

export interface Layout {
  items: LayoutItem[];
  height: number;
}

export function streakKey(s: RankedStreak): string {
  return s.current ? "current" : s.start;
}

/**
 * The ranking as it stood before an event: the current streak at its old length, or — when today
 * starts a new streak — a zero-length placeholder at the bottom, so it can grow and then climb.
 */
export function rankingBefore(before: RankedStreak[], after: RankedStreak[]): RankedStreak[] {
  if (before.some((s) => s.current)) return before;
  const cur = after.find((s) => s.current);
  if (!cur) return before;
  return [...before, { ...cur, length: 0, rank: before.length + 1 }];
}

const endRow = (i: number, n: number) => i === 0 || i === n - 1;

/**
 * Champions League (10+ days) rows are always readable; the rest are a thin compact overview that is
 * sized to fit, or readable rows with dates when `expanded`. The current streak is always a full row.
 */
export function layoutRanking(ranking: RankedStreak[], expanded: boolean, othersH: number): Layout {
  const champs = ranking.filter((s) => s.length >= CHAMPIONS_MIN);
  const others = ranking.filter((s) => s.length < CHAMPIONS_MIN);
  const items: LayoutItem[] = [];
  let y = 0;
  const push = (item: Omit<LayoutItem, "y">) => {
    items.push({ ...item, y });
    y += item.h;
  };
  if (champs.length) {
    push({ key: "h-champ", kind: "header", h: HEADER_H });
    champs.forEach((s) => push({ key: streakKey(s), kind: "row", h: s.current ? CURRENT_H : CHAMP_H, streak: s, labelled: true }));
  }
  if (others.length) {
    push({ key: "h-others", kind: "header", h: HEADER_H });
    others.forEach((s, i) =>
      push({
        key: streakKey(s),
        kind: "row",
        h: s.current ? CURRENT_H : expanded ? READABLE_H : endRow(i, others.length) ? Math.max(othersH, LABEL_H) : othersH,
        streak: s,
        labelled: expanded || s.current || endRow(i, others.length),
      }),
    );
  }
  return { items, height: y };
}

/** Row height for the compact overview so that all non-champion streaks fit in `available` px (3–8px). */
export function fitOthersHeight(ranking: RankedStreak[], available: number): number {
  const champs = ranking.filter((s) => s.length >= CHAMPIONS_MIN);
  const others = ranking.filter((s) => s.length < CHAMPIONS_MIN);
  if (!others.length) return 8;
  const fixed =
    (champs.length ? HEADER_H : 0) +
    HEADER_H +
    champs.reduce((n, s) => n + (s.current ? CURRENT_H : CHAMP_H), 0) +
    others.filter((s) => s.current).length * CURRENT_H;
  const labelled = others.filter((s, i) => !s.current && endRow(i, others.length)).length;
  const flexible = others.filter((s) => !s.current).length - labelled;
  if (flexible <= 0) return 8;
  return Math.max(3, Math.min(8, Math.floor((available - fixed - labelled * LABEL_H) / flexible)));
}

// ── Formatting ────────────────────────────────────────────────────────────────

/** Streak colour by start year relative to the current year (the legend labels the same buckets). */
export const AGE_COLOURS = ["#7CC4B2", "#9FB6DA", "#BCAEDD", "#C8CED8"]; // this year, last year, two years ago, earlier

export function ageBucket(startIso: string, thisYear: number): number {
  return Math.min(3, Math.max(0, thisYear - Number(startIso.slice(0, 4))));
}

export function ageLabels(thisYear: number): string[] {
  return [String(thisYear), String(thisYear - 1), String(thisYear - 2), "Earlier"];
}

export function fmtDay(iso: string, thisYear: number): string {
  const [y, m, d] = iso.split("-").map(Number);
  const s = new Date(y, m - 1, d).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
  return y === thisYear ? s : `${s} ${y}`;
}

export function fmtRange(s: RankedStreak, today: string, thisYear: number): string {
  const end = s.current && s.end >= today ? "today" : fmtDay(s.end, thisYear);
  return s.start === s.end ? end : `${fmtDay(s.start, thisYear)} – ${end}`;
}

export function monthName(m: number, long = true): string {
  return new Date(2000, m - 1, 1).toLocaleDateString("en-GB", { month: long ? "long" : "short" });
}

export function aheadText(ahead: number | null): string | null {
  if (ahead === null) return null;
  if (ahead === 0) return "level with last year";
  return ahead > 0 ? `${ahead} ahead of last year` : `${-ahead} behind last year`;
}

/** Stronger emphasis when the new day caught up with or overtook last year. */
export function caughtUp(beforeAhead: number | null, afterAhead: number | null): boolean {
  return beforeAhead !== null && afterAhead !== null && beforeAhead <= 0 && afterAhead > beforeAhead && afterAhead >= 0;
}
