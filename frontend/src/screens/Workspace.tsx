import { useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import AgentAvatar from "../components/AgentAvatar";
import { api, get, mockEvents, MOCK } from "../lib/api";
import { useRunEvents } from "../lib/useRunEvents";
import type { AgentEvent, CorrelationReport, Mode, RunSummary } from "../lib/types";
import { useResource } from "../lib/useResource";
import { EvidenceView, gbp, pct, ProposalDialog, words } from "./Decisions";

const route = (id: string) => "/runs/" + encodeURIComponent(id);
type RunItem = Omit<RunSummary, "agents">;

function RunPicker({ mode }: { mode?: Mode }) {
  const runs = useResource("runs:" + mode, signal => get<{ items: RunItem[] }>("/runs?limit=100", "runs", signal));
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function start() {
    setBusy(true);
    setError("");
    try { const { run_id } = await api.build(); navigate(route(run_id) + "?live=1"); }
    catch (e) { setError((e as Error).message); setBusy(false); }
  }
  return <div className="mvp-page mvp-enter">
    <div className="mvp-toolbar"><h1>Agent workspace</h1>
      {mode === "live" && <button className="mvp-action primary" disabled={busy} onClick={() => void start()}>Build my portfolio</button>}</div>
    <p className="mvp-muted">Watch the lead and specialists work through an investigation.</p>
    {error && <p role="alert">{error}</p>}
    <section className="terminal-glass mvp-panel">
      <h2>Investigations</h2>
      {runs.error && <p role="alert">{runs.error}</p>}
      {runs.value?.items.slice().reverse().map(run => <Link key={run.run_id} to={route(run.run_id) + (run.status === "running" ? "?live=1" : "")} className="run-row">
        <span>{run.trigger_text || words(run.kind)}</span><time>{run.as_of}</time><span>{words(run.outcome ?? run.status)} ›</span>
      </Link>)}
      {!runs.value?.items.length && !runs.error && <p>{runs.value ? "No investigations recorded yet." : "Loading investigations…"}</p>}
    </section>
  </div>;
}

export default function Workspace({ mode }: { mode?: Mode }) {
  const { runId } = useParams();
  return runId ? <RunRoom key={runId} id={runId} mode={mode} /> : <RunPicker mode={mode} />;
}

function RunRoom({ id, mode }: { id: string; mode?: Mode }) {
  const [params] = useSearchParams();
  const live = params.get("live") === "1" && mode === "live" && !MOCK;
  const archive = useResource(id + live, signal => live ? Promise.resolve(null) :
    MOCK ? Promise.resolve({ items: mockEvents() }) :
      get<{ items: AgentEvent[] }>(route(id) + "/events?format=json", "", signal));
  const stream = useRunEvents(id, live);
  const [cursor, setCursor] = useState<number | null>(null);
  const [playing, setPlaying] = useState(!params.has("seq") && !live);
  const [speed, setSpeed] = useState(1);
  const [focused, setFocused] = useState("");
  const [source, setSource] = useState("");
  const [proposalOpen, setProposalOpen] = useState(false);
  const [resolved, setResolved] = useState(false);
  const initialSeq = Number(params.get("seq"));
  const events = live ? stream : archive.value?.items ?? [];
  const initialIndex = initialSeq > 0 ? events.findIndex(event => event.seq >= initialSeq) : 0;
  const index = Math.min(events.length - 1, live ? events.length - 1 : cursor ?? Math.max(0, initialIndex));
  const visible = events.slice(0, index + 1);
  const active = visible.at(-1);
  const agents = visible.filter(event => event.type === "agent.spawned" && event.agent_id);
  const selected = agents.find(agent => agent.agent_id === focused);
  const working = agents.find(agent => agent.agent_id === active?.agent_id);
  const stage = working && agents.indexOf(working) >= 3 ? [...agents.slice(0, 2), working] : agents.slice(0, 3);
  const panels = selected ? [selected] : stage;
  const proposal = visible.slice().reverse().find(event => event.type === "proposal.created");
  const proposalId = typeof proposal?.payload.proposal_id === "string" ? proposal.payload.proposal_id : "";
  const nextFinding = events.findIndex((event, i) => i > index && event.type === "finding");
  const finished = visible.some(event => event.type === "run.completed");

  useEffect(() => {
    if (!live && playing && index >= 0 && index < events.length - 1) {
      const delay = window.setTimeout(() => setCursor(index + 1), 540 / speed);
      return () => window.clearTimeout(delay);
    }
  }, [events.length, index, live, playing, speed]);

  function jump(next: number) {
    setCursor(Math.max(0, Math.min(events.length - 1, next)));
    setPlaying(false);
    setSource("");
  }

  return <div className="agent-room mvp-enter">
    <div className="agent-room-body">
    <aside className="agent-room-side terminal-glass">
      <header><h1>Agent workspace</h1><Link to="/workspace" aria-label="Back to investigations">←</Link></header>
      <div className="agent-room-brief"><strong>{visible[0]?.trigger_text || "Investigation"}</strong>
        <p>{active?.as_of ?? ""} · {live ? finished ? "Run complete" : "Live investigation" : "Recorded investigation"}</p></div>
      <div className="agent-room-brief mvp-muted">Participants ({agents.length})</div>
      {agents.map(agent => <button className="agent-participant" key={agent.id} aria-pressed={focused === agent.agent_id}
        onClick={() => setFocused(focused === agent.agent_id ? "" : agent.agent_id ?? "")}>
        <AgentAvatar role={agent.role ?? ""} /><span>{words(agent.role ?? "Specialist")}</span>
        <small>{agent.agent_id === active?.agent_id && !finished ? "Current" : finished ? "Recorded" : "In room"}</small>
      </button>)}
    </aside>
    <div className="agent-room-center">
    {archive.error && <p role="alert">{archive.error}</p>}
    {!agents.length && <section className="terminal-glass mvp-panel agent-opening"><AgentAvatar role="lead" /><h2>Lead agent</h2>
      <p>{active?.trigger_text || active?.title || (archive.value ? "No recorded events for this run." : "Waiting for investigation events…")}</p></section>}
    <div className="agent-stage" data-count={panels.length}>
      {panels.map(agent => {
        const activity = visible.filter(event => event.agent_id === agent.agent_id ||
          (agent.role === "lead" && event.agent_id == null && event.type === "calc.result"));
        const current = activity.at(-1);
        const work = activity.slice().reverse().find(event => ["calc.result", "finding", "tool.result", "agent.message", "source.inspect"].includes(event.type));
        const visual = activity.slice().reverse().find(event => event.type === "calc.result" &&
          (current?.type === "calc.result" || (current?.type === "tool.result" && event.seq + 1 === current.seq)));
        const parent = agents.find(item => item.agent_id === agent.parent_agent_id);
        const delegated = agents.filter(item => item.parent_agent_id === agent.agent_id);
        const status = current?.type === "tool.call" ? "Tool running" : current?.payload.status ?? (finished ? "done" : "working");
        return <section className="terminal-glass agent-tile mvp-enter" key={agent.id}>
          <header><AgentAvatar role={agent.role ?? "lead"} /><div><h2>{words(agent.role === "lead" ? "Lead agent" : agent.role ?? "Agent")}</h2>
            <p>{parent ? "Delegated by " + words(parent.role ?? "lead") : "Coordinates the investigation"}</p></div>
            <button className="mvp-action" onClick={() => setFocused(focused ? "" : agent.agent_id ?? "")}>{focused ? "Show team" : "Expand"}</button></header>
          <div className="agent-tile-work">
            <p className="mvp-muted">{agent.purpose || String(agent.payload.question ?? "")}</p>
            <h3>{current?.type === "tool.call" ? current.title : work?.title ?? current?.title ?? "Preparing"}</h3>
            {current?.type === "tool.call" && <div className="agent-tool" role="status">
              <span />{typeof current.payload.tool === "string" ? words(current.payload.tool) : "Tool request"}
              <small>Waiting for output</small>
            </div>}
            {visual && <>{visual.agent_id == null && <p className="mvp-muted">Engine calculation</p>}
              <AgentVisual key={visual.id} event={visual} /></>}
            {!MOCK && work?.type === "source.inspect" && work.evidence_ids[0] && <EvidenceView key={work.id} id={work.evidence_ids[0]} />}
            {delegated.length > 0 && <div className="agent-delegation" aria-label="Delegated work">{delegated.map(child =>
              <button className="mvp-action" key={child.id} onClick={() => setFocused(child.agent_id ?? "")}>
                <AgentAvatar role={child.role ?? ""} />
                <span><b>{words(child.role ?? "Specialist")}</b><small>{child.purpose}</small></span>
              </button>)}</div>}
            {work?.evidence_ids.map(id => <button key={id} className="mvp-link" onClick={() => setSource(id)}>Inspect evidence</button>)}
            {focused && <ol className="agent-events">{activity.map(event =>
              <li key={event.id}><button disabled={live} onClick={() => jump(events.indexOf(event))}>{event.seq} · {event.title}</button></li>)}</ol>}
          </div>
          <footer>{typeof status === "string" ? words(status) : "Working"}</footer>
        </section>;
      })}
    </div>
    {visible.filter(event => event.type === "agent.spawn_denied").map(event =>
      <p className="agent-refused" key={event.id}>{event.title}{event.purpose && " · " + event.purpose}</p>)}
    {proposalId && <div className="proposal-nudge terminal-glass"><strong>{resolved ? "Decision recorded" : proposal?.title}</strong>
      <button className="mvp-action primary" onClick={() => { setPlaying(false); setProposalOpen(true); }}>Review proposal</button></div>}
    {source && <section className="mvp-panel terminal-glass"><button className="mvp-action" onClick={() => setSource("")}>Close evidence</button><EvidenceView key={source} id={source} /></section>}
    </div>
    <aside className="agent-room-side terminal-glass agent-room-activity">
      <header><h2>Investigation activity</h2></header>
      {active && <div className="agent-room-brief"><small>Current step · {active.seq}</small><strong>{active.title}</strong>
        {active.evidence_ids.map(id => <button key={id} className="mvp-link" onClick={() => setSource(id)}>Open source</button>)}
        <details className="agent-terminal"><summary>Inspect payload</summary><pre>{JSON.stringify(active.payload, null, 2)}</pre></details>
      </div>}
      <ol className="agent-event-list">{visible.slice().reverse().map(event =>
        <li key={event.id}><button disabled={live} aria-current={event.id === active?.id ? "step" : undefined}
          onClick={() => jump(events.indexOf(event))}><b>{event.title}</b><small>{words(event.role ?? event.type)} · {event.seq}</small></button></li>)}</ol>
      <details className="agent-terminal"><summary>Execution log</summary>
        <ol className="agent-events">{visible.map(event => <li key={event.id}>{event.seq} · {event.type} · {event.title}</li>)}</ol>
      </details>
    </aside>
    </div>
    <footer className="mvp-toolbar replay-controls terminal-glass">
      {!live && <>
        <button className="mvp-action" disabled={index <= 0} onClick={() => jump(index - 1)}>Previous</button>
        <button className="mvp-action" disabled={!events.length} onClick={() => {
          if (index === events.length - 1) { setCursor(0); setPlaying(true); }
          else setPlaying(!playing);
        }}>{playing && index < events.length - 1 ? "Pause" : "Play"}</button>
        <button className="mvp-action" disabled={index >= events.length - 1} onClick={() => jump(index + 1)}>Next</button>
        <input aria-label="Investigation timeline" type="range" min="0" max={Math.max(0, events.length - 1)} value={Math.max(0, index)}
          onChange={event => jump(Number(event.target.value))} />
        <select className="terminal-field" aria-label="Playback speed" value={speed} onChange={event => setSpeed(Number(event.target.value))}>
          {[0.5, 1, 2, 4].map(value => <option key={value} value={value}>{value}×</option>)}
        </select>
        <button className="mvp-action" disabled={nextFinding < 0} onClick={() => jump(nextFinding)}>Next finding</button>
        {active && <Link className="mvp-action" to={route(id) + "?seq=" + active.seq} onClick={() => jump(index)}>Event {active.seq}</Link>}
      </>}
      <span className="mvp-muted">{index + 1} / {events.length} events</span>
    </footer>
    {proposalOpen && proposalId && <ProposalDialog key={proposalId} id={proposalId} mode={mode}
      close={() => setProposalOpen(false)} changed={() => setResolved(true)} />}
  </div>;
}

function AgentVisual({ event }: { event: AgentEvent }) {
  const output = event.payload.outputs as Record<string, unknown> | undefined;
  const input = event.payload.inputs as Record<string, unknown> | undefined;
  if (!output) return null;
  if (event.payload.name === "correlation_lattice" && Array.isArray(input?.tickers) && typeof input?.lookback === "number") {
    const query = new URLSearchParams({ as_of: event.as_of, lookback: String(input.lookback), tickers: input.tickers.join(",") });
    return MOCK ? <p>Average link {String(output.avg_pairwise)} · {String(output.history_days)} daily returns</p> :
      <AgentMatrix query={query.toString()} />;
  }
  if (event.payload.name === "optimise" && output.weights && typeof output.weights === "object") {
    const weights = Object.entries(output.weights).filter((item): item is [string, number] => typeof item[1] === "number");
    return <div className="agent-bars">{weights.map(([ticker, weight]) => <div key={ticker}><span>{ticker}</span>
      <i style={{ width: pct.format(weight) }} /><b>{pct.format(weight)}</b></div>)}</div>;
  }
  if (event.payload.name === "price_summary" && Array.isArray(output.rows)) {
    return <table className="mvp-table"><thead><tr><th>Holding</th><th>Last close</th><th>1 month</th></tr></thead><tbody>
      {(output.rows as { ticker: string; last_gbp: number; ret_1m: number | null }[]).map(row => <tr key={row.ticker}>
        <th>{row.ticker}</th><td>{gbp.format(row.last_gbp)}</td><td>
          {row.ret_1m == null ? "—" : <div className="agent-return" data-direction={row.ret_1m < 0 ? "down" : "up"}>
            <i style={{ width: Math.min(100, Math.abs(row.ret_1m) * 300) + "%" }} /><span>{pct.format(row.ret_1m)}</span>
          </div>}</td></tr>)}
    </tbody></table>;
  }
  if (event.payload.name === "forecast_2w" && output.mu && typeof output.mu === "object") {
    const estimates = Object.entries(output.mu).filter((entry): entry is [string, number] => typeof entry[1] === "number");
    return <><p className="mvp-muted">Two-week estimates · Model output</p><div className="agent-bars">
      {estimates.map(([ticker, value]) => <div key={ticker}><span>{ticker}</span>
        <span className="agent-return" data-direction={value < 0 ? "down" : "up"}><i style={{ width: Math.min(100, Math.abs(value) * 900) + "%" }} /></span>
        <b>{pct.format(value)}</b></div>)}</div></>;
  }
  return <pre>{JSON.stringify(output, null, 2)}</pre>;
}

function AgentMatrix({ query }: { query: string }) {
  const resource = useResource(query, signal => get<CorrelationReport>("/risk/correlation?" + query, "correlation", signal));
  const report = resource.value;
  if (!report) return <p role={resource.error ? "alert" : "status"}>{resource.error ?? "Loading dated correlation matrix…"}</p>;
  return <div className="agent-matrix"><table className="mvp-table" aria-label="Dated correlation matrix">
    <thead><tr><td />{report.tickers.map(ticker => <th key={ticker}>{ticker.split(".")[0]}</th>)}</tr></thead>
    <tbody>{report.tickers.map((ticker, i) => <tr key={ticker}><th>{ticker.split(".")[0]}</th>
      {report.matrix[i]?.map((value, j) => <td key={j} title={ticker + " / " + report.tickers[j]}
        style={{ background: Number.isFinite(value) ? (value < 0 ? "rgb(177 100 99 / " : "rgb(132 163 191 / ") + Math.abs(value) * 0.55 + ")" : undefined }}>
        {Number.isFinite(value) ? value.toFixed(2) : "—"}</td>)}</tr>)}</tbody>
  </table></div>;
}
