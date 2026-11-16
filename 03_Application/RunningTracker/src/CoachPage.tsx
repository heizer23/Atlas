/** Coach: AI consent and settings, next recommended session (accept / modify / disregard), athlete profile, plan history. */

import React, { useCallback, useEffect, useState } from 'react';
import { apiFetch, isApiError } from '@platform-ui/api/client';
import ErrorCard from '@platform-ui/components/ErrorCard';
import Skeleton from '@platform-ui/components/Skeleton';
import type { ApiError, Dataset } from '@platform-ui/api/types';
import type { RunRow } from './HistoryPage';
import { DASH, fmtDateTime, fmtDuration, fmtPace } from './format';

interface SettingsRow {
  ai_enabled: boolean; consent_current: boolean; consent_version_required: number; consented_at: string | null;
  goal_text: string | null; key_configured: boolean; destination_host: string | null; model: string | null;
  payload_version: number; prompt_version: string; calls_last_24h: number; daily_cap: number;
}
interface PlanRow {
  id: string; status: string; plan_type: string; title: string; summary: string; rationale: string | null; total_s: number;
  target_distance_m: number | null; hr_min: number | null; hr_max: number | null; pace_fast_s_per_km: number | null;
  pace_slow_s_per_km: number | null; cad_min: number | null; cad_max: number | null; segment_count: number;
  created_at: string; decided_at: string | null; run_id: string | null; outcome_summary: string | null;
}
interface ProfileRow { id: string; label: string; basis: string; value_text: string; confidence: number | null; n_runs: number }
interface PreviewRow { destination_host: string | null; model: string | null; byte_size: number; history_runs: number; payload_json: string }

const SENT = 'Per run: relative time and weekday, run kind, distance, moving time, pace, heart rate, cadence, step length, recovery (HRR60/HRR120), per-kilometre splits and 60-second pace / heart-rate / cadence series. Up to 10 earlier runs in the same summary form, your athlete profile, the previous recommendation with its outcome and your goal text.';
const NEVER = 'Never sent: GPS coordinates, tracks or route names, absolute dates and clock times, ids, run titles, comments or categories, raw samples, device information, your identity.';

export default function CoachPage() {
  const [settings, setSettings] = useState<SettingsRow | null>(null);
  const [plan, setPlan] = useState<PlanRow | null | undefined>(undefined);
  const [plans, setPlans] = useState<PlanRow[]>([]);
  const [profile, setProfile] = useState<ProfileRow[]>([]);
  const [runs, setRuns] = useState<RunRow[]>([]);
  const [error, setError] = useState<ApiError | null>(null);
  const [goal, setGoal] = useState('');
  const [previewRun, setPreviewRun] = useState('');
  const [preview, setPreview] = useState<PreviewRow | null>(null);

  const load = useCallback(async () => {
    const [s, n, p, pr, r] = await Promise.all([
      apiFetch<Dataset>('/runningtracker/coach/settings'),
      apiFetch<Dataset>('/runningtracker/coach/next-session'),
      apiFetch<Dataset>('/runningtracker/coach/plans'),
      apiFetch<Dataset>('/runningtracker/coach/profile'),
      apiFetch<Dataset>('/runningtracker/runs?status=complete&page_size=50'),
    ]);
    for (const res of [s, n, p, pr, r]) if (isApiError(res)) { setError(res); return; }
    const settingsRow = (s as Dataset).rows[0] as unknown as SettingsRow;
    setError(null);
    setSettings(settingsRow);
    setGoal(settingsRow.goal_text ?? '');
    setPlan(((n as Dataset).rows[0] as unknown as PlanRow | undefined) ?? null);
    setPlans((p as Dataset).rows as unknown as PlanRow[]);
    setProfile((pr as Dataset).rows as unknown as ProfileRow[]);
    const runRows = (r as Dataset).rows as unknown as RunRow[];
    setRuns(runRows);
    setPreviewRun((cur) => cur || runRows[0]?.id || '');
  }, []);
  useEffect(() => { load(); }, [load]);

  const patchSettings = async (body: Record<string, unknown>) => {
    const res = await apiFetch<Dataset>('/runningtracker/coach/settings', { method: 'PATCH', body: JSON.stringify(body) });
    if (isApiError(res)) { setError(res); return; }
    load();
  };

  const showPreview = async () => {
    const res = await apiFetch<Dataset>(`/runningtracker/coach/analysis-preview?run_id=${previewRun}`);
    if (isApiError(res)) { setError(res); return; }
    setError(null);
    setPreview(res.rows[0] as unknown as PreviewRow);
  };

  if (error && !settings) return <div className="running-page"><ErrorCard error={error} /></div>;
  if (!settings) return <div className="running-page"><Skeleton /></div>;

  return (
    <div className="running-page">
      <h2 className="type-headline">Coach</h2>
      {error && <ErrorCard error={error} />}

      <div className="running-card" data-testid="consent-card">
        <strong>AI analysis</strong>
        <span className="running-muted">
          Off by default. When on, the Analyse run button on a run sends a summary to {settings.destination_host ?? 'an AI provider (not configured)'}
          {settings.model ? ` (model ${settings.model})` : ''}. Nothing is sent automatically and live coaching never needs the AI.
        </span>
        <span className="running-muted" data-testid="sent-categories">{SENT}</span>
        <span className="running-muted" data-testid="never-sent">{NEVER}</span>
        <div className="running-row">
          <select className="running-input" aria-label="Run for preview" value={previewRun} onChange={(e) => setPreviewRun(e.target.value)}>
            {runs.map((r) => <option key={r.id} value={r.id}>{fmtDateTime(r.started_at)}</option>)}
          </select>
          <button className="running-btn" disabled={!previewRun} onClick={showPreview}>Show what would be sent</button>
        </div>
        {preview && (
          <div data-testid="payload-preview">
            <span className="running-muted">{preview.byte_size} bytes, {preview.history_runs} earlier runs</span>
            <pre style={{ overflow: 'auto', maxHeight: 240, fontSize: 12 }}>{preview.payload_json}</pre>
          </div>
        )}
        {!settings.key_configured && <span className="running-warn" data-testid="not-configured">The server has no AI key and model configured, so AI analysis cannot be enabled.</span>}
        {settings.ai_enabled && !settings.consent_current && <span className="running-warn">The consent is outdated. Enable again to accept the current terms.</span>}
        <div className="running-row">
          {settings.ai_enabled
            ? <button className="running-btn" onClick={() => patchSettings({ ai_enabled: false })}>Disable AI analysis</button>
            : <button className="running-btn primary" disabled={!settings.key_configured}
                onClick={() => patchSettings({ ai_enabled: true, consent_version: settings.consent_version_required })}>Enable AI analysis</button>}
          <span className="running-chip" data-testid="ai-state">{settings.ai_enabled && settings.consent_current ? 'AI enabled' : 'AI off'}</span>
          <span className="running-muted">{settings.calls_last_24h}/{settings.daily_cap} calls in 24 h</span>
        </div>
        <label htmlFor="goal"><strong>Goal</strong></label>
        <input id="goal" className="running-input" maxLength={500} placeholder="e.g. Run a relaxed half marathon" value={goal} onChange={(e) => setGoal(e.target.value)} />
        <div><button className="running-btn" onClick={() => patchSettings({ goal_text: goal.trim() === '' ? null : goal.trim() })}>Save goal</button></div>
      </div>

      <NextSession plan={plan} onChanged={load} onError={setError} />

      <div className="running-card" data-testid="profile-card">
        <strong>Athlete profile</strong>
        {profile.length === 0 ? <span className="running-muted">No profile yet. It grows with every finished run.</span> : (
          <table className="running-table" data-testid="profile">
            <thead><tr><th>Value</th><th>Basis</th><th>Confidence</th></tr></thead>
            <tbody>
              {profile.map((p) => (
                <tr key={p.id}>
                  <td>{p.label}: {p.value_text}</td>
                  <td>{p.basis}</td>
                  <td>{p.confidence == null ? DASH : `${Math.round(p.confidence * 100)}%`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="running-card" data-testid="history-card">
        <strong>Plan history</strong>
        {plans.length === 0 ? <span className="running-muted">No plans yet.</span> : (
          <table className="running-table" data-testid="plan-history">
            <thead><tr><th>Plan</th><th>Status</th><th>Outcome</th></tr></thead>
            <tbody>
              {plans.map((p) => (
                <tr key={p.id}>
                  <td>{p.title}<br /><span className="running-muted">{fmtDateTime(p.created_at)}</span></td>
                  <td>{p.status}</td>
                  <td>{p.outcome_summary ?? DASH}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

// ---- next session --------------------------------------------------------------------------------------------------

const num = (v: string): number | null => (v.trim() === '' ? null : Number(v));
const str = (v: number | null | undefined) => (v == null ? '' : String(v));

function NextSession({ plan, onChanged, onError }: { plan: PlanRow | null | undefined; onChanged: () => void; onError: (e: ApiError) => void }) {
  const [editing, setEditing] = useState(false);
  const [f, setF] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);

  const decide = async (body: Record<string, unknown>) => {
    const res = await apiFetch<Dataset>(`/runningtracker/coach/plans/${plan!.id}`, { method: 'PATCH', body: JSON.stringify(body) });
    if (isApiError(res)) { onError(res); return false; }
    setEditing(false);
    onChanged();
    return true;
  };

  const startEdit = () => {
    if (!plan) return;
    setF({
      hrMin: str(plan.hr_min), hrMax: str(plan.hr_max), paceFast: str(plan.pace_fast_s_per_km), paceSlow: str(plan.pace_slow_s_per_km),
      cadMin: str(plan.cad_min), cadMax: str(plan.cad_max), dist: str(plan.target_distance_m),
    });
    setFormError(null);
    setEditing(true);
  };

  // Untouched dimension -> key omitted; all empty -> null (clear); both filled -> object; one empty -> message.
  const submitModify = async () => {
    const o: Record<string, unknown> = {};
    const pair = (lo: string, hi: string, a0: number | null, b0: number | null, k1: string, k2: string): string | null => {
      const a = num(f[lo]), b = num(f[hi]);
      if (a === a0 && b === b0) return null;
      if (a === null && b === null) return 'null';
      if (a === null || b === null) return 'Enter both ends of the range, or clear both.';
      return JSON.stringify({ [k1]: a, [k2]: b });
    };
    for (const [dim, lo, hi, a0, b0, k1, k2] of [
      ['hr', 'hrMin', 'hrMax', plan!.hr_min, plan!.hr_max, 'min', 'max'],
      ['pace', 'paceFast', 'paceSlow', plan!.pace_fast_s_per_km, plan!.pace_slow_s_per_km, 'fast_s_per_km', 'slow_s_per_km'],
      ['cadence', 'cadMin', 'cadMax', plan!.cad_min, plan!.cad_max, 'min', 'max'],
    ] as [string, string, string, number | null, number | null, string, string][]) {
      const r = pair(lo, hi, a0, b0, k1, k2);
      if (r === null) continue;
      if (r.startsWith('Enter')) { setFormError(r); return; }
      o[dim] = r === 'null' ? null : JSON.parse(r);
    }
    const dist = num(f.dist);
    if (dist !== plan!.target_distance_m) o.target_distance_m = dist;
    setFormError(null);
    await decide({ status: 'accepted', overrides: o });
  };

  const field = (key: string, label: string) => (
    <label className="running-muted">{label}
      <input className="running-input" style={{ width: 80, marginLeft: 6 }} inputMode="numeric" aria-label={label} value={f[key] ?? ''} onChange={(e) => setF({ ...f, [key]: e.target.value })} />
    </label>
  );

  return (
    <div className="running-card" data-testid="next-session">
      <strong>Next recommended session</strong>
      {plan === undefined && <Skeleton />}
      {plan === null && <span className="running-muted" data-testid="no-session">No session recommended. Analyse a finished run from its detail page.</span>}
      {plan && (
        <>
          <div className="running-row spread">
            <span data-testid="plan-title"><strong>{plan.title}</strong></span>
            <span className="running-chip" data-testid="plan-status">{plan.status}</span>
          </div>
          <span data-testid="plan-summary">{plan.summary}</span>
          {plan.rationale && <span className="running-muted">{plan.rationale}</span>}
          <span className="running-muted">
            Duration {fmtDuration(plan.total_s)} · HR {plan.hr_min == null ? DASH : `${plan.hr_min}-${plan.hr_max}`} · pace{' '}
            {plan.pace_fast_s_per_km == null ? DASH : `${fmtPace(plan.pace_fast_s_per_km)} to ${fmtPace(plan.pace_slow_s_per_km)}`} · cadence{' '}
            {plan.cad_min == null ? DASH : `${plan.cad_min}-${plan.cad_max}`}
          </span>
          {plan.status === 'accepted' && <span className="running-muted">Accepted. The phone picks it up when you open the Run screen.</span>}
          {!editing && (
            <div className="running-row">
              {plan.status === 'recommended' && <button className="running-btn primary" onClick={() => decide({ status: 'accepted' })}>Accept</button>}
              <button className="running-btn" onClick={startEdit}>Modify</button>
              <button className="running-btn danger" onClick={() => decide({ status: 'disregarded' })}>Disregard</button>
            </div>
          )}
          {editing && (
            <div className="running-card" data-testid="modify-form">
              <div className="running-row">{field('hrMin', 'HR min')}{field('hrMax', 'HR max')}</div>
              <div className="running-row">{field('paceFast', 'Pace fast (s/km)')}{field('paceSlow', 'Pace slow (s/km)')}</div>
              <div className="running-row">{field('cadMin', 'Cadence min')}{field('cadMax', 'Cadence max')}</div>
              <div className="running-row">{field('dist', 'Distance (m)')}</div>
              <span className="running-muted">Empty fields clear that target. Untouched fields stay as they are.</span>
              {formError && <span className="running-warn">{formError}</span>}
              <div className="running-row">
                <button className="running-btn primary" onClick={submitModify}>Accept with changes</button>
                <button className="running-btn" onClick={() => setEditing(false)}>Cancel</button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
