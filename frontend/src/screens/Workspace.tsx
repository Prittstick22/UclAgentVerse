// SCAFFOLD: live agent tree from the event stream. TODO(#fe-workspace): lead/specialist layout, panels, gate strip, badges, replay controls.
import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { subscribeRun } from "../lib/sse";
import type { AgentEvent, RunSummary } from "../lib/types";

export default function Workspace() {
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [runId, setRunId] = useState<string | null>(null);
  const [summary, setSummary] = useState<RunSummary | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!runId) return;
    let active = true;
    const stop = subscribeRun(runId, (event) => {
      setEvents((prev) => [...prev, event]);
      if (event.type !== "run.completed") return;
      stop();
      api.runDetail(runId)
        .then((detail) => { if (active) setSummary(detail); })
        .catch((error: Error) => { if (active) setError(error.message); })
        .finally(() => { if (active) setBusy(false); });
    });
    return () => { active = false; stop(); };
  }, [runId]);

  const start = async () => {
    setRunId(null);
    setEvents([]);
    setSummary(null);
    setError(null);
    setBusy(true);
    try {
      const { run_id } = await api.build();
      setRunId(run_id);
    } catch (error) {
      setError(error instanceof Error ? error.message : "Could not start the run");
      setBusy(false);
    }
  };
  const agents = events.filter((e) => e.type === "agent.spawned" || e.type === "agent.spawn_denied");
  return (
    <div className="grid grid-cols-2 gap-6">
      <div>
        <button className="rounded bg-emerald-600 px-4 py-2 mb-4" onClick={start} disabled={busy}>Build my portfolio</button>
        {error && <p role="alert" className="text-sm text-rose-400 mb-2">{error}</p>}
        <h2 className="text-sm text-slate-400 mb-2">Agent tree</h2>
        <ul className="space-y-1 text-sm">
          {summary ? summary.agents.map((agent) => (
            <li key={agent.agent_id} style={{ paddingLeft: `${agent.depth * 20}px` }}
              className={agent.status === "denied" || agent.status === "failed" ? "text-rose-400" : ""}>
              {agent.role.replaceAll("_", " ")} · {agent.status}
              {agent.badges.length > 0 && ` · ${agent.badges.map((badge) => badge.replaceAll("_", " ")).join(", ")}`}
            </li>
          )) : agents.map((e) => (
            <li key={e.id} style={{ paddingLeft: `${(e.depth ?? 0) * 20}px` }}
              className={e.type === "agent.spawn_denied" ? "text-rose-400" : ""}>
              {e.type === "agent.spawn_denied" ? "⛔ " : "● "}{e.title}
            </li>
          ))}
        </ul>
      </div>
      <div>
        <h2 className="text-sm text-slate-400 mb-2">Event log</h2>
        <ol className="space-y-1 text-xs font-mono max-h-[70vh] overflow-auto">
          {events.map((e) => <li key={e.id}><span className="text-slate-500">{e.type}</span> {e.title}</li>)}
        </ol>
      </div>
    </div>
  );
}
