import { useCallback, useEffect, useRef, useState } from "react";
import { Link, Navigate, NavLink, Outlet, Route, Routes, useLocation } from "react-router-dom";
import { DemoPasscodeDialog, ShellIcon, TerminalBrand } from "./components/TerminalShellUi";
import { api, attachApiFeedback, MOCK } from "./lib/api";
import type { ApiError } from "./lib/api";
import type { Health, Mode } from "./lib/types";
import Quiz, { ProfileScreen } from "./screens/Quiz";
import Workspace from "./screens/Workspace";
import TimelineScreen, { BenchmarkScreen } from "./screens/Timeline";
import { DecisionList } from "./screens/Decisions";
import Home from "./screens/Home";
import Placeholder from "./screens/Placeholder";
import dataSourcesUrl from "../../docs/DATA_SOURCES.md?url";

const NAV = [
  ["/", "Home", "home"], ["/workspace", "Agents", "agents"], ["/timeline", "Timeline", "timeline"],
  ["/benchmarks", "Benchmarks", "chart"], ["/profile", "Profile", "quiz"],
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
  const [setupComplete, setSetupComplete] = useState(() => localStorage.getItem("ucl-paper-setup") === "1");
  const location = useLocation();
  const setup = !setupComplete && (location.pathname === "/" || location.pathname === "/onboarding");
  function finishSetup() {
    localStorage.setItem("ucl-paper-setup", "1");
    setSetupComplete(true);
  }
  const marketMode = <span className="terminal-mode-badge" aria-live="polite">
    <ShellIcon name="clock" />{modeLabel(health, healthPending)}
  </span>;
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
    if (!health) return false;
    if (mode === health.mode) return true;
    if (MOCK) {
      setHealth({ ...health, mode });
      setModeVersion(version => version + 1);
      return true;
    }
    setChanging(true);
    setError(null);
    try {
      const next = await api.setMode(mode);
      setHealth((previous) => previous && { ...previous, mode: next.mode, as_of: next.as_of, data_source: "" });
      setModeVersion((version) => version + 1);
      void api.health().then(setHealth).catch(() => {});
      return true;
    } catch {
      return false;
    } finally {
      setChanging(false);
    }
  }

  return (
    <div className={`terminal-shell${setup ? " terminal-setup" : ""}`}>
      {!setup && <header className="terminal-topbar terminal-glass">
        <Link to="/" className="terminal-brand" aria-label="UclAgentVerse Home" title="UclAgentVerse">
          <TerminalBrand />
        </Link>
        <nav aria-label="Main navigation">
          {NAV.map(([to, title, icon]) => (
            <NavLink key={to} to={to} end className="terminal-nav-item" title={title} aria-current={to === "/workspace" && location.pathname.startsWith("/runs/") ? "page" : undefined}>
              <ShellIcon name={icon} /><span>{title}</span>
            </NavLink>
          ))}
        </nav>
        {marketMode}
        <NavLink to="/decisions" end className="terminal-nav-item terminal-bell" title="Decisions and notifications" aria-label="Decisions and notifications"><ShellIcon name="bell" /></NavLink>
      </header>}

      <main className="terminal-main">
        <Routes>
          <Route path="/" element={setupComplete ? <Home key={modeVersion} onClockChange={showClock} /> : <Navigate replace to="/onboarding" />} />
          <Route path="/runs/:runId" element={<section className="terminal-room-page terminal-glass"><Workspace mode={health?.mode} /></section>} />
          <Route element={<section className="terminal-page terminal-glass"><Outlet /></section>}>
            <Route path="/onboarding" element={<Quiz mode={health?.mode} changing={changing} onMode={changeMode} complete={finishSetup} />} />
            <Route path="/quiz" element={<Navigate replace to="/onboarding" />} />
            <Route path="/profile" element={<ProfileScreen mode={health?.mode} />} />
            <Route path="/workspace" element={<Workspace mode={health?.mode} />} />
            <Route path="/timeline" element={<TimelineScreen />} />
            <Route path="/decisions" element={<DecisionList mode={health?.mode} />} />
            <Route path="/benchmarks" element={<BenchmarkScreen />} />
            <Route path="*" element={<><h1>Page not found</h1><Link to="/">Return home</Link></>} />
          </Route>
        </Routes>
      </main>

      <footer className="terminal-status">
        <span className="terminal-status-chip"><ShellIcon name="wallet" />Paper portfolio</span>
        <span>Not financial advice</span>
        <a href={dataSourcesUrl} download="DATA_SOURCES.md">Data sources</a>
        {setup && marketMode}
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
