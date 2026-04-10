import { useState } from "react";
import type { ApiError } from "../api/types";

interface Props {
  error: ApiError;
}

export default function ErrorCard({ error }: Props) {
  const [detailOpen, setDetailOpen] = useState(false);
  const { code, message, detail, request_id } = error.error;

  return (
    <div className="error-card">
      <div className="error-card-header">
        <span className="material-symbols-rounded">error</span>
        <span className="error-card-message type-body">{message}</span>
      </div>

      <div className="error-card-meta type-label">
        code: {code} &nbsp;·&nbsp; request_id: {request_id}
      </div>

      {detail !== undefined && (
        <>
          <button
            className="btn-text"
            style={{ alignSelf: "flex-start", padding: "0" }}
            onClick={() => setDetailOpen(o => !o)}
          >
            {detailOpen ? "Hide detail" : "Show detail"}
          </button>
          {detailOpen && (
            <pre className="error-card-detail">
              {JSON.stringify(detail, null, 2)}
            </pre>
          )}
        </>
      )}
    </div>
  );
}
