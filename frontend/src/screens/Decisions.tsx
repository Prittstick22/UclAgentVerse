import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import AgentAvatar from "../components/AgentAvatar";
import HoldingIssuer from "../components/HoldingIssuer";
import FinanceTerm from "../components/FinanceTerm";
import { finance } from "../lib/financeTerms";
import { publicNarrative } from "../lib/investigation";
import { AssuranceStrip, focusInProposal, ProposalBacktest, ProposalEvidenceDrawer, proposalCalculations } from "../components/ProposalEvidence";
export { EvidenceView } from "../components/ProposalEvidence";
import { api, get, mockEvents, MOCK, post } from "../lib/api";
import type { AgentEvent, AgentNode, DecisionCard, GateResult, Mode, Notification } from "../lib/types";
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
export const gbp = new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP" });
export const pct = new Intl.NumberFormat("en-GB", { style: "percent", maximumFractionDigits: 2 });
export const words = (value: string) => value.replaceAll("_", " ");
const pathFor = (id: string) => "/proposals/" + encodeURIComponent(id);

export function recordedFixture(id: string): Proposal {
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

export function ProposalDialog({ id, mode, close, changed }: {
  id: string; mode?: Mode; close: () => void; changed?: () => void;
}) {
  const navigate = useNavigate();
  const dialog = useRef<HTMLDialogElement>(null);
  const response = useResource(id, async signal => MOCK ? recordedFixture(id) : get<Proposal>(pathFor(id), "", signal));
  const proposal = response.value;
  const catalogue = useResource("catalogue", signal => get<{ instruments: { ticker: string; name: string }[] }>("/catalogue", "catalogue", signal));
  const runId = proposal?.run_id;
  const run = useResource(runId ?? "", signal => runId ?
    get<{ agents: AgentNode[] }>("/runs/" + encodeURIComponent(runId), "run_detail", signal) : Promise.resolve(null));
  const [selection, setSelection] = useState("");
  const events = useResource(runId ?? "", signal => !runId ? Promise.resolve({ items: [] as AgentEvent[] }) :
    MOCK ? Promise.resolve({ items: mockEvents() }) :
      get<{ items: AgentEvent[] }>("/runs/" + encodeURIComponent(runId) + "/events?format=json", "", signal));
  const [source, setSource] = useState<{ id: string; seq?: number; trigger: HTMLButtonElement }>();
  const evidenceReturnFocus = useRef<HTMLButtonElement>();
  const [error, setError] = useState("");
  const [pendingDecision, setPendingDecision] = useState<"approve" | "decline">();
  const busy = pendingDecision !== undefined;
  const actionable = !MOCK && mode === "live" && proposal?.status === "awaiting_approval";
  const option = proposal?.options.find(item => item.label === (selection || proposal.selected)) ?? proposal?.options[0];
  const changes = option?.label === proposal?.selected ? proposal?.decision_card.changes ?? [] : [];
  const changesByTicker = new Map(changes.map(change => [change.ticker, change]));
  const exits = changes.filter(change => !option?.holdings.some(item => item.ticker === change.ticker));
  const { selection: selectedFigures, allocation } = option && events.value ?
    proposalCalculations(events.value.items, id, option.label, option.holdings) : {};
  const calculation = selectedFigures ?? allocation;

  function closeEvidence() {
    evidenceReturnFocus.current = source?.trigger;
    setSource(undefined);
  }

  useLayoutEffect(() => {
    const trigger = evidenceReturnFocus.current;
    if (source || !trigger) return;
    evidenceReturnFocus.current = undefined;
    if (trigger.isConnected) focusInProposal(trigger);
  }, [source]);

  useEffect(() => {
    const element = dialog.current;
    element?.showModal();
    return () => element?.close();
  }, []);

  async function decide(decision: "approve" | "decline") {
    if (busy || !actionable) return;
    setPendingDecision(decision);
    setError("");
    try {
      const result = await post<{ fill_date?: string }>(pathFor(id) + "/" + decision,
        decision === "approve" ? { option: option?.label } : {}, "");
      const proposalNotice = decision === "approve"
        ? "Proposal approved. Paper trades are queued for " + (result.fill_date ?? "the next available close") + "."
        : "Proposal declined. Your portfolio stays as it is.";
      close();
      changed?.();
      navigate("/", { replace: true, state: { proposalNotice } });
    } catch (e) { setError((e as Error).message); }
    finally { setPendingDecision(undefined); }
  }

  return <dialog className="proposal-modal terminal-glass" ref={dialog} aria-labelledby="proposal-title"
    onCancel={event => { event.preventDefault(); if (!busy) close(); }}>
    <button className="mvp-action proposal-close" aria-label="Close proposal" disabled={busy} onClick={close}>×</button>
    <h1 id="proposal-title">{publicNarrative(proposal?.decision_card.headline) || "Portfolio proposal"}</h1>
    {!proposal ? <p role={response.error ? "alert" : "status"}>{response.error ?? "Loading proposal…"}</p> : <>
      <p className="mvp-muted">{proposal.as_of} · Paper portfolio{mode === "historical" ? " · Recorded demo" : ""}</p>
      {run.value?.agents.length ? <div className="proposal-team">{run.value.agents.filter(agent => agent.status !== "denied").slice(0, 4).map(agent =>
        <div key={agent.agent_id}><AgentAvatar role={agent.role} /><span>{words(agent.role === "lead" ? "Lead agent" : agent.role)}</span></div>)}</div> : null}
      {proposal.decision_card.body && <p className="proposal-message">{publicNarrative(proposal.decision_card.body)}</p>}
      <AssuranceStrip results={proposal.gates} draft={proposal.status === "draft" && !MOCK} />
      <div className="mvp-toolbar proposal-options" aria-label="Portfolio options">{proposal.options.map(item =>
        <button className="mvp-action" key={item.label} aria-pressed={item === option} disabled={busy}
          onClick={() => { setSelection(item.label); setSource(undefined); }}>{words(item.label)}</button>)}
        {calculation && <button className="mvp-action accent compact" type="button"
          onClick={event => setSource({ id: "calc:" + calculation.id, seq: calculation.seq, trigger: event.currentTarget })}>Show calculations</button>}
      </div>
      {source && <ProposalEvidenceDrawer source={source} runId={proposal.run_id} close={closeEvidence} />}
      {option && <>
        <div className="proposal-holdings">
          <header><h2>{option.holdings.length} proposed holdings</h2><span>Cash {pct.format(option.cash_weight)} · <FinanceTerm name="Est. trading cost" help={finance.tradingCost} /> {gbp.format(option.stats.cost_gbp)}</span></header>
          {option.holdings.map(item => {
            const ticker = item.ticker.split(".")[0];
            const change = changesByTicker.get(item.ticker);
            const fullName = catalogue.value?.instruments.find(instrument => instrument.ticker === item.ticker)?.name ?? ticker;
            const name = fullName.replace(/^(Vanguard|iShares) /, "").replace(/ UCITS ETF\b.*$/, "");
            return <article className="proposal-holding" key={item.ticker}>
              <span className="proposal-issuer"><HoldingIssuer name={fullName} ticker={item.ticker} /></span>
              <div><strong title={fullName}>{name}</strong><small>{item.ticker}{item.purpose && " · " + item.purpose}</small>
                {item.why_not_alternatives && <details><summary>Why this holding?</summary>{item.why_not_alternatives}</details>}
                {item.evidence_ids.map((id, index) => <button key={id} className="mvp-action accent compact" type="button"
                  aria-label={"Supporting evidence " + (index + 1) + " for " + ticker}
                  onClick={event => setSource({ id, trigger: event.currentTarget })}>
                  Evidence{item.evidence_ids.length > 1 ? " " + (index + 1) : ""}
                </button>)}</div>
              <div className="proposal-weight"><strong>{pct.format(item.weight)}</strong>
                <span aria-hidden="true"><i style={{ width: pct.format(item.weight) }} /></span>
                {change && <small>{change.action === "buy" ? "Buy" : "Sell"} {gbp.format(change.amount_gbp)}</small>}</div>
            </article>;
          })}
          {exits.length > 0 && <section className="proposal-exits"><h3>Positions to close</h3>
            <ul>{exits.map(change => <li key={change.ticker}><span>{change.ticker.split(".")[0]}</span>
              <strong>{change.action === "sell" ? "Sell" : "Buy"} {gbp.format(change.amount_gbp)}</strong></li>)}</ul>
          </section>}
        </div>
        <ProposalBacktest event={allocation} asOf={proposal.as_of} />
        {option.stats.max_drawdown_backtest != null && <p className="mvp-muted"><FinanceTerm name="Biggest historical drop" help={finance.drawdown} /> {pct.format(option.stats.max_drawdown_backtest)} · Simulated</p>}
      </>}
      {option && events.value && !calculation && <p className="mvp-muted">This recording has no calculation for this option.</p>}
      {proposal.uncertainties.length > 0 && <ul className="proposal-uncertainties">{proposal.uncertainties.map((item, i) => <li key={i}>{item}</li>)}</ul>}
      <p className="mvp-muted">{proposal.decision_card.risk_warning}</p>
      <footer className="mvp-toolbar">
        {pendingDecision && <p className="proposal-decision-status" role="status">
          {pendingDecision === "approve" ? "Saving approval…" : "Saving decline…"}
        </p>}
        {error && <p role="alert" className="proposal-decision-status mvp-error">{error}</p>}
        {!busy && <Link to={"/runs/" + encodeURIComponent(proposal.run_id) + "?replay=1"} className="mvp-action" onClick={close}>Replay investigation</Link>}
        {actionable ? <>
          <button className="mvp-action" disabled={busy} onClick={() => void decide("decline")}>Decline · Keep current portfolio</button>
          <button className="mvp-action primary" disabled={busy || !option} onClick={() => void decide("approve")}>Approve</button>
        </> : mode === "live" && <Link to="/" className="mvp-action primary" onClick={close}>Back to Home</Link>}
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
    <h1><span data-tour-target="decisions-intro">Decisions and activity</span></h1>
    {resource.error && <p role="alert">{resource.error}</p>}
    {error && <p role="alert">{error}</p>}
    {resource.value && (["decision", "digest", "coverage"] as const).map((kind, index) =>
      <section className="terminal-glass glass-feedback mvp-panel" key={kind}>
        <h2>{["Decisions", "Review digest", "Data coverage"][index]}</h2>
        {resource.value?.items.filter(item => item.kind === kind).map(item => <article className="notice-row" key={item.id}>
          <div><strong>{publicNarrative(item.title)}</strong><p>{publicNarrative(item.body)}</p><small>{item.created_at.slice(0, 10)}</small></div>
          <div className="mvp-toolbar">
            {item.proposal_id && <button className="mvp-action primary" data-tour-target="proposal" onClick={() => select(item.proposal_id ?? "")}>Review proposal</button>}
            {item.run_id && <Link className="mvp-action" to={"/runs/" + encodeURIComponent(item.run_id) + "?replay=1"}>
              {item.kind === "decision" ? "Why?" : "Open investigation"}
            </Link>}
            {!item.read && !MOCK && <button className="mvp-action" disabled={!!marking} onClick={() => void markRead(item.id)}>Mark as read</button>}
          </div>
        </article>)}
        {!resource.value?.items.some(item => item.kind === kind) && <p className="mvp-muted">Nothing here yet.</p>}
      </section>)}
    {selected && <ProposalDialog key={selected} id={selected} mode={mode} close={() => select("")} />}
  </div>;
}
