import { useState } from "react";
import { Link } from "react-router-dom";
import type { OrderChange, PortfolioRebalances, RunSummary } from "../lib/types";
import { outcomeLabel } from "../lib/investigation";
import AgentAvatar from "./AgentAvatar";
import HoldingIssuer from "./HoldingIssuer";
import FinanceTerm from "./FinanceTerm";
import { finance } from "../lib/financeTerms";
import ScrollArrivalList from "./ScrollArrivalList";
import "./investigation-overview.css";

type Run = Omit<RunSummary, "agents">;
type Fill = PortfolioRebalances["items"][number];
const date = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
const gbp = new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP" });
const weight = new Intl.NumberFormat("en-GB", { style: "percent", maximumFractionDigits: 2 });
const points = new Intl.NumberFormat("en-GB", { maximumFractionDigits: 2, signDisplay: "exceptZero" });
const name = (ticker: string) => ticker.split(".")[0];
const runPath = (id: string) => "/runs/" + encodeURIComponent(id);
const runLink = (run: Run) => runPath(run.run_id) + (run.status === "running" ? "?live=1" : "?replay=1");
const fillKey = (fill: Fill) => fill.run_id + ":" + fill.date;
const outcomeKey = (run: Run) => run.status === "completed" ? run.outcome || "other" : "other";
const stateLabel = (run: Run) => run.status === "running" ? "Live investigation" : run.status === "failed" ? "Investigation stopped" :
  run.status === "cancelled" ? "Investigation cancelled" : outcomeLabel(run.outcome) || "Investigation completed";

function changeLabel(change: OrderChange) {
  if (change.from_weight <= 0 && change.to_weight > 0) return "Added";
  if (change.from_weight > 0 && change.to_weight <= 0) return "Exited";
  return change.action === "sell" ? "Sold" : "Bought";
}

export default function InvestigationOverview({ runs, rebalances, changesUnavailable }: {
  runs: Run[]; rebalances?: PortfolioRebalances; changesUnavailable: boolean;
}) {
  const ordered = runs.slice().reverse();
  const completed = runs.filter(run => run.status === "completed");
  const latest = ordered[0];
  const ids = new Set(runs.map(run => run.run_id));
  const changes = (rebalances?.items ?? []).filter(item => ids.has(item.run_id)).sort((a, b) => b.date.localeCompare(a.date));
  const changesByRun = new Map<string, OrderChange[]>();
  for (const fill of changes) changesByRun.set(fill.run_id, [...(changesByRun.get(fill.run_id) ?? []), ...fill.changes]);
  const [selection, setSelection] = useState("");
  const fill = changes.find(item => fillKey(item) === selection) ?? changes[0];
  const kept = completed.filter(run => run.outcome === "maintain").length;
  const proposals = completed.filter(run => run.outcome === "adjust").length;

  return <div className="investigation-insights">
    <section className="terminal-glass glass-feedback mvp-panel investigation-decision" aria-label="Latest investigation">
      <header><h2>Latest investigation</h2><time dateTime={latest.as_of}>{date.format(new Date(latest.as_of))}</time></header>
      <Link className="investigation-latest glass-feedback" to={runLink(latest)}>
        <AgentAvatar role="lead" /><div><strong>{stateLabel(latest)}</strong><span>{latest.trigger_text || "Portfolio investigation"}</span></div>
        <svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" aria-hidden="true"><path d="M3 8h9m-4-4 4 4-4 4" /></svg>
      </Link>
      <dl className="investigation-summary">
        <div><dt>Completed</dt><dd>{completed.length}</dd></div>
        <div><dt>Kept as is</dt><dd>{kept}</dd></div>
        <div><dt>Changes proposed</dt><dd>{proposals}</dd></div>
      </dl>
    </section>
    <section className="terminal-glass glass-feedback mvp-panel investigation-changes" aria-label="Filled portfolio changes">
      <header><h2>Filled portfolio changes</h2>
        {changes.length > 1 && <select className="terminal-field" aria-label="Filled trade batch" value={fillKey(fill)}
          onChange={event => setSelection(event.target.value)}>{changes.map(item => <option key={fillKey(item)} value={fillKey(item)}>
            {date.format(new Date(item.date))} · {item.trigger_kind === "construction" ? "Starting portfolio" : "Rebalance"}
          </option>)}</select>}
      </header>
      {fill ? <>
        <p className="investigation-change-context"><span>{date.format(new Date(fill.date))} · {fill.trigger_kind === "construction" ? "Starting portfolio" : "Rebalance"}</span>
          <Link className="mvp-action compact" to={runPath(fill.run_id) + "?replay=1"}>View investigation</Link></p>
        <div className="investigation-change-table" role="region" aria-label="Holdings that changed" tabIndex={0}>
          <table className="mvp-table"><thead><tr><th scope="col">Holding</th><th scope="col"><FinanceTerm name="Weight before → after" help={finance.weightChange} /></th><th scope="col"><FinanceTerm name="Traded" help={finance.traded} /></th></tr></thead>
            <tbody>{fill.changes.map((change, i) => <tr key={change.ticker + i}>
              <th scope="row"><span className="investigation-holding"><HoldingIssuer ticker={change.ticker} /><span>
                {name(change.ticker)} <small>{changeLabel(change)}</small></span></span></th>
              <td><span>{weight.format(change.from_weight)} → <strong>{weight.format(change.to_weight)}</strong></span>
                <small>{points.format((change.to_weight - change.from_weight) * 100)} <abbr title="Percentage points">pp</abbr></small></td>
              <td>{gbp.format(change.amount_gbp)}</td>
            </tr>)}</tbody></table>
        </div>
        <p className="investigation-change-context"><span>{fill.changes.length} {fill.changes.length === 1 ? "holding" : "holdings"}</span>
          <span>Trading cost {gbp.format(fill.cost_gbp)}</span></p>
      </> : <p className="mvp-muted">{changesUnavailable ? "Filled portfolio changes are unavailable." :
        rebalances ? "No filled changes are recorded for these investigations." : "Loading filled portfolio changes…"}</p>}
    </section>
    <section className="investigation-gallery" aria-label="Investigations">
      <h2>Investigations</h2>
      <ScrollArrivalList className="investigation-card-grid">
        {ordered.map(run => {
          const filled = changesByRun.get(run.run_id) ?? [];
          const holdings = [...new Set(filled.map(change => change.ticker))];
          return <li key={run.run_id}>
            <Link className="investigation-card glass-feedback" to={runLink(run)}>
              <div className="investigation-card-cover" data-outcome={outcomeKey(run)}>
                {holdings.length ? <div className="investigation-cover-holdings" aria-hidden="true">
                  {holdings.slice(0, 3).map(ticker => <HoldingIssuer key={ticker} ticker={ticker} />)}
                  {holdings.length > 3 && <small>+{holdings.length - 3}</small>}
                </div> : <AgentAvatar role="lead" />}
                <span>{stateLabel(run)}</span>
              </div>
              <div className="investigation-card-copy"><h3>{run.trigger_text || "Portfolio investigation"}</h3>
                <p><time dateTime={run.as_of}>{date.format(new Date(run.as_of))}</time>
                  {holdings.length > 0 && " · " + holdings.length + (holdings.length === 1 ? " holding changed" : " holdings changed")}</p>
              </div>
            </Link>
          </li>;
        })}
      </ScrollArrivalList>
    </section>
  </div>;
}
