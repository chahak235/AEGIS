// A small hook for "load data from the API and show loading / error / result".
// Every page needs exactly this, so it lives in one place.

import { useCallback, useEffect, useRef, useState } from "react";

export interface AsyncState<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  reload: () => void;
}

export function useAsync<T>(load: () => Promise<T>, deps: unknown[]): AsyncState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);
  const latest = useRef(0);

  useEffect(() => {
    const call = ++latest.current; // ignore answers to old requests (e.g. filters changed quickly)
    setLoading(true);
    setError(null);
    load()
      .then((result) => { if (call === latest.current) setData(result); })
      .catch((e: Error) => { if (call === latest.current) setError(e.message); })
      .finally(() => { if (call === latest.current) setLoading(false); });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { data, error, loading, reload };
}
