/**
 * Freeze diagnostics for the Workout app. While installed it reports browser stalls to the backend
 * log (POST /api/workout/client-perf) so a "the app froze for a few seconds" report can be matched
 * to a cause:
 *   longtask   main thread blocked ≥ LONGTASK_MS (JS/render work on the phone)
 *   gap        a 250 ms heartbeat arrived ≥ GAP_MS late while the page was visible (blocked or throttled)
 *   slow_fetch a request took ≥ SLOW_FETCH_MS as seen by the browser (compare with server duration_ms)
 * Diagnostic only: failures are swallowed and nothing is stored on the device.
 */

const LONGTASK_MS = 200;
const GAP_MS = 1000;
const SLOW_FETCH_MS = 1500;
const HEARTBEAT_MS = 250;
const FLUSH_MS = 5000;
const PERF_URL = "/api/workout/client-perf";

interface PerfEvent {
  kind: "longtask" | "gap" | "slow_fetch";
  ms: number;
  path: string;
  last_action: string;
  detail: string;
}

export function installFreezeLog(): () => void {
  const queue: PerfEvent[] = [];
  let lastAction = "";
  let lastActionAt = 0;
  let hiddenSince = 0; // last time the page was hidden or resumed; gaps right after are not freezes

  const push = (kind: PerfEvent["kind"], ms: number, detail = "") => {
    if (queue.length >= 20) return;
    const age = lastAction ? ` (${Math.round((Date.now() - lastActionAt) / 1000)}s before)` : "";
    queue.push({
      kind,
      ms: Math.round(ms),
      path: location.pathname,
      last_action: (lastAction + age).slice(0, 120),
      detail: detail.slice(0, 200),
    });
  };

  const flush = () => {
    if (!queue.length) return;
    const body = JSON.stringify(queue.splice(0, queue.length));
    try {
      // Raw fetch (not the wrapped one) with keepalive; errors are irrelevant here.
      void rawFetch(PERF_URL, { method: "POST", headers: { "Content-Type": "application/json" }, body, keepalive: true }).catch(() => {});
    } catch {
      /* diagnostics must never break the app */
    }
  };

  const onAction = (ev: Event) => {
    const el = ev.target instanceof Element ? ev.target.closest("button,a,[role=button],input,textarea,select") ?? ev.target : null;
    const label = el instanceof HTMLElement ? (el.getAttribute("aria-label") ?? el.innerText ?? "").trim().replace(/\s+/g, " ").slice(0, 40) : "";
    lastAction = `${ev.type} ${el instanceof Element ? el.tagName.toLowerCase() : "?"}${label ? ` "${label}"` : ""}`;
    lastActionAt = Date.now();
  };
  document.addEventListener("pointerdown", onAction, true);
  document.addEventListener("keydown", onAction, true);

  let observer: PerformanceObserver | null = null;
  try {
    observer = new PerformanceObserver((list) => {
      for (const e of list.getEntries()) if (e.duration >= LONGTASK_MS) push("longtask", e.duration);
    });
    observer.observe({ type: "longtask", buffered: false });
  } catch {
    observer = null; // longtask unsupported in this webview; the heartbeat still covers it
  }

  let last = performance.now();
  const onVisibility = () => {
    hiddenSince = performance.now();
    last = hiddenSince;
  };
  document.addEventListener("visibilitychange", onVisibility);
  const heartbeat = setInterval(() => {
    const now = performance.now();
    const gap = now - last - HEARTBEAT_MS;
    last = now;
    if (document.visibilityState === "visible" && now - hiddenSince > 2000 && gap >= GAP_MS) push("gap", gap);
  }, HEARTBEAT_MS);

  const rawFetch = window.fetch.bind(window);
  const wrapped: typeof window.fetch = async (input, init) => {
    const t0 = performance.now();
    try {
      return await rawFetch(input, init);
    } finally {
      const ms = performance.now() - t0;
      const url = typeof input === "string" ? input : input instanceof URL ? input.pathname : input.url;
      if (ms >= SLOW_FETCH_MS && !url.includes(PERF_URL)) push("slow_fetch", ms, `${init?.method ?? "GET"} ${url.split("?")[0]}`);
    }
  };
  window.fetch = wrapped;

  const flusher = setInterval(flush, FLUSH_MS);
  document.addEventListener("visibilitychange", flush);

  return () => {
    flush();
    clearInterval(heartbeat);
    clearInterval(flusher);
    observer?.disconnect();
    document.removeEventListener("pointerdown", onAction, true);
    document.removeEventListener("keydown", onAction, true);
    document.removeEventListener("visibilitychange", onVisibility);
    document.removeEventListener("visibilitychange", flush);
    if (window.fetch === wrapped) window.fetch = rawFetch;
  };
}
