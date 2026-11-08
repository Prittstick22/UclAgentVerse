import { useCallback, useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, Route, Routes } from "react-router-dom";
import { DemoPasscodeDialog, ShellIcon, TerminalBrand } from "./components/TerminalShellUi";
import { api, attachApiFeedback, MOCK } from "./lib/api";
import type { ApiError } from "./lib/api";
import type { Health, Mode } from "./lib/types";
import Quiz from "./screens/Quiz";
import Workspace from "./screens/Workspace";
import Home from "./screens/Home";
import Placeholder from "./screens/Placeholder";
import dataSourcesUrl from "../../docs/DATA_SOURCES.md?url";

const NAV = [
  [["/", "Home", "home"], ["/quiz", "Quiz", "quiz"], ["/timeline", "Timeline", "timeline"],
    ["/benchmarks", "Benchmarks", "chart"]],
  [["/workspace", "Agents", "agents"], ["/decisions", "Decisions", "decisions"], ["/chat", "Chat", "chat"]],
] as const;

const statusDate = new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeZone: "UTC" });

function modeLabel(health: Health | null, pending: boolean): string {
  if (!health) return pending ? "Loading market mode" : "Market mode unavailable";
  if (health.mode === "live") return "Current markets · Paper portfolio";
  const date = new Date(health.as_of);
  return `Historical demo · As of ${Number.isNaN(date.getTime()) ? health.as_of : statusDate.format(date)}`;
}

interface PendingPasscode {
  previousRejected: boolean;
  resolve: (passcode: string | null) => void;
}

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [healthPending, setHealthPending] = useState(true);
  const [changing, setChanging] = useState(false);
  const [modeVersion, setModeVersion] = useState(0);
  const [error, setError] = useState<ApiError | null>(null);
  const [prompt, setPrompt] = useState<PendingPasscode | null>(null);
  const pendingPasscode = useRef<PendingPasscode | null>(null);
  const showClock = useCallback((as_of: string) => {
    setHealth((previous) => previous && { ...previous, as_of });
  }, []);

  useEffect(() => {
    const detach = attachApiFeedback({
      showError: setError,
      requestPasscode: (previousRejected) => new Promise((resolve) => {
        const pending = { previousRejected, resolve };
        pendingPasscode.current = pending;
        setPrompt(pending);
      }),
    });
    return () => {
      detach();
      pendingPasscode.current?.resolve(null);
      pendingPasscode.current = null;
    };
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    api.health(controller.signal)
      .then(setHealth)
      .catch(() => { if (!controller.signal.aborted) setHealth(null); })
      .finally(() => { if (!controller.signal.aborted) setHealthPending(false); });
    return () => controller.abort();
  }, []);

  function finishPasscode(value: string | null) {
    pendingPasscode.current?.resolve(value);
    pendingPasscode.current = null;
    setPrompt(null);
  }

  async function changeMode(mode: Mode) {
    setChanging(true);
    setError(null);
    try {
      const next = await api.setMode(mode);
      setHealth((previous) => previous && { ...previous, mode: next.mode, as_of: next.as_of, data_source: "" });
      setModeVersion((version) => version + 1);
      setHealth(await api.health());
    } catch {
      // The API client has already reported the structured error to the shell.
    } finally {
      setChanging(false);
    }
  }

  return (
    <div className="terminal-shell">
      <aside className="terminal-sidebar terminal-glass">
        <Link to="/" className="terminal-brand" aria-label="UclAgentVerse Home" title="UclAgentVerse">
          <TerminalBrand />
        </Link>
        <nav aria-label="Main navigation">
          {NAV.map((group, index) => (
            <div className="terminal-nav-group" key={group[0][0]}>
              {index > 0 && <div className="terminal-nav-divider" />}
              {group.map(([to, title, icon]) => (
                <NavLink key={to} to={to} end className="terminal-nav-item" title={title}>
                  <ShellIcon name={icon} />
                  <span>{title}</span>
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
      </aside>

      <main key={modeVersion} className="terminal-main">
        <Routes>
          <Route path="/" element={<Home onClockChange={showClock} />} />
          <Route element={<section className="terminal-page terminal-glass"><Outlet /></section>}>
            <Route path="/quiz" element={
              <>
                <h1>Investor profile</h1>
                <div className="terminal-mode-choice">
                  <label htmlFor="market-mode">Market mode</label>
                  <select id="market-mode" className="terminal-field" value={health?.mode ?? "historical"}
                    disabled={changing || MOCK || !health}
                    onChange={(event) => { void changeMode(event.target.value as Mode); }}>
                    <option value="historical">Historical demo</option>
                    <option value="live">Current markets</option>
                  </select>
                  {MOCK && <span>Fixture preview uses historical mode.</span>}
                </div>
                <Quiz />
              </>
            } />
            <Route path="/workspace" element={<><h1>Agents</h1><Workspace /></>} />
            <Route path="/timeline" element={<Placeholder title="Timeline" issue="fe-timeline" />} />
            <Route path="/decisions" element={<Placeholder title="Decision cards" issue="fe-decision-card" />} />
            <Route path="/benchmarks" element={<Placeholder title="Benchmarks" issue="fe-benchmarks" />} />
            <Route path="/chat" element={<Placeholder title="Chat" issue="fe-chat" />} />
            <Route path="*" element={<><h1>Page not found</h1><Link to="/">Return home</Link></>} />
          </Route>
        </Routes>
      </main>

      <footer className="terminal-status">
        <span className="terminal-status-chip"><ShellIcon name="wallet" />Paper portfolio</span>
        <span>Not financial advice</span>
        <a href={dataSourcesUrl} download="DATA_SOURCES.md">Data sources</a>
        <span className="terminal-mode-badge" aria-live="polite">
          <ShellIcon name="clock" />{modeLabel(health, healthPending)}
        </span>
        {health?.data_source && (
          <span className="terminal-source">{health.data_source === "synthetic" ? "SYNTHETIC data" : health.data_source}</span>
        )}
        {MOCK && <span>Mock</span>}
        <strong>UclAgentVerse</strong>
      </footer>

      {error && (
        <div className="terminal-toast terminal-glass">
          <div role="alert">
            <strong>{error.code === "network_error" ? "Connection problem" : "Request failed"}</strong>
            <p>{error.message}</p>
          </div>
          <button type="button" aria-label="Dismiss error" onClick={() => setError(null)}><ShellIcon name="close" /></button>
        </div>
      )}
      {prompt && <DemoPasscodeDialog previousRejected={prompt.previousRejected} finish={finishPasscode} />}
    </div>
  );
}
