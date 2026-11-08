import { useEffect, useState } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import { api, MOCK } from "./lib/api";
import type { Health, Mode } from "./lib/types";
import Quiz from "./screens/Quiz";
import Workspace from "./screens/Workspace";
import Home from "./screens/Home";
import Placeholder from "./screens/Placeholder";
import dataSourcesUrl from "../../docs/DATA_SOURCES.md?url";

const NAV = [
  ["/", "Home"], ["/quiz", "Quiz"], ["/workspace", "Agents"], ["/timeline", "Timeline"],
  ["/decisions", "Decisions"], ["/benchmarks", "Benchmarks"], ["/chat", "Chat"],
] as const;

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [changing, setChanging] = useState(false);
  const [modeError, setModeError] = useState("");
  const [modeVersion, setModeVersion] = useState(0);
  async function changeMode(mode: Mode) {
    setChanging(true);
    setModeError("");
    try {
      await api.setMode(mode);
      setHealth(await api.health());
      setModeVersion((version) => version + 1);
    } catch {
      setModeError("Could not change mode. Please try again.");
    } finally {
      setChanging(false);
    }
  }
  useEffect(() => { api.health().then(setHealth).catch(() => setHealth(null)); }, []);
  const label = health?.mode === "live" ? "Current markets · Paper portfolio" : `Historical demo · As of ${health?.as_of ?? "…"}`;
  return (
    <div className="min-h-screen flex flex-col">
      <header className="flex items-center gap-6 px-6 py-3 border-b border-slate-800">
        <span className="font-semibold">UclAgentVerse</span>
        <nav className="flex gap-4 text-sm">
          {NAV.map(([to, name]) => (
            <NavLink key={to} to={to} end className={({ isActive }) => (isActive ? "text-white" : "text-slate-400 hover:text-slate-200")}>{name}</NavLink>
          ))}
        </nav>
        <span className="ml-auto rounded bg-slate-800 px-2 py-1 text-xs">{label}{MOCK && " · MOCK"}</span>
        <select aria-label="Market mode" className="bg-slate-800 rounded px-2 py-1 text-sm"
          value={health?.mode ?? "historical"} disabled={changing || MOCK || !health}
          onChange={(event) => { void changeMode(event.target.value as Mode); }}>
          <option value="historical">Historical demo</option>
          <option value="live">Current markets</option>
        </select>
      </header>
      {modeError && <p role="alert" className="px-6 text-red-300">{modeError}</p>}
      <main key={modeVersion} className="flex-1 p-6">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/quiz" element={<Quiz />} />
          <Route path="/workspace" element={<Workspace />} />
          <Route path="/timeline" element={<Placeholder title="Timeline" issue="fe-timeline" />} />
          <Route path="/decisions" element={<Placeholder title="Decision cards" issue="fe-decision-card" />} />
          <Route path="/benchmarks" element={<Placeholder title="Benchmarks" issue="fe-benchmarks" />} />
          <Route path="/chat" element={<Placeholder title="Chat" issue="fe-chat" />} />
        </Routes>
      </main>
      <footer className="px-6 py-2 text-xs text-slate-500 border-t border-slate-800">
        Paper portfolio · Not financial advice · {health?.data_source === "synthetic" ? "SYNTHETIC data" : health?.data_source}
        {" · "}<a className="underline hover:text-slate-300" href={dataSourcesUrl} download="DATA_SOURCES.md">Data sources</a>
      </footer>
    </div>
  );
}
