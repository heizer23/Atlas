/** Display helpers for RunningTracker. Missing values render as an en dash. */

export const DASH = '–';

export function fmtDistance(m: number | null | undefined): string {
  return m == null ? DASH : `${(m / 1000).toFixed(2)} km`;
}

export function fmtDuration(s: number | null | undefined): string {
  if (s == null) return DASH;
  const t = Math.round(s);
  const h = Math.floor(t / 3600), m = Math.floor((t % 3600) / 60), sec = t % 60;
  return h > 0 ? `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}` : `${m}:${String(sec).padStart(2, '0')}`;
}

export function fmtPace(sPerKm: number | null | undefined): string {
  if (sPerKm == null || !isFinite(sPerKm)) return DASH;
  const t = Math.round(sPerKm);
  return `${Math.floor(t / 60)}:${String(t % 60).padStart(2, '0')} /km`;
}

export function fmtHr(bpm: number | null | undefined): string {
  return bpm == null ? DASH : `${Math.round(bpm)} bpm`;
}

export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return DASH;
  const d = new Date(iso);
  return isNaN(d.getTime()) ? DASH : d.toLocaleString();
}

export function syncLabel(syncState: string): string {
  return syncState === 'synced' ? 'Synced' : syncState === 'pending' ? 'Pending sync' : 'Prepared';
}
