import { getRequestLog } from "../api/client";

interface Props {
  reason:      string;
  suggestion?: string;
  config?:     unknown;
}

// Never dismissible. Always explains why and suggests a fix.
// Invalid configs are also pushed to DebugPanel as [PLATFORM GAP] entries.
export default function WarningPlaceholder({ reason, suggestion, config }: Props) {
  // Log to request log ring buffer as a platform gap event
  const log = getRequestLog();
  const alreadyLogged = log.some(e => e.url === `[PLATFORM GAP] ${reason}`);
  if (!alreadyLogged && config !== undefined) {
    // Inject directly — apiFetch is for real requests; platform gaps use this slot
    log.unshift({
      request_id: crypto.randomUUID().slice(0, 8),
      url:        `[PLATFORM GAP] ${reason}`,
      method:     "WARN",
      status:     0,
      duration:   0,
      response:   config,
    });
  }

  return (
    <div className="warning-placeholder">
      <div className="warning-placeholder-header">
        <span className="material-symbols-rounded">warning</span>
        <span>Configuration warning</span>
      </div>
      <p className="warning-placeholder-reason type-body">{reason}</p>
      {suggestion && (
        <p className="warning-placeholder-suggestion type-label">{suggestion}</p>
      )}
    </div>
  );
}
