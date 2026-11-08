import { useId, useLayoutEffect, useRef } from "react";
import { Link } from "react-router-dom";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { chartDateTick, chartValueTick, moneyAxisWidth } from "../lib/chartLabels";
import { get, mockEvents, MOCK } from "../lib/api";
import { publicNarrative } from "../lib/investigation";
import type { AgentEvent, Badge, GateName, GateResult, GateStatus } from "../lib/types";
import { useResource } from "../lib/useResource";
import "./proposal-evidence.css";

type Evidence = {
  title: string; source: string; excerpt: string | null; available_at: string; published_at: string | null;
  url: string | null; data: unknown; quarantined: boolean;
};
const money = new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP" });
const percent = new Intl.NumberFormat("en-GB", { style: "percent", maximumFractionDigits: 2 });
const record = (value: unknown): Record<string, unknown> =>
  value != null && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
const number = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value);
const calculationId = (event: AgentEvent) => "calc:" + event.id;

const currencyRows: Record<string, string> = {
  capital_gbp: "Portfolio size", invested_gbp: "Invested", cash_gbp: "Cash", decision_cost_gbp: "Trading cost in the summary",
  cost_gbp: "Estimated trading cost", annual_fund_fees_gbp: "Estimated annual fund fees", buy_total_gbp: "Total to buy",
  sell_total_gbp: "Total to sell", amount_moved_gbp: "Amount moved",
};
const percentRows: Record<string, string> = {
  cash_weight: "Cash weight", vol_annual: "Estimated annual volatility", max_drawdown_backtest: "Historical worst drawdown",
  max_drawdown: "Historical worst drawdown", ocf_weighted: "Annual fund fee rate", turnover: "Estimated turnover",
  decision_turnover: "Turnover in the summary", total_return: "Historical return",
};
const countRows: Record<string, string> = {
  holdings_count: "Proposed holdings", trade_count: "Proposed trades", lookback_days: "Trading days in the analysis", history_days: "Trading days available",
};

function CalculationDetails({ data }: { data: unknown }) {
  const frame = record(data);
  const inputs = record(frame.inputs);
  const outputs = record(frame.outputs);
  const figures = { ...inputs, ...outputs };
  const rows: [string, string][] = [];
  for (const [labels, format] of [[currencyRows, money.format], [percentRows, percent.format], [countRows, String]] as const) {
    for (const [key, label] of Object.entries(labels)) {
      const value = figures[key];
      if (number(value)) rows.push([label, format(value)]);
    }
  }
  const weights = Object.entries(record(outputs.weights ?? inputs.weights)).filter((row): row is [string, number] => number(row[1]));
  const trades = Array.isArray(outputs.trades) ? outputs.trades.map(record).filter(trade =>
    typeof trade.ticker === "string" && (trade.action === "buy" || trade.action === "sell") && number(trade.amount_gbp)) : [];
  if (!rows.length && !weights.length && !trades.length) return null;

  return <div className="evidence-calculation">
    {rows.length > 0 && <dl>{rows.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>}
    {weights.length > 0 && <details><summary>Holding weights</summary>
      <dl>{weights.map(([ticker, value]) => <div key={ticker}><dt>{ticker}</dt><dd>{percent.format(value)}</dd></div>)}</dl>
    </details>}
    {trades.length > 0 && <details><summary>Proposed trade amounts</summary>
      <dl>{trades.map((trade, index) => <div key={String(trade.ticker) + index}>
        <dt>{trade.action === "buy" ? "Buy" : "Sell"} {String(trade.ticker)}</dt><dd>{money.format(Number(trade.amount_gbp))}</dd>
      </div>)}</dl>
    </details>}
  </div>;
}

export function EvidenceView({ id, debug = false }: { id: string; debug?: boolean }) {
  const evidence = useResource(id, async signal => {
    if (!MOCK) return get<Evidence>("/evidence/" + encodeURIComponent(id), "", signal);
    const event = mockEvents().find(item => item.type === "calc.result" && calculationId(item) === id);
    if (!event) throw new Error("This source is unavailable in the fixture recording.");
    return { title: event.title, source: "Recorded calculation · Synthetic fixture", excerpt: null, available_at: event.as_of,
      published_at: null, url: null, data: event.payload, quarantined: false };
  });
  if (!evidence.value) return <p role={evidence.error ? "alert" : "status"}>{evidence.error ?? "Loading evidence…"}</p>;
  const item = evidence.value;
  const url = item.url && /^https?:\/\//i.test(item.url) ? item.url : null;
  const generated = /^(?:case|proposal|calc):/.test(id);
  const source = ({ agent_investment_case: "Investment case", agent_proposal: "Portfolio proposal" } as Record<string, string>)[item.source] ?? item.source;
  const excerpt = generated ? publicNarrative(item.excerpt) : item.excerpt;
  return <div className="evidence-box">
    <strong>{generated ? publicNarrative(item.title) : item.title}</strong>
    <p className="evidence-source">{source}
      {item.published_at && <> · Published <time dateTime={item.published_at}>{item.published_at.slice(0, 10)}</time></>}
      {" · Available "}<time dateTime={item.available_at}>{item.available_at.slice(0, 10)}</time>
    </p>
    {item.quarantined ? <p>This source was quarantined by the assurance gate.</p> : <>
      {excerpt && <blockquote>{excerpt}</blockquote>}
      {id.startsWith("calc:") && <CalculationDetails data={item.data} />}
      {item.data != null && debug && import.meta.env.DEV && <pre>{JSON.stringify(item.data, null, 2)}</pre>}
      {url && <a className="mvp-action accent compact" href={url} target="_blank" rel="noreferrer">Open source ↗</a>}
    </>}
  </div>;
}

const gates: [GateName, string][] = [
  ["injection_guard", "Source safety"], ["evidence", "Evidence"], ["numbers", "Numbers"],
  ["mandate", "Mandate"], ["critic", "Critic"], ["compliance", "Compliance"], ["qa", "Final review"],
];
const statusLabels: Record<GateStatus, string> = {
  pending: "Pending", pass: "Passed", pass_with_flags: "Passed with notes", fail: "Failed", skipped: "Skipped",
};

export function AssuranceStrip({ results, draft }: { results: GateResult[]; draft: boolean }) {
  const id = useId();
  const byGate = new Map(results.map(result => [result.gate, result]));
  const checks: [GateName, string][] = [...gates];
  if (byGate.has("revalidation")) checks.push(["revalidation", "Revalidation"]);
  return <ul className="proposal-gates evidence-gates" aria-label="Assurance checks">
    {checks.map(([gate, label]) => {
      const result = byGate.get(gate);
      const status = result?.status ?? (draft ? "pending" : "skipped");
      const description = result ? statusLabels[status] : draft ? "Pending" : "No recorded result";
      const detail = result?.issues.length ? result.issues.join(" · ") : null;
      return <li key={gate} data-status={status}>
        {detail ? <details><summary title={detail} aria-describedby={id + gate}>{label} · {description}</summary>
          <p id={id + gate}>{detail}</p></details> : <span>{label} · {description}</span>}
      </li>;
    })}
  </ul>;
}

const badgeLabels: Record<Badge, string> = {
  source_retrieved: "Source retrieved", claim_supported: "Claim supported", relationship_uncertain: "Relationship uncertain",
  calculation_recomputed: "Calculation recomputed", judgement_uncertain: "Judgement uncertain",
};

export function FindingBadges({ finding, events }: { finding: AgentEvent; events: AgentEvent[] }) {
  const citations = new Set(finding.evidence_ids);
  const supportedEvent = events.find(event => event.seq > finding.seq && event.type === "gate.verdict"
    && event.payload.gate === "evidence" && event.payload.status === "pass");
  const badges: Badge[] = [];
  if (events.some(event => event.seq <= finding.seq && (
    event.type === "source.inspect" || (event.type === "tool.result" &&
    ["search_news", "search_filings", "web_search"].includes(String(event.payload.tool)))
  ) && event.evidence_ids.some(id => citations.has(id)))) badges.push("source_retrieved");
  if (citations.size && supportedEvent && !finding.payload.view_dropped && !events.some(event =>
    event.type === "content.quarantined" && event.evidence_ids.some(id => citations.has(id)))) badges.push("claim_supported");
  if (events.some(event => event.type === "gate.verdict" && event.payload.gate === "numbers" &&
    (event.payload.status === "pass" || event.payload.status === "pass_with_flags") &&
    event.evidence_ids.some(id => id.startsWith("calc:") && citations.has(id)))) badges.push("calculation_recomputed");
  if (finding.payload.confidence === "low" || (Array.isArray(finding.payload.uncertainties) && finding.payload.uncertainties.length > 0)) {
    badges.push("judgement_uncertain");
  }
  return badges.length ? <ul className="finding-badges" aria-label="Finding evidence badges">
    {badges.map(badge => <li key={badge} data-badge={badge}>{badgeLabels[badge]}</li>)}
  </ul> : null;
}

export function proposalCalculations(
  events: AgentEvent[], proposalId: string, optionLabel: string, holdings: { ticker: string; weight: number }[],
) {
  const created = events.find(event => event.type === "proposal.created" && event.payload.proposal_id === proposalId);
  if (!created) return {};
  const available = events.filter(event => event.type === "calc.result" && event.seq <= created.seq).reverse();
  const selection = available.find(event => created.evidence_ids.includes(calculationId(event))
    && event.payload.name === "proposal_numbers" && record(event.payload.inputs).option === optionLabel);
  const allocation = available.find(event => {
    if (event.payload.name !== "optimise" || record(event.payload.inputs).variant !== optionLabel) return false;
    const weights = record(record(event.payload.outputs).weights);
    return Object.keys(weights).length === holdings.length && holdings.every(({ ticker, weight }) => weights[ticker] === weight);
  });
  return { selection, allocation };
}

export function focusInProposal(target: HTMLElement, alignTop = false) {
  const dialog = target.closest("dialog");
  const holdings = target.closest<HTMLElement>(".proposal-holdings");
  for (const container of [holdings, dialog]) {
    if (!container) continue;
    const viewportTop = container.getBoundingClientRect().top + container.clientTop;
    const footer = container === dialog ? dialog.querySelector("footer") : null;
    const viewportBottom = Math.min(viewportTop + container.clientHeight, footer?.getBoundingClientRect().top ?? Infinity);
    const { top, bottom } = target.getBoundingClientRect();
    const offset = alignTop || top < viewportTop + 8 ? top - viewportTop - 8 : Math.max(0, bottom - viewportBottom + 8);
    if (offset) container.scrollBy({ top: offset, behavior: "instant" });
  }
  target.focus({ preventScroll: true });
}

export function ProposalEvidenceDrawer({ source, runId, close }: {
  source: { id: string; seq?: number }; runId: string; close: () => void;
}) {
  const heading = useRef<HTMLHeadingElement>(null);
  useLayoutEffect(() => {
    if (heading.current) focusInProposal(heading.current, true);
  }, [source]);
  const { id, seq } = source;
  const calculation = id.startsWith("calc:");
  return <section className="proposal-evidence-drawer" aria-label="Proposal evidence">
    <header><h2 ref={heading} tabIndex={-1}>{calculation ? "Calculation evidence" : "Supporting source"}</h2>
      <button className="mvp-action" type="button" onClick={close}>Close evidence</button></header>
    <EvidenceView id={id} key={id} />
    {seq && <Link to={"/runs/" + encodeURIComponent(runId) + "?seq=" + seq} className="mvp-action accent compact" onClick={close}>
      Open calculation in replay ↗
    </Link>}
  </section>;
}

export function ProposalBacktest({ event, asOf }: { event?: AgentEvent; asOf: string }) {
  const values = record(event?.payload.outputs).backtest_nav;
  const points = Array.isArray(values) ? values.flatMap(row =>
    Array.isArray(row) && typeof row[0] === "string" && row[0] <= asOf && number(row[1]) ? [{ date: row[0], value: row[1] }] : []) : [];
  if (points.length < 2) return null;
  const label = "Historical backtest · Not a forecast";
  const short = (day: string) => new Intl.DateTimeFormat("en-GB", { month: "short", year: "2-digit", timeZone: "UTC" }).format(new Date(day));
  return <figure className="proposal-backtest">
    <figcaption><strong>{label}</strong><span>Pre-investment prices · {points[0].date} to {points.at(-1)?.date}</span></figcaption>
    <div role="img" aria-label={label + ", simulated portfolio value in pounds"}>
      <ResponsiveContainer width="100%" height={145}>
        <AreaChart data={points} margin={{ top: 8, right: 10, bottom: 0, left: 0 }}>
          <CartesianGrid vertical={false} stroke="var(--terminal-edge)" />
          <XAxis dataKey="date" tickFormatter={short} interval="preserveStartEnd" minTickGap={24} tickLine={false} axisLine={false} tick={chartDateTick} />
          <YAxis width={moneyAxisWidth} tickCount={4} domain={["auto", "auto"]} tickFormatter={(value: number) => "£" + Math.round(value).toLocaleString("en-GB")}
            tickLine={false} axisLine={false} tick={chartValueTick} />
          <Tooltip formatter={(value: number) => [money.format(value), "Simulated value"]} />
          <Area dataKey="value" stroke="var(--terminal-accent)" fill="var(--terminal-accent)" fillOpacity={0.14} isAnimationActive={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  </figure>;
}
