import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import AgentAvatar from "../components/AgentAvatar";
import HoldingIssuer from "../components/HoldingIssuer";
import { api, get, mockEvents, MOCK, post } from "../lib/api";
import type { AgentNode, DecisionCard, GateResult, Mode, Notification } from "../lib/types";
import { useResource } from "../lib/useResource";

type Option = {
  label: string; cash_weight: number;
  holdings: { ticker: string; weight: number; purpose: string; why_not_alternatives: string; evidence_ids: string[] }[];
  stats: { cost_gbp: number; vol_annual: number; ocf_weighted: number; turnover: number; max_drawdown_backtest: number | null };
};
type Proposal = {
  id: string; run_id: string; selected: string; status: string; as_of: string; options: Option[];
  decision_card: DecisionCard; uncertainties: string[]; gates: GateResult[];
};
type Evidence = { title: string; source: string; excerpt: string | null; available_at: string; published_at: string | null; url: string | null; data: unknown; quarantined: boolean };

export const gbp = new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP" });
export const pct = new Intl.NumberFormat("en-GB", { style: "percent", maximumFractionDigits: 2 });
export const words = (value: string) => value.replaceAll("_", " ");
const pathFor = (id: string) => "/proposals/" + encodeURIComponent(id);

function recordedFixture(id: string): Proposal {
  const events = mockEvents();
  const created = events.find(event => event.type === "proposal.created" && event.payload.proposal_id === id);
  if (!created?.run_id) throw new Error("This proposal is unavailable in the fixtures.");
  const names = ["recommended", "lower_cost", "lower_risk"];
  const options = events.filter(event => event.type === "calc.result" && event.payload.name === "optimise").map((event, i) => {
    const { weights, cash_weight, ...stats } = event.payload.outputs as Option["stats"] & {
      weights: Record<string, number>; cash_weight: number;
    };
    return { label: names[i], cash_weight, stats,
      holdings: Object.entries(weights).map(([ticker, weight]) => ({ ticker, weight, purpose: "", why_not_alternatives: "", evidence_ids: [] })) };
  });
  return { id, run_id: created.run_id, as_of: created.as_of, selected: "recommended", options, gates: [],
    status: "draft", uncertainties: [], decision_card: { headline: created.title, body: created.purpose ?? "Compare the allocations recorded by the portfolio engine.",
      changes: [], risk_warning: "Recorded paper portfolio · Synthetic fixture", simulated: true } };
}

export function EvidenceView({ id }: { id: string }) {
  const evidence = useResource(id, async signal => {
    if (!MOCK) return get<Evidence>("/evidence/" + encodeURIComponent(id), "", signal);
    const event = mockEvents().find(item => item.type === "calc.result" && "calc:" + item.id === id);
    if (!event) throw new Error("Source unavailable in the fixture recording.");
    return { title: event.title, source: "Recorded calculation", excerpt: null, available_at: event.as_of,
      published_at: null, url: null, data: event.payload, quarantined: false };
  });
  if (!evidence.value) return <p role={evidence.error ? "alert" : "status"}>{evidence.error ?? "Loading source…"}</p>;
  const item = evidence.value;
  const url = item.url && /^https?:\/\//i.test(item.url) ? item.url : null;
  return <div className="evidence-box">
    <strong>{item.title}</strong><p>{item.source} · Available {item.available_at}</p>
    {item.quarantined ? <p>This source was quarantined by the assurance gate.</p> : <>
      {item.excerpt && <blockquote>{item.excerpt}</blockquote>}
      {item.data != null && <pre>{JSON.stringify(item.data, null, 2)}</pre>}
      {url && <a href={url} target="_blank" rel="noreferrer">Open source ↗</a>}
    </>}
  </div>;
}

export function ProposalDialog({ id, mode, close, changed }: {
  id: string; mode?: Mode; close: () => void; changed?: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const response = useResource(id, async signal => MOCK ? recordedFixture(id) : get<Proposal>(pathFor(id), "", signal));
  const proposal = response.value;
  const catalogue = useResource("catalogue", signal => get<{ instruments: { ticker: string; name: string }[] }>("/catalogue", "catalogue", signal));
  const runId = proposal?.run_id;
  const run = useResource(runId ?? "", signal => runId ?
    get<{ agents: AgentNode[] }>("/runs/" + encodeURIComponent(runId), "run_detail", signal) : Promise.resolve(null));
  const [selection, setSelection] = useState("");
  const [source, setSource] = useState("");
  const [outcome, setOutcome] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const option = proposal?.options.find(item => item.label === (selection || proposal.selected)) ?? proposal?.options[0];

  useEffect(() => {
    const element = dialog.current;
    element?.showModal();
    return () => element?.close();
  }, []);

  async function decide(decision: "approve" | "decline") {
    setBusy(true);
    setError("");
    try {
      const result = await post<{ fill_date?: string }>(pathFor(id) + "/" + decision,
        decision === "approve" ? { option: option?.label } : {}, "");
      setOutcome(decision === "approve" ? (result.fill_date ? "Approved · Scheduled for " + result.fill_date : "Approved") : "Portfolio kept as is");
      changed?.();
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  return <dialog className="proposal-modal terminal-glass" ref={dialog} aria-labelledby="proposal-title"
    onCancel={event => { event.preventDefault(); if (!busy) close(); }}>
    <button className="mvp-action proposal-close" aria-label="Close proposal" disabled={busy} onClick={close}>×</button>
    <h1 id="proposal-title">{proposal?.decision_card.headline ?? "Portfolio proposal"}</h1>
    {!proposal ? <p role={response.error ? "alert" : "status"}>{response.error ?? "Loading proposal…"}</p> : <>
      <p className="mvp-muted">{proposal.as_of} · Paper portfolio{mode === "historical" ? " · Recorded demo" : ""}</p>
      {run.value?.agents.length ? <div className="proposal-team">{run.value.agents.filter(agent => agent.status !== "denied").slice(0, 4).map(agent =>
        <div key={agent.agent_id}><AgentAvatar role={agent.role} /><span>{words(agent.role === "lead" ? "Lead agent" : agent.role)}</span></div>)}</div> : null}
      {proposal.decision_card.body && <p className="proposal-message">{proposal.decision_card.body}</p>}
      {option?.label === proposal.selected && proposal.decision_card.changes.length > 0 && <ul className="proposal-gates">{proposal.decision_card.changes.map(change =>
        <li key={change.ticker}>{words(change.action)} {gbp.format(change.amount_gbp)} · {change.ticker}</li>)}</ul>}
      <div className="mvp-toolbar proposal-options" aria-label="Portfolio options">{proposal.options.map(item =>
        <button className="mvp-action" key={item.label} aria-pressed={item === option} disabled={busy || !!outcome}
          onClick={() => { setSelection(item.label); setSource(""); }}>{words(item.label)}</button>)}</div>
      {option && <>
        <div className="proposal-holdings">
          <header><h2>{option.holdings.length} proposed holdings</h2><span>Cash {pct.format(option.cash_weight)} · Est. cost {gbp.format(option.stats.cost_gbp)}</span></header>
          {option.holdings.map(item => {
            const ticker = item.ticker.split(".")[0];
            const fullName = catalogue.value?.instruments.find(instrument => instrument.ticker === item.ticker)?.name ?? ticker;
            const name = fullName.replace(/^(Vanguard|iShares) /, "").replace(/ UCITS ETF\b.*$/, "");
            return <article className="proposal-holding" key={item.ticker}>
              <span className="proposal-issuer"><HoldingIssuer name={fullName} ticker={ticker} /></span>
              <div><strong title={fullName}>{name}</strong><small>{item.ticker}{item.purpose && " · " + item.purpose}</small>
                {item.why_not_alternatives && <details><summary>Why this holding?</summary>{item.why_not_alternatives}</details>}
                {item.evidence_ids.map(id => <button key={id} className="mvp-link" onClick={() => setSource(id)}>Evidence</button>)}</div>
              <div className="proposal-weight"><strong>{pct.format(item.weight)}</strong>
                <span aria-hidden="true"><i style={{ width: pct.format(item.weight) }} /></span></div>
            </article>;
          })}
        </div>
        {option.stats.max_drawdown_backtest != null && <p className="mvp-muted">Historical backtest drawdown {pct.format(option.stats.max_drawdown_backtest)} · Pre-start data</p>}
      </>}
      {source && <EvidenceView key={source} id={source} />}
      {proposal.gates.length > 0 && <ul className="proposal-gates" aria-label="Assurance checks">{proposal.gates.map((gate, index) =>
        <li key={gate.gate + index} title={gate.issues.join(" · ")} data-status={gate.status}>{words(gate.gate)} · {words(gate.status)}</li>)}</ul>}
      {proposal.uncertainties.length > 0 && <ul className="proposal-uncertainties">{proposal.uncertainties.map((item, i) => <li key={i}>{item}</li>)}</ul>}
      <p className="mvp-muted">{proposal.decision_card.risk_warning}</p>
      {outcome && <p role="status">{outcome}</p>}
      {error && <p role="alert" className="mvp-error">{error}</p>}
      <footer className="mvp-toolbar">
        <Link to={"/runs/" + encodeURIComponent(proposal.run_id)} className="mvp-action" onClick={close}>Open investigation</Link>
        {!MOCK && mode === "live" && proposal.status === "awaiting_approval" && !outcome && <>
          <button className="mvp-action" disabled={busy} onClick={() => void decide("decline")}>Decline · Keep current portfolio</button>
          <button className="mvp-action primary" disabled={busy || !option} onClick={() => void decide("approve")}>Approve</button>
        </>}
      </footer>
    </>}
  </dialog>;
}

export function DecisionList({ mode }: { mode?: Mode }) {
  const [revision, refresh] = useState(0);
  const [selected, select] = useState("");
  const [marking, setMarking] = useState("");
  const [error, setError] = useState("");
  const resource = useResource("notices:" + revision, signal => get<{ items: Notification[] }>("/notifications", "notifications", signal));

  async function markRead(id: string) {
    setMarking(id);
    setError("");
    try { await api.markNotificationRead(id); refresh(n => n + 1); }
    catch (e) { setError((e as Error).message); }
    finally { setMarking(""); }
  }

  return <div className="mvp-page mvp-enter">
    <h1>Decisions and activity</h1>
    {resource.error && <p role="alert">{resource.error}</p>}
    {error && <p role="alert">{error}</p>}
    {resource.value && (["decision", "digest", "coverage"] as const).map((kind, index) =>
      <section className="terminal-glass mvp-panel" key={kind}>
        <h2>{["Decisions", "Review digest", "Data coverage"][index]}</h2>
        {resource.value?.items.filter(item => item.kind === kind).map(item => <article className="notice-row" key={item.id}>
          <div><strong>{item.title}</strong><p>{item.body}</p><small>{item.created_at.slice(0, 10)}</small></div>
          <div className="mvp-toolbar">
            {item.proposal_id && <button className="mvp-action primary" onClick={() => select(item.proposal_id ?? "")}>Review proposal</button>}
            {item.run_id && <Link className="mvp-action" to={"/runs/" + encodeURIComponent(item.run_id)}>Open investigation</Link>}
            {!item.read && !MOCK && <button className="mvp-action" disabled={!!marking} onClick={() => void markRead(item.id)}>Mark as read</button>}
          </div>
        </article>)}
        {!resource.value?.items.some(item => item.kind === kind) && <p className="mvp-muted">Nothing here yet.</p>}
      </section>)}
    {selected && <ProposalDialog key={selected} id={selected} mode={mode} close={() => select("")} changed={() => refresh(n => n + 1)} />}
  </div>;
}
