import { useMemo, useState, type CSSProperties } from "react";
import { Link } from "react-router-dom";
import {
  CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis,
} from "recharts";
import Term from "../components/FinanceTerm";
import { chartDateTick, chartValueTick, moneyAxisWidth, percentAxisWidth } from "../lib/chartLabels";
import { get, MOCK } from "../lib/api";
import { investigationTitle } from "../lib/investigation";
import {
  benchmarkNames, joinBenchmarkSeries, sp500Key, sp500ReturnSeries, sp500Ticker, type Benchmarks,
} from "../lib/benchmarkData";
import type { HoldingPrices, PortfolioRebalances } from "../lib/types";
import { useResource } from "../lib/useResource";
import { gbp, pct, words } from "./Decisions";
import "./benchmarks.css";

const palette = ["#9cbff3", "#b3a2d6", "#86b8bb", "#d3ae89", "#a2a8bf", "#cd98aa"];
const marketColor = "#e4b876";
const dateShort = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });
const dateLong = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
const signedPct = new Intl.NumberFormat("en-GB", { style: "percent", maximumFractionDigits: 2, signDisplay: "exceptZero" });
const pounds = new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP", maximumFractionDigits: 0 });
const label = (name: string) => benchmarkNames[name] ?? words(name);
const referenceHelp = "Vanguard’s VUAG fund tracks the S&P 500 index of large US companies. This is its adjusted price change in pounds over the same dates, before any simulated trading costs.";
const strategyHelp: Record<string, string> = {
  ours: "The paper portfolio built and reviewed by the agents.",
  ours_no_agents: "The same investing rules without the agents’ research or decisions.",
  ours_no_forecast: "The same system with its short-term return estimates switched off.",
  buy_and_hold: "Keeps the starting investments and adds new money without resetting their proportions.",
  quarterly_rebalance: "Returns investments to their target proportions when a new quarter starts.",
  global_etf: "Puts the portfolio in one fund that holds shares around the world.",
  mechanical_5pct: "Uses the same targets and resets them when the automatic 5% trigger fires.",
  [sp500Key]: referenceHelp,
};
const metrics = [
  { id: "total_return", label: "Return", help: "How much the investments gained or lost over the period, excluding new deposits.", format: signedPct.format },
  { id: "vol_annual", label: "Volatility", help: "How much returns moved up and down, scaled to one year. A higher number means larger swings.", format: pct.format },
  { id: "max_drawdown", label: "Worst drop", help: "The biggest fall from an earlier high during the period. Also called drawdown.", format: pct.format },
  { id: "sharpe", label: "Sharpe", help: "Return relative to how much it fluctuated. This calculation assumes a zero return on a risk-free investment.", format: (value: number) => value.toFixed(2) },
  { id: "turnover", label: "Turnover", help: "How much of the portfolio was traded, relative to its average value. Opening purchases are excluded.", format: pct.format },
  { id: "costs_gbp", label: "Trading costs", help: "Estimated charges for placing the simulated trades.", format: gbp.format },
  { id: "trades", label: "Trades", help: "The number of individual buys and sells that went through.", format: (value: number) => value.toLocaleString("en-GB") },
] as const;
const comparisonMetrics = [metrics[0], metrics[2], metrics[5]] as const;

function ComparisonBars({ rows, metric }: {
  rows: { name: string; value: number; color: string }[]; metric: (typeof comparisonMetrics)[number];
}) {
  const max = Math.max(0, ...rows.map(({ value }) => value));
  const min = Math.min(0, ...rows.map(({ value }) => value));
  const range = max - min || 1;
  const zero = -min / range * 100;
  return <ul className="benchmark-bars" aria-label={metric.label + " by strategy"}>
    {rows.map(({ name, value, color }) => <li key={name} data-ours={name === "ours" || undefined}>
      <span>{label(name)}</span>
      <span className="benchmark-bar-track" aria-hidden="true" style={{ "--zero": zero + "%" } as CSSProperties}>
        <i style={{ insetInlineStart: Math.min(zero, zero + value / range * 100) + "%", width: Math.abs(value / range * 100) + "%", background: color }} />
      </span>
      <strong>{metric.format(value)}</strong>
    </li>)}
  </ul>;
}

async function loadTracker(signal: AbortSignal) {
  const path = "/portfolio/holdings/" + encodeURIComponent(sp500Ticker) + "/prices?limit=260";
  if (!MOCK) return get<HoldingPrices>(path, "", signal);
  return (await get<Record<string, HoldingPrices>>(path, "holding_prices", signal))[sp500Ticker] ?? null;
}

export default function BenchmarkScreen() {
  const report = useResource("benchmarks", signal => get<Benchmarks>("/benchmarks", "benchmarks", signal));
  const rebalances = useResource("rebalances", signal => get<PortfolioRebalances>("/portfolio/rebalances", "rebalances", signal));
  const [start, end] = report.value?.periods.held_out ?? ["", null];
  const hasWindow = end !== null && start !== "" && start < end;
  const tracker = useResource(hasWindow ? start + "/" + end : "", signal => hasWindow ? loadTracker(signal) : Promise.resolve(null));
  const [view, setView] = useState<"value" | "market">("value");
  const [metricIndex, setMetricIndex] = useState(0);
  const [hidden, setHidden] = useState<string[]>([]);
  const data = useMemo(() => joinBenchmarkSeries(report.value?.series ?? {}), [report.value]);
  const names = Object.entries(report.value?.series ?? {}).filter(([, points]) => points.length).map(([name]) => name);
  const strategies = Object.keys(report.value?.metrics ?? {});
  const showReplayNote = !MOCK && hasWindow && strategies.length > 0;
  const colors = new Map([...new Set([...names, ...strategies])].map((name, index) => [name, palette[index % palette.length]]));
  colors.set(sp500Key, marketColor);
  const color = (name: string) => colors.get(name) ?? palette[0];
  const market = end ? sp500ReturnSeries(tracker.value, start, end) : [];
  const marketReturn = market.at(-1)?.[sp500Key];
  const marketUnavailable = hasWindow && (tracker.value !== undefined || Boolean(tracker.error)) && marketReturn === undefined;
  const selectedMetric = comparisonMetrics[metricIndex];
  const strategyMetrics = report.value?.metrics;
  const rows = strategies.flatMap(name => {
    const value = strategyMetrics?.[name][selectedMetric.id];
    return value != null && Number.isFinite(value) ? [{ name, value, color: color(name) }] : [];
  });
  if (selectedMetric.id === "total_return" && marketReturn !== undefined) rows.push({ name: sp500Key, value: marketReturn, color: marketColor });
  const risk = strategies.flatMap(name => {
    const metric = strategyMetrics?.[name];
    return metric && Number.isFinite(metric.vol_annual) && Number.isFinite(metric.total_return)
      ? [{ name, volatility: metric.vol_annual, return: metric.total_return, fill: color(name) }] : [];
  });
  const visible = names.filter(name => !hidden.includes(name));
  const chartData = view === "market" ? market : data;
  const canChart = chartData.length > 1;
  const rebalanceItems = rebalances.value?.items ?? [];

  function toggleStrategy(name: string) {
    if (!hidden.includes(name) && visible.length <= 1) return;
    setHidden(current => current.includes(name) ? current.filter(item => item !== name) : [...current, name]);
  }

  return <div className="mvp-page mvp-enter benchmark-desk">
    <header className="benchmark-heading">
      <div><h1><span data-tour-target="benchmarks-intro">Benchmarks</span></h1><p>Compare how the agents’ paper portfolio performed against simpler investing strategies.</p></div>
      <div className="benchmark-period">
        <strong>{hasWindow ? dateLong.format(new Date(start)) + " – " + dateLong.format(new Date(end)) : "Recorded results"}</strong>
        <span>Paper portfolio · Recorded simulation{MOCK ? " · Synthetic fixtures" : showReplayNote ? "*" : ""}</span>
      </div>
    </header>
    {report.error ? <section className="terminal-glass glass-feedback benchmark-card"><p role="alert">Couldn’t load benchmark results. {report.error}</p></section> :
      !report.value ? <section className="terminal-glass glass-feedback benchmark-card" aria-busy="true"><p role="status">Loading benchmark results…</p></section> :
      !names.length && !strategies.length ? <section className="terminal-glass glass-feedback benchmark-card benchmark-empty">
        <h2>No benchmark results yet</h2>
        <p>Completed recorded runs show how your paper portfolio compares with other strategies. Open Timeline to play a recording.</p>
        <Link className="mvp-action" to="/timeline">Open Timeline</Link>
      </section> : <>
        <div className="benchmark-grid">
          <section className="terminal-glass glass-feedback benchmark-card">
            <header className="benchmark-card-head">
              <div><h2>{view === "value" ? "Portfolio value" : "S&P 500 tracker"}</h2>
                <p>{view === "value" ? "Simulated balances in pounds, including deposits." : "Change in the tracker’s adjusted price in pounds."}</p></div>
              <div className="benchmark-toggle" role="group" aria-label="Chart view">
                <button type="button" aria-pressed={view === "value"} onClick={() => setView("value")}>Portfolio value</button>
                <button type="button" aria-pressed={view === "market"} onClick={() => setView("market")}>S&P 500</button>
              </div>
            </header>
            {canChart ? <div className="benchmark-plot" role="region" aria-label={view === "value" ? "Portfolio values over time" : "S&P 500 tracker return over time"}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 8, right: 26, bottom: 0, left: 0 }}>
                  <CartesianGrid vertical={false} stroke="var(--terminal-edge)" strokeDasharray="3 4" />
                  <XAxis dataKey="date" tickFormatter={(value: string) => dateShort.format(new Date(value))} tick={chartDateTick} interval="preserveStartEnd" minTickGap={30} />
                  <YAxis width={view === "value" ? moneyAxisWidth : percentAxisWidth} tick={chartValueTick} domain={["auto", "auto"]} tickFormatter={view === "value" ? pounds.format : pct.format} />
                  <Tooltip labelFormatter={(value: string) => dateLong.format(new Date(value))}
                    formatter={(value: number, name: string) => [view === "value" ? gbp.format(value) : signedPct.format(value), label(name)]} />
                  {view === "market" && <ReferenceLine y={0} stroke="var(--terminal-muted)" strokeDasharray="3 4" />}
                  {(view === "value" ? visible : [sp500Key]).map(name => <Line key={name} dataKey={name} stroke={color(name)}
                    strokeWidth={name === "ours" || name === sp500Key ? 2.5 : 1.4} dot={false} connectNulls isAnimationActive={false} />)}
                </LineChart>
              </ResponsiveContainer>
            </div> : <p className="benchmark-empty benchmark-plot" role="status">{view === "value" ? "No portfolio value series is available." :
              marketUnavailable || !hasWindow ? "S&P 500 tracker prices don’t cover this full comparison period." : "Loading S&P 500 tracker prices…"}</p>}
            {view === "value" ? <div className="benchmark-legend" role="group" aria-label="Show or hide strategies">
              {names.map(name => <button key={name} type="button" aria-pressed={visible.includes(name)}
                disabled={visible.length === 1 && visible[0] === name} onClick={() => toggleStrategy(name)}>
                <i aria-hidden="true" style={{ background: color(name) }} />{label(name)}
              </button>)}
            </div> : <p className="benchmark-note">{referenceHelp}</p>}
          </section>

          <section className="terminal-glass glass-feedback benchmark-card">
            <header className="benchmark-card-head">
              <div><h2><Term name={selectedMetric.label + " by strategy"} help={selectedMetric.help} /></h2>
                <p>{selectedMetric.id === "total_return" ? "Gains or losses over the same dates." : selectedMetric.id === "max_drawdown" ? "Each strategy’s biggest fall from a previous high." : "What each strategy spent on simulated trades."}</p></div>
              <select className="terminal-field" aria-label="Comparison metric" data-tour-target="benchmark-metric" value={metricIndex} onChange={event => setMetricIndex(Number(event.target.value))}>
                {comparisonMetrics.map((metric, index) => <option key={metric.id} value={index}>{metric.label}</option>)}
              </select>
            </header>
            {rows.length ? <ComparisonBars rows={rows} metric={selectedMetric} /> : <p className="benchmark-empty">No values for this metric.</p>}
            {selectedMetric.id === "total_return" && <p className="benchmark-note">{marketUnavailable ? "S&P 500 tracker prices are unavailable for the full period." :
              marketReturn !== undefined ? "S&P 500 uses Vanguard’s VUAG fund in GBP. Strategy returns exclude deposits and include simulated trading costs." : "Strategy returns exclude deposits and include simulated trading costs."}</p>}
            {showReplayNote && <p className="benchmark-note">* We limited both demos to four months to keep Gemini API usage manageable. The profiles follow different risk plans, and one replay can’t show long-term performance.</p>}
          </section>
        </div>
        <div className="benchmark-grid benchmark-grid-details">
          <section className="terminal-glass glass-feedback benchmark-card">
            <header className="benchmark-card-head"><div>
              <h2><Term name="Return vs. volatility" help="Higher dots gained more. Dots further right had bigger swings in their returns." /></h2>
              <p>Compare the return each strategy delivered and how much it fluctuated.</p>
            </div></header>
            {risk.length ? <div className="benchmark-plot benchmark-risk" role="region" aria-label="Simulated return versus annualised volatility">
              <ResponsiveContainer width="100%" height="100%">
                <ScatterChart margin={{ top: 12, right: 28, bottom: 20, left: 2 }}>
                  <CartesianGrid stroke="var(--terminal-edge)" strokeDasharray="3 4" />
                  <XAxis type="number" dataKey="volatility" name="Volatility" tickFormatter={pct.format} tick={chartValueTick} tickCount={4}
                    label={{ value: "Volatility (annualised)", position: "insideBottom", offset: -10 }} />
                  <YAxis type="number" dataKey="return" name="Return" width={percentAxisWidth} tick={chartValueTick} domain={["auto", "auto"]} tickFormatter={pct.format} />
                  <ReferenceLine y={0} stroke="var(--terminal-muted)" strokeDasharray="3 4" />
                  <Tooltip cursor={{ strokeDasharray: "3 3" }} content={({ active, payload }) => {
                    const point = payload?.[0]?.payload as (typeof risk)[number] | undefined;
                    return active && point ? <div className="benchmark-chart-tip">
                      <strong>{label(point.name)}</strong>
                      <span>Return {signedPct.format(point.return)}</span><span>Volatility {pct.format(point.volatility)}</span>
                    </div> : null;
                  }} />
                  <Scatter data={risk} isAnimationActive={false} />
                </ScatterChart>
              </ResponsiveContainer>
            </div> : <p className="benchmark-empty">No volatility data is available.</p>}
          </section>
          <section className="terminal-glass glass-feedback benchmark-card benchmark-details">
            <header className="benchmark-card-head"><div><h2>Strategy details</h2><p>Hover or focus a question mark for a plain-English definition.</p></div></header>
            <div className="benchmark-table-wrap" role="region" aria-label="Detailed benchmark results" tabIndex={0}>
              <table className="mvp-table benchmark-table">
                <thead><tr><th scope="col">Strategy</th>{metrics.map(metric => <th scope="col" key={metric.id}>
                  <Term name={metric.label} help={metric.help} />
                </th>)}</tr></thead>
                <tbody>{[...strategies, ...(marketReturn !== undefined ? [sp500Key] : [])].map(name => <tr key={name} data-ours={name === "ours" || undefined}>
                  <th scope="row">{strategyHelp[name] ? <Term name={label(name)} help={strategyHelp[name]} /> : label(name)}</th>
                  {metrics.map(metric => {
                    const value = name === sp500Key ? (metric.id === "total_return" ? marketReturn : undefined) : strategyMetrics?.[name][metric.id];
                    return <td key={metric.id}>{value != null && Number.isFinite(value) ? metric.format(value) : <span aria-label="Unavailable">—</span>}</td>;
                  })}
                </tr>)}</tbody>
              </table>
            </div>
            <p className="benchmark-note">Simulated performance over a short historical period. The S&P 500 reference reports fund return only.</p>
          </section>
        </div>
      </>}
    <section className="terminal-glass glass-feedback benchmark-card">
      <header className="benchmark-card-head"><div><h2><Term name="Recent rebalances" help="Trades that change how much the portfolio holds in each investment." /></h2>
        <p>Filled trades that changed the mix of investments in the paper portfolio.</p></div></header>
      {rebalances.error ? <p role="alert">Couldn’t load recent rebalances.</p> : !rebalances.value ? <p role="status">Loading recent rebalances…</p> :
        !rebalanceItems.length ? <p className="benchmark-note">No filled rebalances yet.</p> :
          rebalanceItems.map(item => <article className="notice-row" key={(item.run_id ?? "recorded") + item.date}>
            <div><strong>{item.trigger_text ? investigationTitle(item.trigger_text, item.trigger_kind) : "Recorded trades"}</strong><p>{item.date} · Cost {gbp.format(item.cost_gbp)}</p>
              <ul>{item.changes.map((change, i) => <li key={change.ticker + change.action + i}>{words(change.action)} {gbp.format(change.amount_gbp)} · {change.ticker}</li>)}</ul></div>
            {item.run_id && <Link to={"/runs/" + encodeURIComponent(item.run_id) + "?replay=1"} className="mvp-action">Replay investigation</Link>}
          </article>)}
    </section>
  </div>;
}
