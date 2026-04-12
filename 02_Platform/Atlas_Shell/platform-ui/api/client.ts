// platform-ui/api/client.ts — do not modify during feature work
// See: 02_Platform/Atlas_Shell/UI_Implementation.md §3

import type { ApiError } from "./types";

interface RequestLogEntry {
  request_id: string;
  url:        string;
  method:     string;
  status:     number;
  duration:   number;   // ms
  response:   unknown;
}

const requestLog: RequestLogEntry[] = [];  // ring buffer, max 50

export async function apiFetch<T>(
  path: string,
  options?: RequestInit
): Promise<T | ApiError> {
  // crypto.randomUUID requires a secure context (HTTPS/localhost); fall back for plain HTTP
  const request_id = (typeof crypto.randomUUID === 'function'
    ? crypto.randomUUID()
    : Math.random().toString(36).slice(2, 10) + Math.random().toString(36).slice(2, 6)
  ).slice(0, 8);
  const url    = `/api${path}`;
  const method = options?.method ?? "GET";
  const start  = Date.now();

  try {
    const res  = await fetch(url, {
      ...options,
      headers: { "Content-Type": "application/json", ...options?.headers },
    });
    const text = await res.text();
    if (!text) throw new Error(`HTTP ${res.status} — empty response (is the backend running?)`);
    const data = JSON.parse(text);
    pushLog({ request_id, url, method, status: res.status, duration: Date.now() - start, response: data });
    return data as T | ApiError;
  } catch (err) {
    const error: ApiError = {
      error: { code: "NETWORK_ERROR", message: String(err), request_id, detail: err },
    };
    pushLog({ request_id, url, method, status: 0, duration: Date.now() - start, response: error });
    return error;
  }
}

function pushLog(entry: RequestLogEntry) {
  requestLog.unshift(entry);
  if (requestLog.length > 50) requestLog.pop();
}

export function getRequestLog(): RequestLogEntry[] { return requestLog; }

export function isApiError(x: unknown): x is ApiError {
  return typeof x === "object" && x !== null && "error" in x;
}
