import { useEffect, useState } from "react";

export function useResource<T>(key: string, load: (signal: AbortSignal) => Promise<T>) {
  const [state, setState] = useState<{ key: string; value?: T; error?: string }>({ key: "" });
  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal).then(value => {
      if (!controller.signal.aborted) setState({ key, value });
    }).catch((error: Error) => {
      if (!controller.signal.aborted) setState({ key, error: error.message });
    });
    return () => controller.abort();
    // The key identifies the request and all its inputs.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return state.key === key ? state : { key };
}
