import { useCallback, useState } from 'react';
import { apiFetch, isApiError } from '@platform-ui/api/client';

export type Post = <T>(path: string, body?: unknown, method?: string) => Promise<T | null>;

// ── Helpers ───────────────────────────────────────────────────────────────────

export function dayLabel(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString('en-GB', { weekday: 'short', day: '2-digit', month: '2-digit' });
}

export function num(v: number): string { return String(Math.round(v * 100) / 100); }

export function todayLocal(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

export function readPref(key: string, fallback: string): string {
  try { return localStorage.getItem(`kitchen.${key}`) ?? fallback; } catch { return fallback; }
}

export function writePref(key: string, value: string): void {
  try { localStorage.setItem(`kitchen.${key}`, value); } catch { /* per-viewer convenience only */ }
}

export function useAction(): { post: Post; error: string | null; busy: boolean } {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const post: Post = useCallback(async (path, body, method = 'POST') => {
    setBusy(true); setError(null);
    const res = await apiFetch<any>(`/kitchen${path}`, { method, body: body === undefined ? undefined : JSON.stringify(body) });
    setBusy(false);
    if (isApiError(res)) { setError(res.error.message); return null; }
    return res;
  }, []);
  return { post, error, busy };
}

