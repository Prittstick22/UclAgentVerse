import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { Link, Navigate, useLocation, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import AgentAvatar from "../components/AgentAvatar";
import { ShellIcon } from "../components/TerminalShellUi";
import { api, get, mockEvents, MOCK } from "../lib/api";
import { useRunEvents } from "../lib/useRunEvents";
import type { AgentEvent, CorrelationReport, Mode, RunSummary } from "../lib/types";
import { useResource } from "../lib/useResource";
import { EvidenceView, gbp, pct, ProposalDialog, words } from "./Decisions";
import { FindingBadges } from "../components/ProposalEvidence";

const route = (id: string) => "/runs/" + encodeURIComponent(id);
const evidenceFor = (event?: AgentEvent) =>
  event?.type === "calc.result" ? ["calc:" + event.id] : event?.evidence_ids ?? [];
const toolLabels: Record<string, string> = {
  get_prices: "Compare price movements", search_news: "Read relevant news", get_catalogue: "Review eligible investments",
  correlation_lattice: "Compare holding movements", build_options: "Build portfolio options",
  check_proposal: "Check the investment plan", risk_stats: "Measure portfolio risk", backtest: "Test historical performance",
  exposure: "Measure indirect exposure", overlap: "Check overlapping holdings", cost_turnover: "Estimate trade costs",
  forecast: "Estimate two-week movement", propose_adjustment: "Prepare a portfolio proposal",
  search_filings: "Read company filings", web_search: "Search market sources",
};
const sourceTools = new Set(["search_news", "search_filings", "web_search"]);
const outcomeLabels: Record<string, string> = {
  built: "Starting portfolio prepared", adjust: "Change proposed", maintain: "Portfolio kept as is",
  investigate_further: "More investigation needed", answered: "Review answered",
};

function AgentSources({ ids }: { ids: string[] }) {
  const [sourceIndex, setSourceIndex] = useState(0);
  return <div className="agent-sources">
    {ids.length > 1 && <div className="agent-source-switch">
      <span>Source {sourceIndex + 1} of {ids.length}</span>
      <button type="button" className="mvp-action" aria-label="Previous source" disabled={sourceIndex === 0}
        onClick={() => setSourceIndex(index => index - 1)}>‹</button>
      <button type="button" className="mvp-action" aria-label="Next source" disabled={sourceIndex === ids.length - 1}
        onClick={() => setSourceIndex(index => index + 1)}>›</button>
    </div>}
    <EvidenceView key={ids[sourceIndex]} id={ids[sourceIndex]} />
  </div>;
}

function WebSources({ event }: { event: AgentEvent }) {
  const sources = Array.isArray(event.payload.sources) ? event.payload.sources as { title?: string; url?: string }[] : [];
  const links = sources.filter(item => typeof item?.url === "string" && /^https?:\/\//i.test(item.url));
  return <div className="agent-sources">
    {event.type === "source.inspect" && typeof event.payload.title === "string" && <p>{event.payload.title}</p>}
    {links.length ? <ul>{links.map(({ title, url }, index) => <li key={url + ":" + index}>
      <a href={url} target="_blank" rel="noreferrer">{title || url} ↗</a>
    </li>)}</ul> : <p className="mvp-muted">No source links returned for this search.</p>}
  </div>;
}

function StepIcon({ event }: { event: AgentEvent }) {
  const source = event.type === "source.inspect" || sourceTools.has(String(event.payload.tool));
  const name = source ? "search" : event.type === "calc.result" ? "chart" :
    event.type.startsWith("agent.spawn") ? "agents" :
      /^(approval|gate|decision)\./.test(event.type) ? "decisions" : "timeline";
  return <ShellIcon name={name} />;
}

const roleName = (role: string | null | undefined) => words(role || "agent").replace(/\b[a-z]/g, letter => letter.toUpperCase());

function elapsedLabel(ms: number) {
  const seconds = Math.max(0, Math.floor(ms / 1000));
  return seconds < 60 ? seconds + "s" : Math.floor(seconds / 60) + "m " + (seconds % 60) + "s";
}

function eventLabel(event: AgentEvent) {
  if ((event.type === "tool.call" || event.type === "tool.result") && typeof event.payload.tool === "string") {
    const label = toolLabels[event.payload.tool] ?? words(event.payload.tool);
    return event.type === "tool.result" ? label + (event.payload.ok === false ? " · Unavailable" : " · Complete") : label;
  }
  if (event.type === "run.completed") return event.status === "failed" ? "Investigation stopped" : outcomeLabels[String(event.payload.outcome)] ?? "Investigation complete";
  if (event.type === "decision.made") return outcomeLabels[String(event.payload.action)] ?? "Recorded a decision";
  if (event.type === "approval.requested") return "Your approval is needed";
  if (event.type === "approval.decided" && event.payload.by === "user_policy") return "Approved within your saved limit";
  if (event.type === "agent.spawn_requested" || event.type === "agent.spawn_denied") {
    const role = roleName(typeof event.payload.role === "string" ? event.payload.role : null);
    return event.type === "agent.spawn_requested" ? "Asked " + role + " to join" : role + " couldn’t join";
  }
  if (event.type === "agent.spawned") return "Joined the investigation";
  if (event.type === "agent.status") return event.payload.status === "done" ? "Finished their review" : words(event.title);
  return event.title;
}
type RunItem = Omit<RunSummary, "agents">;

function RunPicker({ mode }: { mode?: Mode }) {
  const [params] = useSearchParams();
  const view = params.get("view");
  const legacyTimeline = view === "timeline" || view === "history";
  const runs = useResource("runs:" + mode + ":" + legacyTimeline, signal => legacyTimeline ? Promise.resolve(null) : get<{ items: RunItem[] }>("/runs?limit=100", "runs", signal));
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function start() {
    setBusy(true);
    setError("");
    try { const { run_id } = await api.build(); navigate(route(run_id) + "?live=1"); }
    catch (e) { setError((e as Error).message); setBusy(false); }
  }
  if (legacyTimeline) return <Navigate replace to={view === "history" ? "/timeline?view=history" : "/timeline"} />;
  return <div className="mvp-page mvp-enter agent-workspace">
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
  const { search } = useLocation();
  return runId ? <RunRoom key={runId + search} id={runId} mode={mode} /> : <RunPicker mode={mode} />;
}

function useAgentStageMotion(signature: string, animate: boolean) {
  const stage = useRef<HTMLDivElement>(null);
  const previous = useRef<{ signature: string; boxes: Map<string, DOMRect> }>();

  useLayoutEffect(() => {
    const tiles = Array.from(stage.current?.querySelectorAll<HTMLElement>("[data-agent-tile]") ?? []);
    const boxes = new Map(tiles.map(tile => [tile.dataset.agentTile!, tile.getBoundingClientRect()]));
    const before = previous.current;
    previous.current = { signature, boxes };
    if (!animate || !before || before.signature === signature || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    for (const tile of tiles) {
      const key = tile.dataset.agentTile!;
      const prior = before.boxes.get(key);
      const next = boxes.get(key)!;
      if (!prior) {
        tile.animate([{ opacity: 0, transform: "translateY(7px)" }, { opacity: 1, transform: "none" }], {
          duration: 245, easing: "cubic-bezier(.22,.72,.28,1)",
        });
      } else if (Math.abs(prior.x - next.x) > 1 || Math.abs(prior.y - next.y) > 1) {
        tile.animate([{ transform: "translate(" + (prior.x - next.x) + "px," + (prior.y - next.y) + "px)" }, { transform: "none" }], {
          duration: 280, easing: "cubic-bezier(.22,.72,.28,1)",
        });
      }
    }
  });

  return stage;
}

export function RunRoom({ id, mode, embedded = false, autoplay = false, onContinue }: {
  id: string; mode?: Mode; embedded?: boolean; autoplay?: boolean; onContinue?: () => void;
}) {
  const [params] = useSearchParams();
  const debug = import.meta.env.DEV && params.get("debug") === "1";
  const explicitReplay = embedded || params.has("seq") || params.get("replay") === "1";
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
  const [playing, setPlaying] = useState(embedded ? autoplay : !params.has("seq") && !live);
  const [speed, setSpeed] = useState(1);
  const [focused, setFocused] = useState("");
  const [paneSteps, setPaneSteps] = useState<Record<string, number | undefined>>({});
  const [source, setSource] = useState("");
  const [proposalOpen, setProposalOpen] = useState(false);
  const [resolved, setResolved] = useState(false);
  const initialSeq = Number(params.get("seq"));
  const events = live ? stream : archive.value?.items ?? [];
  const initialIndex = Number.isInteger(initialSeq) && initialSeq > 0
    ? events.findIndex(event => event.seq >= initialSeq)
    : embedded && !autoplay ? Math.max(0, events.findIndex(event => event.type === "agent.spawned")) : 0;
  const lastIndex = events.length - 1;
  const index = live ? lastIndex : Math.min(lastIndex, cursor ?? (initialIndex < 0 ? lastIndex : initialIndex));
  const visible = events.slice(0, index + 1);
  const active = visible.at(-1);
  const activeEvidence = evidenceFor(active).find(id => !id.startsWith("web:"));
  const activityLog = visible.slice(0, -1);
  const sourceCalculation = visible.find(event => event.type === "calc.result" && "calc:" + event.id === source);
  const agents = visible.filter(event => event.type === "agent.spawned" && event.agent_id);
  const selected = agents.find(agent => agent.agent_id === focused);
  const specialists = new Set(agents.slice(2).map(agent => agent.agent_id));
  const recentSpecialist = visible.slice().reverse().find(event => specialists.has(event.agent_id));
  const third = agents.find(agent => agent.agent_id === recentSpecialist?.agent_id);
  const stage = third ? [...agents.slice(0, 2), third] : agents.slice(0, 3);
  const lead = agents[0];
  const panels = embedded ? [...(lead ? [lead] : []), ...(selected && selected !== lead ? [selected] : [])] : selected ? [selected] : stage;
  const stageRef = useAgentStageMotion(panels.map(agent => agent.id).join(","), live || playing);
  const proposal = visible.slice().reverse().find(event => live
    ? event.type === "approval.requested" || (event.type === "approval.decided" && event.payload.by === "user_policy")
    : event.type === "proposal.created");
  const proposalId = typeof proposal?.payload.proposal_id === "string" ? proposal.payload.proposal_id : "";
  const decided = visible.some(event => event.type === "approval.decided" && event.payload.proposal_id === proposalId);
  const nextFinding = events.findIndex((event, i) => i > index && event.type === "finding");
  const finished = visible.some(event => event.type === "run.completed");
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    if (!live || finished) return;
    setNow(Date.now());
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [live, finished]);
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
    if (!live && playing && index >= 0 && index === events.length - 1 && onContinue) {
      const delay = window.setTimeout(onContinue, 700 / speed);
      return () => window.clearTimeout(delay);
    }
  }, [events.length, index, live, onContinue, playing, speed]);

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

  const orderedActivity = activityLog.slice().reverse();
  function activityRow(event: AgentEvent) {
    const actor = agents.find(agent => agent.agent_id === event.agent_id);
    const label = <>{event.type.startsWith("agent.spawn") && typeof event.payload.role === "string" ? <AgentAvatar role={event.payload.role} /> : <StepIcon event={event} />}<span className="agent-event-title">{eventLabel(event)}</span><small>{words(event.role ?? "Portfolio engine")}{debug ? " · " + event.seq : ""}</small></>;
    const evidenceId = evidenceFor(event).find(id => !id.startsWith("web:"));
    const action = !live ? () => jump(events.indexOf(event)) : actor && actor.agent_id ? () => {
      setFocused(actor.agent_id ?? "");
      inspectAgentStep(actor.agent_id ?? "", event.seq);
    } : evidenceId ? () => inspectEvidence(evidenceId) : undefined;
    return <li key={event.id} aria-current={event.id === active?.id ? "step" : undefined}>
      {action ? <button onClick={action}>{label}</button> : <div>{label}</div>}
    </li>;
  }

  return <div className="agent-room" data-live={live} data-embedded={embedded}>
    <div className="agent-room-body">
    {!embedded && <aside className="agent-room-side terminal-glass">
      <header><h1>{embedded ? "Investigation" : "Agent workspace"}</h1>{!embedded && <Link to="/workspace" aria-label="Back to investigations">←</Link>}</header>
      <div className="agent-room-brief"><strong>{visible[0]?.trigger_text || "Investigation"}</strong>
        <p>{active?.as_of ?? ""} · {waitingForMode ? "Connecting…" : live ? finished ? "Run complete" : "Live investigation" : "Recorded investigation"}</p></div>
      {live && finished && <div className="agent-room-brief"><Link className="mvp-action" to={route(id) + "?replay=1"}>Replay run</Link></div>}
      <div className="agent-room-brief mvp-muted">Participants ({agents.length})</div>
      {agents.map(agent => <button className="agent-participant" key={agent.id} aria-pressed={focused === agent.agent_id}
        onClick={() => setFocused(focused === agent.agent_id ? "" : agent.agent_id ?? "")}>
        <AgentAvatar role={agent.role ?? ""} /><span>{words(agent.role ?? "Specialist")}</span>
        <small>{words(statusFor(agent.agent_id))}</small>
      </button>)}
    </aside>}
    <div className="agent-room-center">
    {embedded && agents.length > 1 && <div className="timeline-agent-strip" aria-label="Inspect a specialist">
      {agents.slice(1).map(agent => <button type="button" className="agent-participant" key={agent.id}
        aria-pressed={focused === agent.agent_id} onClick={() => setFocused(focused === agent.agent_id ? "" : agent.agent_id ?? "")}>
        <AgentAvatar role={agent.role ?? ""} /><span>{roleName(agent.role)}</span>
      </button>)}
    </div>}
    {embedded && source && <section className="agent-inline-evidence terminal-glass">
      <button type="button" className="mvp-action" onClick={() => setSource("")}>Close evidence</button>
      <EvidenceView key={source} id={source} debug={debug} />
      {sourceCalculation && <AgentVisual event={sourceCalculation} debug={false} />}
    </section>}
    {archive.error && <p role="alert">{archive.error}</p>}
    {!agents.length && <section className="terminal-glass mvp-panel agent-opening"><AgentAvatar role="lead" /><h2>Lead agent</h2>
      <p>{active?.trigger_text || active?.title || (archive.value ? "No recorded events for this run." : "Waiting for investigation events…")}</p></section>}
    {!panels.length && <div className="agent-empty terminal-glass" role="status">
      <AgentAvatar role="lead" />
      <strong>{live ? "Connecting to the investigation" : events.length ? "The Lead joins at the next step" : "Waiting for recorded steps"}</strong>
      <p>{archive.error ?? (live ? "The Lead Agent will appear when the first event arrives." : "The room will show the recorded agents and evidence as soon as they load.")}</p>
    </div>}
    <div className="agent-stage" ref={stageRef} data-count={panels.length}>
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
        const work = current?.type === "agent.status" ?
          shown.slice(0, -1).reverse().find(event => ["calc.result", "finding", "tool.result", "agent.message", "source.inspect"].includes(event.type)) : current;
        const linkedEvidence = evidenceFor(work);
        const calculation = work?.type === "calc.result" ? work : shown.slice().reverse().find(event =>
          event.type === "calc.result" && linkedEvidence.includes("calc:" + event.id));
        const isSourceWork = work?.type === "source.inspect" || (work?.type === "tool.result" && sourceTools.has(String(work.payload.tool)));
        const webSource = isSourceWork ? shown.slice().reverse().find(event =>
          event.type === "source.inspect" && event.payload.kind === "web" && evidenceFor(event).some(id => linkedEvidence.includes(id))) : undefined;
        const documentIds = !MOCK && isSourceWork ? [...new Set(linkedEvidence.filter(id => !id.startsWith("web:")))] : [];
        const message = work?.type === "finding" ? work.payload.claim : work?.type === "agent.message" ? work.payload.text : null;
        const searchEmpty = work?.type === "tool.result" && work.payload.ok === true && isSourceWork && !linkedEvidence.length;
        const evidenceLinks = linkedEvidence.filter(id => !documentIds.includes(id) && !id.startsWith("web:"));
        const checks = agent.role === "lead" ? new Map(visible.filter(event =>
          event.type === "gate.verdict" && (inspected < 0 || event.seq <= (current?.seq ?? 0)) &&
          typeof event.payload.gate === "string").map(event => [String(event.payload.gate), event])) : null;
        const parent = agents.find(item => item.agent_id === agent.parent_agent_id);
        const delegated = agents.filter(item => item.parent_agent_id === agent.agent_id && (inspected < 0 || item.seq <= (current?.seq ?? 0)));
        const status = !finished && inspected < 0 && current?.type === "tool.call" ? "Working" : statusFor(agent.agent_id);
        return <section className="terminal-glass agent-tile" key={agent.id} data-agent-tile={agent.id} data-following={(live || playing) && inspected < 0}>
          <header><AgentAvatar role={agent.role ?? "lead"} /><div><h2>{words(agent.role === "lead" ? "Lead agent" : agent.role ?? "Agent")}</h2>
            <p>{parent ? <button type="button" className="agent-parent" aria-label={"Parent task: " + words(parent.role ?? "Lead agent")} title="Parent task"
              onClick={() => setFocused(parent.agent_id ?? "")}>↖ {words(parent.role ?? "Lead agent")}</button> : "Coordinates the investigation"}</p></div>
            {(!embedded || agent !== lead) && <button className="mvp-action" onClick={() => setFocused(selected ? "" : agent.agent_id ?? "")}>
              {embedded ? "Close specialist" : selected ? "Show team" : "Expand"}
            </button>}</header>
          <div className="agent-tile-work">
            <p className="mvp-muted">{agent.purpose || String(agent.payload.question ?? "")}</p>
            <h3 className="agent-step-title" key={"title:" + current?.id}>
              {current?.type === "agent.spawn_requested" && typeof current.payload.role === "string" && <AgentAvatar role={current.payload.role} />}
              {current ? eventLabel(current) : "Preparing"}
            </h3>
            {current?.type === "tool.call" && <p className="agent-tool" role="status">
              <span />{inspected < 0 && !finished ? "Waiting for results" : "Tool started"}
            </p>}
            {live && !finished && inspected < 0 && current?.type === "agent.spawned" && <div className="agent-work-loading" role="status">
              <div><ShellIcon name="timeline" /><strong>{agent.role === "lead" ? "Reviewing the brief" : "Starting the delegated check"}</strong></div>
              <p>Evidence will appear here as this agent works.</p>
              <span aria-hidden="true"><i /></span>
            </div>}
            {work?.type === "finding" && <FindingBadges finding={work} events={shown} />}
            {typeof message === "string" && message !== current?.title && <p className="agent-step-note">{message.slice(0, 800)}</p>}
            {calculation && <div className="agent-work-reveal" key={"visual:" + calculation.id}><AgentVisual event={calculation} debug={debug} /></div>}
            {webSource && <div className="agent-work-reveal" key={"web:" + webSource.id}><WebSources event={webSource} /></div>}
            {documentIds.length > 0 && <div className="agent-work-reveal" key={"sources:" + work?.id}><AgentSources ids={documentIds} /></div>}
            {searchEmpty && <p className="mvp-muted">No matching sources were returned.</p>}
            {!!checks?.size && <ul className="proposal-gates" aria-label="Assurance progress">{[...checks].map(([gate, event]) =>
              <li key={gate} data-status={String(event.payload.status)}>{words(gate)} · {words(String(event.payload.status))}</li>)}</ul>}
            {delegated.length > 0 && <div className="agent-delegation" aria-label="Delegated work">{delegated.map(child =>
              <button className="mvp-action" key={child.id} onClick={() => setFocused(child.agent_id ?? "")}>
                <AgentAvatar role={child.role ?? ""} />
                <span><b>{words(child.role ?? "Specialist")}</b><small>{child.purpose}</small></span>
              </button>)}</div>}
            {evidenceLinks.map(id => <button key={id} className="mvp-link" onClick={() => inspectEvidence(id)}>Inspect evidence</button>)}
            {selected && debug && <ol className="agent-events">{activity.map(event =>
              <li key={event.id}><button disabled={live} onClick={() => jump(events.indexOf(event))}>{event.seq} · {event.title}</button></li>)}</ol>}
          </div>
          <footer className="agent-step-controls">
            <span>{inspected < 0 ? words(status) : "Reviewing step"}
              {live && !finished && inspected < 0 && (current?.type === "agent.spawned" || current?.type === "tool.call") && current.ts_wall && <small className="agent-elapsed">
                {elapsedLabel(now - Date.parse(current.ts_wall))} on this step
              </small>}
            </span>
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
    {proposalId && <div className="proposal-nudge terminal-glass"><strong>{proposal?.payload.by === "user_policy" ? "Automatically approved · " + (proposal.payload.fill_date || "Next available close") : resolved || decided ? "Decision recorded" : live ? "Your approval is needed" : proposal?.title}</strong>
      <button className="mvp-action primary" onClick={() => { setPlaying(false); setProposalOpen(true); }}>Review proposal</button></div>}
    </div>
    {!embedded && <aside className="agent-room-side terminal-glass agent-room-activity">
      <header><h2>{source ? "Evidence" : "Investigation activity"}</h2>
        {source && <button className="mvp-action" onClick={() => setSource("")}>Close evidence</button>}</header>
      {source ? <div className="agent-room-evidence"><EvidenceView key={source} id={source} debug={debug} />
        {sourceCalculation && <AgentVisual key={sourceCalculation.id} event={sourceCalculation} debug={false} />}
      </div> : <>
      {active && <div className="agent-room-brief agent-current-activity" key={active.id}><small>{live ? finished ? "Run outcome" : "Now" : "Current step · " + active.seq}</small><strong><StepIcon event={active} />{eventLabel(active)}</strong>
        {activeEvidence && <button className="mvp-link" onClick={() => inspectEvidence(activeEvidence)}>{activeEvidence.startsWith("calc:") ? "Inspect calculation" : "Open source"}</button>}
        {debug && <details className="agent-terminal"><summary>Inspect payload</summary><pre>{JSON.stringify(active.payload, null, 2)}</pre></details>}
      </div>}
      <div className="agent-event-scroll">
        <ol className="agent-event-list">{orderedActivity.slice(0, 8).map(activityRow)}</ol>
        {orderedActivity.length > 8 && <details className="desk-disclosure agent-older-steps">
          <summary><span>Earlier steps</span><small>{orderedActivity.length - 8}</small></summary>
          <ol className="agent-event-list" start={9}>{orderedActivity.slice(8).map(activityRow)}</ol>
        </details>}
      </div>
      {debug && <details className="agent-terminal"><summary>Execution log</summary>
        <ol className="agent-events">{visible.map(event => <li key={event.id}>{event.seq} · {event.type} · {event.title}</li>)}</ol>
      </details>}
      </>}
    </aside>}
    </div>
    {!live && !waitingForMode && events.length > 0 && <footer className="mvp-toolbar replay-controls terminal-glass">
        <button className="mvp-action replay-arrow" aria-label="Previous replay step" disabled={index <= 0} onClick={() => jump(index - 1)}>‹</button>
        <button className="mvp-action replay-play" disabled={!events.length} onClick={() => {
          if (index === lastIndex) { jump(0); setPlaying(true); }
          else { setSource(""); setPlaying(!playing); }
        }}>{playing && index < events.length - 1 ? "Pause" : "Play"}</button>
        <input aria-label="Investigation timeline" aria-valuetext={active ? `Event ${active.seq}, ${index + 1} of ${events.length}` : undefined}
          type="range" min="0" max={Math.max(0, lastIndex)} value={Math.max(0, index)} disabled={events.length < 2}
          onChange={event => jump(Number(event.target.value))} />
        <button className="mvp-action replay-arrow" aria-label="Next replay step" disabled={index >= lastIndex} onClick={() => jump(index + 1)}>›</button>
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

function CompactResult({ count, children }: { count: number; children: ReactNode }) {
  const [expanded, setExpanded] = useState(false);
  if (count <= 5) return children;
  return <div className="agent-compact-result" data-expanded={expanded}>
    <div className="agent-compact-body" tabIndex={expanded ? 0 : undefined}>{children}</div>
    <button type="button" className="agent-compact-toggle" aria-expanded={expanded} onClick={() => setExpanded(value => !value)}>
      <span aria-hidden="true" />{expanded ? "Show less" : "Show all " + count}
    </button>
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
          <XAxis dataKey="date" tick={{ fontSize: 10, fill: "var(--terminal-muted)" }} minTickGap={38} axisLine={false} tickLine={false} />
          <YAxis orientation="right" width={62} domain={["auto", "auto"]} axisLine={false} tickLine={false}
            tick={{ fontSize: 10, fill: "var(--terminal-muted)" }} tickFormatter={value => "£" + Math.round(value).toLocaleString("en-GB")} />
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
    return <CompactResult count={output.rows.length}><table className="mvp-table"><thead><tr><th>Holding</th><th>Last close</th><th>1 month</th></tr></thead><tbody>
      {(output.rows as { ticker: string; last_gbp: number; ret_1m: number | null }[]).map(row => <tr key={row.ticker}>
        <th>{row.ticker}</th><td>{gbp.format(row.last_gbp)}</td><td>
          {row.ret_1m == null ? "—" : <div className="agent-return" data-direction={row.ret_1m < 0 ? "down" : "up"}>
            <i style={{ width: Math.min(100, Math.abs(row.ret_1m) * 300) + "%" }} /><span>{pct.format(row.ret_1m)}</span>
          </div>}</td></tr>)}
    </tbody></table></CompactResult>;
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
