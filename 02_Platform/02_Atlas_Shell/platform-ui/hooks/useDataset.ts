// src/hooks/useDataset.ts — standard data fetching hook
// Extends Blueprint §4 with a refresh() callback for post-mutation reloads.

import { useState, useEffect, useCallback } from "react";
import type { Dataset, ApiError } from "../api/types";
import { apiFetch, isApiError } from "../api/client";

export function useDataset(path: string, params?: Record<string, string>) {
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [error,   setError]   = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    setLoading(true);
    setError(null);
    const query = params ? "?" + new URLSearchParams(params) : "";
    apiFetch<Dataset>(`${path}${query}`).then(res => {
      if (isApiError(res)) setError(res);
      else setDataset(res);
      setLoading(false);
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, JSON.stringify(params), version]);

  const refresh = useCallback(() => setVersion(v => v + 1), []);

  return { dataset, error, loading, refresh };
}
