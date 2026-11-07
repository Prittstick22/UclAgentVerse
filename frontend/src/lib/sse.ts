// Subscribe to a run's event stream. In mock mode, replays fixtures with a small delay so the tree "grows".
import { MOCK, mockEvents } from "./api";
import type { AgentEvent } from "./types";

export function subscribeRun(runId: string, onEvent: (e: AgentEvent) => void): () => void {
  if (MOCK) {
    const evs = mockEvents();
    let i = 0;
    const t = setInterval(() => (i < evs.length ? onEvent(evs[i++]) : clearInterval(t)), 120);
    return () => clearInterval(t);
  }
  const es = new EventSource(`/api/runs/${runId}/events`);
  es.onmessage = (m) => onEvent(JSON.parse(m.data));
  // backend sends named events (event: <type>); listen to all known ones via a generic handler
  const handler = (m: MessageEvent) => onEvent(JSON.parse(m.data));
  ["run.started", "run.completed", "agent.spawned", "agent.spawn_denied", "agent.status", "agent.message", "tool.call",
    "tool.result", "finding", "decision.made", "gate.verdict", "content.quarantined", "proposal.created", "calc.result"]
    .forEach((t) => es.addEventListener(t, handler as EventListener));
  return () => es.close();
}
