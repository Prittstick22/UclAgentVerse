import { useEffect, useState } from "react";
import { subscribeRun } from "./sse";
import type { AgentEvent } from "./types";

export function useRunEvents(runId: string, enabled: boolean) {
  const [events, setEvents] = useState<AgentEvent[]>([]);
  useEffect(() => {
    if (enabled) return subscribeRun(runId, event =>
      setEvents(previous => previous.some(item => item.id === event.id) ? previous : [...previous, event]));
  }, [runId, enabled]);
  return events;
}
