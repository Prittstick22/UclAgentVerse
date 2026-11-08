import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Area, AreaChart, CartesianGrid, Line, LineChart, ReferenceArea, ReferenceDot, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { get } from "../lib/api";
import type { PortfolioHistory, PortfolioRebalances, RunSummary } from "../lib/types";
import { useResource } from "../lib/useResource";
import { gbp, pct, words } from "./Decisions";

type Point = { date: string; nav_gbp: number };
type Metrics = { total_return: number; vol_annual: number; max_drawdown: number; sharpe: number; costs_gbp: number; trades: number };
type Benchmarks = {
  series: Record<string, Point[]>; metrics: Record<string, Metrics>;
  periods: { development: [string, string]; held_out: [string, string | null] };
};
const palette = ["#b4c7da", "#8bbba6", "#b3a3ca", "#bd9a78", "#aa8f9a", "#7c95a7", "#97a780"];
const labels: Record<string, string> = {
  ours: "Agent portfolio", ours_no_agents: "Engine only", buy_and_hold: "Buy and hold",
  quarterly_rebalance: "Quarterly rebalance", global_etf: "Global ETF", mechanical_5pct: "5% rebalance",
};
const dateLabel = (date: string) => new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", timeZone: "UTC" }).format(new Date(date));
const close = (value: number) => "£" + Math.round(value).toLocaleString("en-GB");
const runRoute = (id: string) => "/runs/" + encodeURIComponent(id);

export default function Timeline() {
  const navigate = useNavigate();
  const history = useResource("history", signal => get<PortfolioHistory>("/portfolio/history", "history", signal));
  const benchmarks = useResource("benchmarks", signal => get<Benchmarks>("/benchmarks", "benchmarks", signal));
  const runs = useResource("runs", signal => get<{ items: Omit<RunSummary, "agents">[] }>("/runs?limit=1000", "runs", signal));
  const [cursor, setCursor] = useState<number | null>(null);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [comparison, setComparison] = useState(true);
  const points = history.value?.points;
  const series = benchmarks.value?.series;
  const joined = useMemo(() => {
    const byDate = new Map<string, Record<string, string | number>>();
    for (const point of points ?? []) byDate.set(point.date, { date: point.date, ours: point.nav_gbp });
    for (const [name, records] of Object.entries(series ?? {})) for (const { date, nav_gbp } of records) {
      const row = byDate.get(date) ?? { date };
      if (row[name] == null) row[name] = nav_gbp;
      byDate.set(date, row);
    }
    return [...byDate.values()].sort((a, b) => String(a.date).localeCompare(String(b.date)));
  }, [points, series]);
  const index = Math.min(joined.length - 1, cursor ?? joined.length - 1);
  const current = joined[index];
  const weights = useMemo(() => [...new Set((points ?? []).flatMap(point => Object.keys(point.weights)))], [points]);
  const visibleWeights = useMemo(() => (points ?? []).filter(point => current && point.date <= String(current.date))
    .map(point => ({ date: point.date, ...Object.fromEntries(weights.map(ticker => [ticker, point.weights[ticker] ?? 0])) })), [points, current, weights]);
  const strategies = ["ours", ...Object.keys(series ?? {}).filter(name => name !== "ours" && !name.startsWith("ours_"))];
  const markers = runs.value?.items.filter(run => run.as_of <= String(current?.date ?? "") && ["review", "construction", "drift", "news", "price_move", "nav_drop", "cap_breach", "corr_regime"].includes(run.kind)) ?? [];

  useEffect(() => {
    if (playing && index >= 0 && index < joined.length - 1) {
      const timer = window.setTimeout(() => setCursor(index + 1), 600 / speed);
      return () => window.clearTimeout(timer);
    }
  }, [index, joined.length, playing, speed]);

  return <div className="mvp-page timeline-page mvp-enter">
    <header className="mvp-toolbar"><div><h1>Portfolio timeline</h1><p className="mvp-muted">Recorded portfolio history and agent investigations</p></div>
      {current && <strong>{dateLabel(String(current.date))} · {typeof current.ours === "number" ? gbp.format(current.ours) : "—"}</strong>}</header>
    {(history.error || benchmarks.error || runs.error) && <p role="alert">{history.error ?? benchmarks.error ?? runs.error}</p>}
    <section className="terminal-glass mvp-panel">
      <div className="mvp-toolbar"><h2>Portfolio value</h2>
        {strategies.length > 1 && <button className="mvp-action" aria-pressed={comparison} onClick={() => setComparison(!comparison)}>Benchmarks</button>}</div>
      {!joined.length ? <p className="mvp-muted">{history.value ? "No recorded closes yet." : "Loading portfolio history…"}</p> :
        <div className="timeline-chart"><ResponsiveContainer width="100%" height="100%"><LineChart data={joined.slice(0, index + 1)} margin={{ right: 18, top: 8 }}>
          <CartesianGrid stroke="var(--terminal-edge)" vertical={false} />
          <XAxis dataKey="date" tickFormatter={dateLabel} tick={{ fontSize: 11, fill: "var(--terminal-muted)" }} minTickGap={32} />
          <YAxis width={72} tickFormatter={close} tick={{ fontSize: 11, fill: "var(--terminal-muted)" }} domain={["auto", "auto"]} />
          <Tooltip labelFormatter={dateLabel} formatter={(value: number, name: string) => [gbp.format(value), name]} />
          {(["development", "held_out"] as const).map((period, i) => {
            const range = benchmarks.value?.periods[period];
            const dates = joined.slice(0, index + 1).filter(row => range && String(row.date) >= range[0] && (!range[1] || String(row.date) <= range[1]));
            return dates.length ? <ReferenceArea key={period} x1={String(dates[0].date)} x2={String(dates.at(-1)?.date)}
              fill={palette[i]} fillOpacity={0.09} strokeOpacity={0} /> : null;
          })}
          {strategies.slice(0, comparison ? strategies.length : 1).map((name, i) =>
            <Line key={name} name={labels[name] ?? words(name)} dataKey={name} stroke={palette[i % palette.length]}
              strokeWidth={i === 0 ? 2 : 1.25} dot={joined.length === 1} isAnimationActive={false} />)}
          {markers.map(run => {
            const value = joined.find(row => row.date === run.as_of)?.ours;
            if (typeof value !== "number") return null;
            return <ReferenceDot key={run.run_id} x={run.as_of} y={value} r={5}
              fill={run.outcome === "adjust" ? "#c6aa8c" : "var(--terminal-positive)"} stroke="var(--terminal-bg)"
              style={{ cursor: "pointer" }} onClick={() => navigate(runRoute(run.run_id))} />;
          })}
        </LineChart></ResponsiveContainer></div>}
      <div className="mvp-toolbar timeline-legend">{strategies.slice(0, comparison ? strategies.length : 1).map((name, i) =>
        <span key={name}><i style={{ background: palette[i % palette.length] }} />{labels[name] ?? words(name)}</span>)}</div>
      {current && <div className="mvp-toolbar replay-controls">
        <button className="mvp-action" disabled={joined.length < 2} onClick={() => {
          if (index === joined.length - 1) { setCursor(0); setPlaying(true); } else setPlaying(!playing);
        }}>{playing && index < joined.length - 1 ? "Pause" : "Play"}</button>
        <input type="range" min="0" max={Math.max(0, joined.length - 1)} value={index} aria-label="Portfolio timeline"
          aria-valuetext={String(current.date)} onChange={event => { setCursor(Number(event.target.value)); setPlaying(false); }} />
        <select className="terminal-field" aria-label="Playback speed" value={speed} onChange={event => setSpeed(Number(event.target.value))}>
          {[1, 2, 4, 8].map(value => <option key={value} value={value}>{value}×</option>)}
        </select>
      </div>}
      {markers.length > 0 && <div className="timeline-markers" aria-label="Investigation markers">{markers.map(run =>
        <Link key={run.run_id} to={runRoute(run.run_id)} title={run.trigger_text} data-outcome={run.outcome}>
          <time>{dateLabel(run.as_of)}</time><span>{words(run.kind)}</span><span>{words(run.outcome ?? run.status)}</span>
        </Link>)}</div>}
    </section>
    <section className="terminal-glass mvp-panel">
      <h2>Allocation over time</h2>
      {weights.length ? <div className="timeline-weights"><ResponsiveContainer width="100%" height="100%">
        <AreaChart data={visibleWeights} margin={{ right: 18, top: 8 }}><CartesianGrid stroke="var(--terminal-edge)" vertical={false} />
          <XAxis dataKey="date" tickFormatter={dateLabel} tick={{ fontSize: 11, fill: "var(--terminal-muted)" }} minTickGap={32} />
          <YAxis width={60} tickFormatter={pct.format} tick={{ fontSize: 11, fill: "var(--terminal-muted)" }} domain={[0, 1]} />
          <Tooltip labelFormatter={dateLabel} formatter={(value: number) => pct.format(value)} />
          {weights.map((ticker, index) => <Area key={ticker} dataKey={ticker} stackId="weights" stroke={palette[index % palette.length]}
            fill={palette[index % palette.length]} fillOpacity={0.55} isAnimationActive={false} />)}
        </AreaChart></ResponsiveContainer></div> : <p className="mvp-muted">No recorded allocations yet.</p>}
    </section>
    <Link className="mvp-action" to="/benchmarks">See rebalances and benchmarks</Link>
  </div>;
}

export function BenchmarkScreen() {
  const report = useResource("benchmarks", signal => get<Benchmarks>("/benchmarks", "benchmarks", signal));
  const rebalances = useResource("rebalances", signal => get<PortfolioRebalances>("/portfolio/rebalances", "rebalances", signal));
  const rows = Object.entries(report.value?.metrics ?? {});
  return <div className="mvp-page mvp-enter">
    <h1>Rebalances and benchmarks</h1>
    {(report.error || rebalances.error) && <p role="alert">{report.error ?? rebalances.error}</p>}
    <section className="mvp-panel terminal-glass">
      <h2>Benchmark comparison</h2>
      <p className="mvp-muted">Simulated held-out window. A short period of past returns is not a forecast. Sharpe uses a zero risk-free rate.</p>
      {rows.length ? <table className="mvp-table">
        <thead><tr><th>Strategy</th><th>Return</th><th>Volatility</th><th>Drawdown</th><th>Sharpe</th><th>Costs</th><th>Trades</th></tr></thead>
        <tbody>{rows.map(([name, row]) => <tr key={name}><th>{labels[name] ?? words(name)}</th>
          <td>{pct.format(row.total_return)}</td><td>{pct.format(row.vol_annual)}</td><td>{pct.format(row.max_drawdown)}</td>
          <td>{row.sharpe.toFixed(2)}</td><td>{gbp.format(row.costs_gbp)}</td><td>{row.trades}</td></tr>)}</tbody>
      </table> : <p>{report.value ? "No completed benchmark run." : "Loading benchmarks…"}</p>}
    </section>
    <section className="mvp-panel terminal-glass">
      <h2>Recent rebalances</h2>
      {rebalances.value?.items.map(item => <article className="notice-row" key={item.run_id + item.date}>
        <div><strong>{item.trigger_text || words(item.trigger_kind)}</strong><p>{item.date} · Cost {gbp.format(item.cost_gbp)}</p>
          <ul>{item.changes.map(change => <li key={change.ticker}>{words(change.action)} {gbp.format(change.amount_gbp)} · {change.ticker}</li>)}</ul></div>
        <Link to={runRoute(item.run_id)} className="mvp-action">Replay investigation</Link>
      </article>)}
      {rebalances.value && !rebalances.value.items.length && <p>No filled rebalances yet.</p>}
    </section>
  </div>;
}
