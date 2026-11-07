// SCAFFOLD: live agent tree from the event stream. TODO(#fe-workspace): lead/specialist layout, panels, gate strip, badges, replay controls.
import { useState } from "react";
import { api } from "../lib/api";
import { subscribeRun } from "../lib/sse";
import type { AgentEvent } from "../lib/types";

export default function Workspace() {
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const start = async () => {
    setEvents([]);
    const { run_id } = await api.build();
    subscribeRun(run_id, (e) => setEvents((prev) => [...prev, e]));
  };
  const agents = events.filter((e) => e.type === "agent.spawned" || e.type === "agent.spawn_denied");
  return (
    <div className="grid grid-cols-2 gap-6">
      <div>
        <button className="rounded bg-emerald-600 px-4 py-2 mb-4" onClick={start}>Build my portfolio</button>
        <h2 className="text-sm text-slate-400 mb-2">Agent tree</h2>
        <ul className="space-y-1 text-sm">
          {agents.map((e) => (
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
