/** Devices: pair a phone (one-time code as text and QR, expiry countdown) and manage paired devices. */

import React, { useCallback, useEffect, useState } from 'react';
import { QRCodeSVG } from 'qrcode.react';
import { apiFetch, isApiError } from '@platform-ui/api/client';
import ErrorCard from '@platform-ui/components/ErrorCard';
import Skeleton from '@platform-ui/components/Skeleton';
import type { ApiError, Dataset } from '@platform-ui/api/types';
import { buildPairingPayload } from './pairingPayload';
import { DASH, fmtDateTime } from './format';

interface DeviceRow { id: string; name: string; created_at: string; last_used_at: string | null; revoked_at: string | null; is_revoked: boolean }
interface CodeRow { id: string; code: string; expires_at: string; native_base_url: string | null }

export default function DevicesPage() {
  const [devices, setDevices] = useState<DeviceRow[] | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [code, setCode] = useState<CodeRow | null>(null);
  const [secondsLeft, setSecondsLeft] = useState(0);

  const load = useCallback(async () => {
    const res = await apiFetch<Dataset>('/runningtracker/devices');
    if (isApiError(res)) setError(res);
    else { setError(null); setDevices(res.rows as unknown as DeviceRow[]); }
  }, []);
  useEffect(() => { load(); }, [load]);

  // Countdown; the code disappears when it expires.
  useEffect(() => {
    if (!code) return;
    const tick = () => {
      const left = Math.round((new Date(code.expires_at).getTime() - Date.now()) / 1000);
      if (left <= 0) { setCode(null); setSecondsLeft(0); } else setSecondsLeft(left);
    };
    tick();
    const timer = window.setInterval(tick, 1000);
    return () => window.clearInterval(timer);
  }, [code]);

  const pair = async () => {
    const res = await apiFetch<Dataset>('/runningtracker/pairing-codes', { method: 'POST' });
    if (isApiError(res)) { setError(res); return; }
    setCode(res.rows[0] as unknown as CodeRow);
  };

  const revoke = async (id: string) => {
    const res = await apiFetch<Dataset>(`/runningtracker/devices/${id}/revoke`, { method: 'POST' });
    if (isApiError(res)) { setError(res); return; }
    load();
  };

  return (
    <div className="running-page">
      <h2 className="type-headline">Devices</h2>
      <div className="running-card">
        <strong>Pair a phone</strong>
        <span className="running-muted">Enter the code in AtlasPhone (Running Screen, pairing), or scan the QR code. The code works once.</span>
        <div><button className="running-btn primary" onClick={pair}>Pair phone</button></div>
        {code && (
          <div className="running-card" data-testid="pairing-code">
            <span className="running-code">{code.code}</span>
            <div className="running-qr" data-testid="pairing-qr">
              <QRCodeSVG value={buildPairingPayload(code.native_base_url, code.code)} size={160} />
            </div>
            <span className="running-muted">Expires in {Math.floor(secondsLeft / 60)}:{String(secondsLeft % 60).padStart(2, '0')}</span>
            {!code.native_base_url && <span className="running-warn">Server URL is not configured; type it on the phone.</span>}
          </div>
        )}
      </div>

      {error && <ErrorCard error={error} />}
      {devices === null && !error && <Skeleton />}
      {devices !== null && devices.length === 0 && <span className="running-muted">No paired devices.</span>}
      {devices?.map((d) => (
        <div className="running-card" key={d.id} data-testid="device">
          <div className="running-row spread">
            <strong>{d.name}</strong>
            {d.is_revoked
              ? <span className="running-chip revoked">Revoked</span>
              : <button className="running-btn danger" onClick={() => revoke(d.id)} aria-label={`Revoke ${d.name}`}>Revoke</button>}
          </div>
          <span className="running-muted">Last used {d.last_used_at ? fmtDateTime(d.last_used_at) : DASH}</span>
        </div>
      ))}
    </div>
  );
}
