import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import AgentAvatar from "../components/AgentAvatar";
import { api, get, mockEvents, MOCK } from "../lib/api";
import { useRunEvents } from "../lib/useRunEvents";
import type { AgentEvent, CorrelationReport, Mode, RunSummary } from "../lib/types";
import { useResource } from "../lib/useResource";
import { EvidenceView, gbp, pct, ProposalDialog, words } from "./Decisions";
import TimelineView from "./Timeline";

const route = (id: string) => "/runs/" + encodeURIComponent(id);
const evidenceFor = (event?: AgentEvent) =>
  event?.type === "calc.result" ? ["calc:" + event.id] : event?.evidence_ids ?? [];
const toolLabels: Record<string, string> = {
  get_prices: "Compare price movements", search_news: "Read relevant news", get_catalogue: "Review eligible investments",
  correlation_lattice: "Compare holding movements", build_options: "Build portfolio options",
  check_proposal: "Check the investment plan", risk_stats: "Measure portfolio risk", backtest: "Test historical performance",
  exposure: "Measure indirect exposure", overlap: "Check overlapping holdings", cost_turnover: "Estimate trade costs",
  forecast: "Estimate two-week movement", propose_adjustment: "Prepare a portfolio proposal",
};
function eventLabel(event: AgentEvent) {
  if ((event.type === "tool.call" || event.type === "tool.result") && typeof event.payload.tool === "string") {
    const label = toolLabels[event.payload.tool] ?? words(event.payload.tool);
    return event.type === "tool.result" ? label + (event.payload.ok === false ? " · Unavailable" : " · Complete") : label;
  }
  if (event.type === "agent.spawned") return "Joined the investigation";
  if (event.type === "agent.status") return event.payload.status === "done" ? "Finished their review" : words(event.title);
  return event.title;
}
type RunItem = Omit<RunSummary, "agents">;

function RunPicker({ mode }: { mode?: Mode }) {
  const [params] = useSearchParams();
  const view = params.get("view");
  const timeline = view === "timeline" || view === "history";
  const runs = useResource("runs:" + mode + ":" + timeline, signal => timeline ? Promise.resolve(null) : get<{ items: RunItem[] }>("/runs?limit=100", "runs", signal));
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function start() {
    setBusy(true);
    setError("");
    try { const { run_id } = await api.build(); navigate(route(run_id) + "?live=1"); }
    catch (e) { setError((e as Error).message); setBusy(false); }
  }
  return <div className="mvp-page mvp-enter agent-workspace">
    <div className="mvp-toolbar"><h1>Agent workspace</h1>
      {mode === "live" && <button className="mvp-action primary" disabled={busy} onClick={() => void start()}>Build my portfolio</button>}</div>
    {!timeline && <p className="mvp-muted">Watch the lead and specialists work through an investigation.</p>}
    <nav className="workspace-tabs" aria-label="Agent workspace views">
      <Link to="/workspace" aria-current={!timeline ? "page" : undefined}>Investigations</Link>
      <Link to="/workspace?view=timeline" aria-current={view === "timeline" ? "page" : undefined}>Timeline</Link>
      {timeline && <Link to="/workspace?view=history" aria-current={view === "history" ? "page" : undefined}>Portfolio history</Link>}
    </nav>
    {error && <p role="alert">{error}</p>}
    {timeline ? <TimelineView portfolioTab={view === "history"} /> : <section className="terminal-glass mvp-panel">
      <h2>Investigations</h2>
      {runs.error && <p role="alert">{runs.error}</p>}
      {runs.value?.items.slice().reverse().map(run => <Link key={run.run_id} to={route(run.run_id) + (run.status === "running" ? "?live=1" : "")} className="run-row">
        <span>{run.trigger_text || words(run.kind)}</span><time>{run.as_of}</time><span>{words(run.outcome ?? run.status)} ›</span>
      </Link>)}
      {!runs.value?.items.length && !runs.error && <p>{runs.value ? "No investigations recorded yet." : "Loading investigations…"}</p>}
    </section>}
  </div>;
}

export default function Workspace({ mode }: { mode?: Mode }) {
  const { runId } = useParams();
  const { search } = useLocation();
  return runId ? <RunRoom key={runId + search} id={runId} mode={mode} /> : <RunPicker mode={mode} />;
}

function RunRoom({ id, mode }: { id: string; mode?: Mode }) {
  const [params] = useSearchParams();
  const debug = import.meta.env.DEV && params.get("debug") === "1";
  const explicitReplay = params.has("seq") || params.get("replay") === "1";
  const wantsLive = !explicitReplay && params.get("live") === "1";
  const checkStatus = !MOCK && mode === "live" && !explicitReplay && !wantsLive;
  const runStatus = useResource(id + ":" + checkStatus, signal =>
    checkStatus ? get<RunSummary>(route(id), "run_detail", signal) : Promise.resolve(null));
  const live = !MOCK && mode === "live" && (wantsLive || (checkStatus && runStatus.value?.status === "running"));
  const waitingForMode = !MOCK && !explicitReplay && (mode === undefined || (checkStatus && !runStatus.value && !runStatus.error));
  const archive = useResource(id + ":" + live + ":" + waitingForMode, signal => live || waitingForMode ? Promise.resolve(null) :
    MOCK ? Promise.resolve({ items: mockEvents() }) :
      get<{ items: AgentEvent[] }>(route(id) + "/events?format=json", "", signal));
  const stream = useRunEvents(id, live);
  const [cursor, setCursor] = useState<number | null>(null);
  const [playing, setPlaying] = useState(!params.has("seq") && !live);
  const [speed, setSpeed] = useState(1);
  const [focused, setFocused] = useState("");
  const [paneSteps, setPaneSteps] = useState<Record<string, number | undefined>>({});
  const [source, setSource] = useState("");
  const [proposalOpen, setProposalOpen] = useState(false);
  const [resolved, setResolved] = useState(false);
  const initialSeq = Number(params.get("seq"));
  const events = live ? stream : archive.value?.items ?? [];
  const initialIndex = Number.isInteger(initialSeq) && initialSeq > 0 ? events.findIndex(event => event.seq >= initialSeq) : 0;
  const lastIndex = events.length - 1;
  const index = live ? lastIndex : Math.min(lastIndex, cursor ?? (initialIndex < 0 ? lastIndex : initialIndex));
  const visible = events.slice(0, index + 1);
  const active = visible.at(-1);
  const sourceCalculation = visible.find(event => event.type === "calc.result" && "calc:" + event.id === source);
  const agents = visible.filter(event => event.type === "agent.spawned" && event.agent_id);
  const selected = agents.find(agent => agent.agent_id === focused);
  const specialists = new Set(agents.slice(2).map(agent => agent.agent_id));
  const recentSpecialist = visible.slice().reverse().find(event => specialists.has(event.agent_id));
  const third = agents.find(agent => agent.agent_id === recentSpecialist?.agent_id);
  const stage = third ? [...agents.slice(0, 2), third] : agents.slice(0, 3);
  const panels = selected ? [selected] : stage;
  const proposal = visible.slice().reverse().find(event => event.type === (live ? "approval.requested" : "proposal.created"));
  const proposalId = typeof proposal?.payload.proposal_id === "string" ? proposal.payload.proposal_id : "";
  const decided = visible.some(event => event.type === "approval.decided" && event.payload.proposal_id === proposalId);
  const nextFinding = events.findIndex((event, i) => i > index && event.type === "finding");
  const finished = visible.some(event => event.type === "run.completed");
  const agentStatuses = new Map<string, string>();
  const calculationOwners = new Map<string, string>();
  for (const event of visible) {
    if (event.type === "agent.status" && event.agent_id && typeof event.payload.status === "string") {
      agentStatuses.set(event.agent_id, event.payload.status);
    }
    if (event.type === "tool.result" && event.agent_id) {
      for (const ref of event.evidence_ids) if (ref.startsWith("calc:")) calculationOwners.set(ref.slice(5), event.agent_id);
    }
  }
  const statusFor = (agentId: string | null) => agentStatuses.get(agentId ?? "") ?? (finished ? "Run ended" : "Working");

  useEffect(() => {
    if (!live && playing && index >= 0 && index < events.length - 1) {
      const delay = window.setTimeout(() => setCursor(index + 1), 540 / speed);
      return () => window.clearTimeout(delay);
    }
  }, [events.length, index, live, playing, speed]);

  useEffect(() => {
    if (live && proposalId && !decided) setProposalOpen(true);
  }, [live, proposalId, decided]);

  function jump(next: number) {
    const target = Math.max(0, Math.min(lastIndex, next));
    setCursor(target);
    setPlaying(false);
    setSource("");
    setPaneSteps({});
    if (selected && selected.seq > events[target]?.seq) setFocused("");
  }

  function inspectEvidence(id: string) {
    setPlaying(false);
    setSource(id);
  }

  function inspectAgentStep(id: string, step?: number) {
    setPlaying(false);
    setSource("");
    setPaneSteps(steps => ({ ...steps, [id]: step }));
  }

  return <div className="agent-room" data-live={live}>
    <div className="agent-room-body">
    <aside className="agent-room-side terminal-glass">
      <header><h1>Agent workspace</h1><Link to="/workspace" aria-label="Back to investigations">←</Link></header>
      <div className="agent-room-brief"><strong>{visible[0]?.trigger_text || "Investigation"}</strong>
        <p>{active?.as_of ?? ""} · {waitingForMode ? "Connecting…" : live ? finished ? "Run complete" : "Live investigation" : "Recorded investigation"}</p></div>
      {live && finished && <div className="agent-room-brief"><Link className="mvp-action" to={route(id) + "?replay=1"}>Replay run</Link></div>}
      <div className="agent-room-brief mvp-muted">Participants ({agents.length})</div>
      {agents.map(agent => <button className="agent-participant" key={agent.id} aria-pressed={focused === agent.agent_id}
        onClick={() => setFocused(focused === agent.agent_id ? "" : agent.agent_id ?? "")}>
        <AgentAvatar role={agent.role ?? ""} /><span>{words(agent.role ?? "Specialist")}</span>
        <small>{words(statusFor(agent.agent_id))}</small>
      </button>)}
    </aside>
    <div className="agent-room-center">
    {archive.error && <p role="alert">{archive.error}</p>}
    {!agents.length && <section className="terminal-glass mvp-panel agent-opening"><AgentAvatar role="lead" /><h2>Lead agent</h2>
      <p>{active?.trigger_text || active?.title || (archive.value ? "No recorded events for this run." : "Waiting for investigation events…")}</p></section>}
    <div className="agent-stage" data-count={panels.length}>
      {panels.map(agent => {
        const agentId = agent.agent_id ?? agent.id;
        const activity = visible.filter(event => {
          if (event.agent_id) return event.agent_id === agentId;
          if (event.type !== "calc.result") return false;
          const owner = calculationOwners.get(event.id);
          return owner ? owner === agentId : agent.role === "lead";
        });
        const inspected = activity.findIndex(event => event.seq === paneSteps[agentId]);
        const position = inspected < 0 ? activity.length - 1 : inspected;
        const shown = activity.slice(0, position + 1);
        const current = shown.at(-1);
        const work = shown.slice().reverse().find(event => ["calc.result", "finding", "tool.result", "agent.message", "source.inspect"].includes(event.type));
        const visual = shown.slice().reverse().find(event => event.type === "calc.result" && event.payload.outputs);
        const previewSource = !MOCK && (work?.type === "source.inspect" ||
          (work?.type === "tool.result" && work.payload.tool === "search_news")) ? work?.evidence_ids[0] : undefined;
        const checks = agent.role === "lead" ? new Map(visible.filter(event =>
          event.type === "gate.verdict" && (inspected < 0 || event.seq <= (current?.seq ?? 0)) &&
          typeof event.payload.gate === "string").map(event => [String(event.payload.gate), event])) : null;
        const parent = agents.find(item => item.agent_id === agent.parent_agent_id);
        const delegated = agents.filter(item => item.parent_agent_id === agent.agent_id);
        const status = !finished && inspected < 0 && current?.type === "tool.call" ? "Working" : statusFor(agent.agent_id);
        return <section className="terminal-glass agent-tile" key={agent.id} data-following={live && inspected < 0}>
          <header><AgentAvatar role={agent.role ?? "lead"} /><div><h2>{words(agent.role === "lead" ? "Lead agent" : agent.role ?? "Agent")}</h2>
            <p>{parent ? "Delegated by " + words(parent.role ?? "lead") : "Coordinates the investigation"}</p></div>
            <button className="mvp-action" onClick={() => setFocused(selected ? "" : agent.agent_id ?? "")}>{selected ? "Show team" : "Expand"}</button></header>
          <div className="agent-tile-work">
            <p className="mvp-muted">{agent.purpose || String(agent.payload.question ?? "")}</p>
            <h3 className="agent-step-title" key={current?.id}>{current ? eventLabel(current) : "Preparing"}</h3>
            {current?.type === "tool.call" && <div className="agent-tool" role="status">
              <span />{inspected < 0 && !finished ? "Waiting for results" : "Calculation started"}
            </div>}
            {visual && !previewSource && <>{visual.id !== work?.id && <p className="mvp-muted">Latest calculation · {visual.title}</p>}
              {visual.id === work?.id && visual.agent_id == null && <p className="mvp-muted">Engine calculation</p>}
              <AgentVisual key={visual.id} event={visual} debug={debug} /></>}
            {previewSource && <EvidenceView key={previewSource} id={previewSource} />}
            {!!checks?.size && <ul className="proposal-gates" aria-label="Assurance progress">{[...checks].map(([gate, event]) =>
              <li key={gate} data-status={String(event.payload.status)}>{words(gate)} · {words(String(event.payload.status))}</li>)}</ul>}
            {delegated.length > 0 && <div className="agent-delegation" aria-label="Delegated work">{delegated.map(child =>
              <button className="mvp-action" key={child.id} onClick={() => setFocused(child.agent_id ?? "")}>
                <AgentAvatar role={child.role ?? ""} />
                <span><b>{words(child.role ?? "Specialist")}</b><small>{child.purpose}</small></span>
              </button>)}</div>}
            {evidenceFor(work).map(id => <button key={id} className="mvp-link" onClick={() => inspectEvidence(id)}>Inspect evidence</button>)}
            {selected && debug && <ol className="agent-events">{activity.map(event =>
              <li key={event.id}><button disabled={live} onClick={() => jump(events.indexOf(event))}>{event.seq} · {event.title}</button></li>)}</ol>}
          </div>
          <footer className="agent-step-controls">
            <span>{inspected < 0 ? words(status) : "Reviewing step"}</span>
            <div>
              <button className="mvp-action" type="button" aria-label={`Previous step for ${words(agent.role ?? "agent")}`}
                disabled={position <= 0} onClick={() => inspectAgentStep(agentId, activity[position - 1].seq)}>‹</button>
              <span>{position + 1} / {activity.length}</span>
              <button className="mvp-action" type="button" aria-label={`Next step for ${words(agent.role ?? "agent")}`}
                disabled={position >= activity.length - 1}
                onClick={() => inspectAgentStep(agentId, position + 1 === activity.length - 1 ? undefined : activity[position + 1].seq)}>›</button>
            </div>
          </footer>
        </section>;
      })}
    </div>
    {visible.filter(event => event.type === "agent.spawn_denied").map(event =>
      <p className="agent-refused" key={event.id}>{event.title}{event.purpose && " · " + event.purpose}</p>)}
    {proposalId && <div className="proposal-nudge terminal-glass"><strong>{resolved || decided ? "Decision recorded" : live ? "Your approval is needed" : proposal?.title}</strong>
      <button className="mvp-action primary" onClick={() => { setPlaying(false); setProposalOpen(true); }}>Review proposal</button></div>}
    </div>
    <aside className="agent-room-side terminal-glass agent-room-activity">
      <header><h2>{source ? "Evidence" : "Investigation activity"}</h2>
        {source && <button className="mvp-action" onClick={() => setSource("")}>Close evidence</button>}</header>
      {source ? <div className="agent-room-evidence"><EvidenceView key={source} id={source} debug={debug} />
        {sourceCalculation && <AgentVisual key={sourceCalculation.id} event={sourceCalculation} debug={false} />}
      </div> : <>
      {active && <div className="agent-room-brief"><small>Current step · {active.seq}</small><strong>{eventLabel(active)}</strong>
        {evidenceFor(active).map(id => <button key={id} className="mvp-link" onClick={() => inspectEvidence(id)}>Open source</button>)}
        {debug && <details className="agent-terminal"><summary>Inspect payload</summary><pre>{JSON.stringify(active.payload, null, 2)}</pre></details>}
      </div>}
      <ol className="agent-event-list">{visible.slice().reverse().map(event => {
        const actor = agents.find(agent => agent.agent_id === event.agent_id);
        const label = <><span className="agent-event-title">{eventLabel(event)}</span><small>{words(event.role ?? "Portfolio engine")} · {event.seq}</small></>;
        const action = !live ? () => jump(events.indexOf(event)) : actor && actor.agent_id ? () => {
          setFocused(actor.agent_id ?? "");
          inspectAgentStep(actor.agent_id ?? "", event.seq);
        } : evidenceFor(event)[0] ? () => inspectEvidence(evidenceFor(event)[0]) : undefined;
        return <li key={event.id} aria-current={event.id === active?.id ? "step" : undefined}>
          {action ? <button onClick={action}>{label}</button> : <div>{label}</div>}
        </li>;
      })}</ol>
      {debug && <details className="agent-terminal"><summary>Execution log</summary>
        <ol className="agent-events">{visible.map(event => <li key={event.id}>{event.seq} · {event.type} · {event.title}</li>)}</ol>
      </details>}
      </>}
    </aside>
    </div>
    {!live && !waitingForMode && <footer className="mvp-toolbar replay-controls terminal-glass">
        <button className="mvp-action" disabled={index <= 0} onClick={() => jump(index - 1)}>Previous</button>
        <button className="mvp-action replay-play" disabled={!events.length} onClick={() => {
          if (index === lastIndex) { jump(0); setPlaying(true); }
          else { setSource(""); setPlaying(!playing); }
        }}>{playing && index < events.length - 1 ? "Pause" : "Play"}</button>
        <button className="mvp-action" disabled={index >= events.length - 1} onClick={() => jump(index + 1)}>Next</button>
        <input aria-label="Investigation timeline" aria-valuetext={active ? `Event ${active.seq}, ${index + 1} of ${events.length}` : undefined}
          type="range" min="0" max={Math.max(0, lastIndex)} value={Math.max(0, index)} disabled={events.length < 2}
          onChange={event => jump(Number(event.target.value))} />
        <select className="terminal-field" aria-label="Playback speed" value={speed} onChange={event => setSpeed(Number(event.target.value))}>
          {[0.5, 1, 2, 4].map(value => <option key={value} value={value}>{value}×</option>)}
        </select>
        <button className="mvp-action" disabled={nextFinding < 0} onClick={() => jump(nextFinding)}>Next finding</button>
        {active && <Link className="mvp-action replay-step-link" to={route(id) + "?seq=" + active.seq} onClick={() => jump(index)}>Event {active.seq}</Link>}
      <span className="mvp-muted replay-count">{index + 1} / {events.length} events</span>
    </footer>}
    {proposalOpen && proposalId && <ProposalDialog key={proposalId} id={proposalId} mode={mode}
      close={() => setProposalOpen(false)} changed={() => setResolved(true)} />}
  </div>;
}

function AgentVisual({ event, debug }: { event: AgentEvent; debug: boolean }) {
  const output = event.payload.outputs as Record<string, unknown> | undefined;
  const input = event.payload.inputs as Record<string, unknown> | undefined;
  if (!output) return null;
  if (event.payload.name === "correlation_lattice" && Array.isArray(input?.tickers) && typeof input?.lookback === "number") {
    if (Array.isArray(output.tickers) && Array.isArray(output.matrix)) return <Matrix report={output as unknown as CorrelationReport} />;
    const query = new URLSearchParams({ as_of: event.as_of, lookback: String(input.lookback), tickers: input.tickers.join(",") });
    return MOCK ? <ResultBars rows={[[ "Average link", Number(output.avg_pairwise) ]]} format={value => value.toFixed(2)} /> :
      <AgentMatrix query={query.toString()} />;
  }
  if (event.payload.name === "backtest" && Array.isArray(output.nav)) {
    const points = (output.nav as [string, number][]).map(([date, value]) => ({ date, value }));
    return <figure className="agent-backtest">
      <figcaption>Historical portfolio value · Simulated</figcaption>
      <ResponsiveContainer width="100%" height={160}>
        <AreaChart data={points} margin={{ right: 8, top: 8 }}>
          <CartesianGrid vertical={false} stroke="var(--terminal-edge)" />
          <XAxis dataKey="date" tick={{ fontSize: 9, fill: "var(--terminal-muted)" }} minTickGap={38} />
          <YAxis width={56} domain={["auto", "auto"]} tick={{ fontSize: 9, fill: "var(--terminal-muted)" }} tickFormatter={value => "£" + Math.round(value)} />
          <Tooltip formatter={(value: number) => gbp.format(value)} />
          <Area dataKey="value" name="Portfolio value" stroke="var(--terminal-accent)" fill="var(--terminal-accent)" fillOpacity={.15} isAnimationActive={false} />
        </AreaChart>
      </ResponsiveContainer>
    </figure>;
  }
  if (event.payload.name === "exposure") {
    const funds = Object.entries(output.via_funds ?? {}).filter((entry): entry is [string, number] => typeof entry[1] === "number");
    if (typeof output.direct === "number" && output.direct > 0) funds.unshift(["Direct holding", output.direct]);
    return <><p className="mvp-muted">Ownership exposure by holding</p><ResultBars rows={funds} format={pct.format} /></>;
  }
  if (event.payload.name === "overlap" && Array.isArray(output.pairs)) {
    const pairs = output.pairs as { a: string; b: string; overlap: number | null }[];
    return <><p className="mvp-muted">Shared holdings by weight</p>
      <ResultBars rows={pairs.flatMap(pair => pair.overlap == null ? [] : [[pair.a + " / " + pair.b, pair.overlap]])} format={pct.format} /></>;
  }
  if (event.payload.name === "risk_stats" || event.payload.name === "backtest") {
    const rows: [string, unknown][] = [["Historical return", output.total_return], ["Annual volatility", output.vol_annual],
      ["Worst decline", output.max_drawdown], ["Cash", output.cash_weight]];
    return <ResultBars rows={rows.filter((row): row is [string, number] => typeof row[1] === "number")} format={pct.format} />;
  }
  if (event.payload.name === "cost_turnover" && Array.isArray(output.trades)) {
    const trades = output.trades as { ticker: string; action: string; amount_gbp: number }[];
    return <><p>Estimated costs {gbp.format(Number(output.cost_gbp))}</p>
      <ResultBars rows={trades.map(trade => [trade.ticker, (trade.action === "sell" ? -1 : 1) * Math.abs(trade.amount_gbp)])} format={gbp.format} /></>;
  }
  if (event.payload.name === "check_proposal") {
    const issues = Array.isArray(output.violations) ? output.violations as { message: string }[] : [];
    return <div className="agent-check" data-pass={output.passed === true}>
      <strong>{output.passed ? "✓ Fits the investment plan" : "Needs changes before approval"}</strong>
      {issues.map((issue, index) => <p key={index}>{issue.message}</p>)}
    </div>;
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
  return debug ? <pre>{JSON.stringify(output, null, 2)}</pre> : null;
}

function ResultBars({ rows, format }: { rows: [string, number][]; format: (value: number) => string }) {
  const valid = rows.filter(([, value]) => Number.isFinite(value));
  if (!valid.length) return <p className="mvp-muted">No measured values for this step.</p>;
  const scale = Math.max(...valid.map(([, value]) => Math.abs(value))) || 1;
  return <div className="agent-result-bars">{valid.map(([label, value], index) =>
    <div key={label + index} data-negative={value < 0}><span>{label}</span>
      <span aria-hidden="true"><i style={{ width: (Math.abs(value) / scale * 100) + "%" }} /></span>
      <strong>{format(value)}</strong></div>)}</div>;
}

function AgentMatrix({ query }: { query: string }) {
  const resource = useResource(query, signal => get<CorrelationReport>("/risk/correlation?" + query, "correlation", signal));
  const report = resource.value;
  if (!report) return <p role={resource.error ? "alert" : "status"}>{resource.error ?? "Loading dated correlation matrix…"}</p>;
  return <Matrix report={report} />;
}

function Matrix({ report }: { report: CorrelationReport }) {
  return <div className="agent-matrix"><table className="mvp-table" aria-label="Dated correlation matrix">
    <thead><tr><td />{report.tickers.map(ticker => <th key={ticker}>{ticker.split(".")[0]}</th>)}</tr></thead>
    <tbody>{report.tickers.map((ticker, i) => <tr key={ticker}><th>{ticker.split(".")[0]}</th>
      {report.matrix[i]?.map((value, j) => <td key={j} title={ticker + " / " + report.tickers[j]}
        style={{ background: Number.isFinite(value) ? (value < 0 ? "rgb(177 100 99 / " : "rgb(132 163 191 / ") + Math.abs(value) * 0.55 + ")" : undefined }}>
        {Number.isFinite(value) ? value.toFixed(2) : "—"}</td>)}</tr>)}</tbody>
  </table></div>;
}
