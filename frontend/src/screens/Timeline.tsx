import { useCallback, useMemo, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Area, AreaChart, CartesianGrid, Line, LineChart, ReferenceDot, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { get } from "../lib/api";
import type { NewsFeed, NewsItem, PortfolioHistory, PortfolioRebalances, RunSummary } from "../lib/types";
import { useResource } from "../lib/useResource";
import { gbp, pct, words } from "./Decisions";
import { RunRoom } from "./Workspace";

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

const outcomes: Record<NonNullable<RunSummary["outcome"]>, string> = {
  maintain: "Portfolio kept as is", adjust: "Change proposed", investigate_further: "More investigation needed",
  built: "Starting portfolio prepared", answered: "Review answered",
};
const signedMoney = new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP", signDisplay: "exceptZero" });
const fullDate = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
const loadHistory = (signal: AbortSignal) => get<PortfolioHistory>("/portfolio/history", "history", signal);
const loadRuns = (signal: AbortSignal) => get<{ items: Omit<RunSummary, "agents">[] }>("/runs?limit=1000", "runs", signal);
const loadNews = (signal: AbortSignal) => get<NewsFeed>("/news?limit=500", "news", signal);
const loadRebalances = (signal: AbortSignal) => get<PortfolioRebalances>("/portfolio/rebalances?limit=500", "rebalances", signal);
type Run = Omit<RunSummary, "agents">;
type Activity = { date: string; stamp: string } & (
  { kind: "Investigations"; item: Run } |
  { kind: "News"; item: NewsItem } |
  { kind: "Trades"; item: PortfolioRebalances["items"][number] }
);
const activityFilters = ["All", "Investigations", "News", "Trades"] as const;
const runLink = (run: Run) => runRoute(run.run_id) + (run.status === "running" ? "?live=1" : "?replay=1");
const runLabel = (run: Run) => run.outcome ? outcomes[run.outcome] : words(run.status);
const tickerLabel = (ticker: string) => ticker.split(".")[0];

function ActivityIcon({ kind }: { kind: Activity["kind"] }) {
  return <svg viewBox="0 0 20 20" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.35"
    strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {kind === "News" ? <path d="M5 3h11v12a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7h2m2 0h6m-6 3h6m-6 3h4M5 3v12" /> :
      kind === "Trades" ? <path d="M3 7h13m-4-4 4 4-4 4M17 13H4m4-4-4 4 4 4" /> :
        <><circle cx="8.5" cy="8.5" r="4.5" /><path d="m12 12 4 4m-10-7h1l1-2 1 3 1-1h1" /></>}
  </svg>;
}

function ActivityRow({ entry, inspect }: { entry: Activity; inspect?: (id: string) => void }) {
  const icon = <span className="history-event-icon"><ActivityIcon kind={entry.kind} /></span>;
  if (entry.kind === "News") {
    const { item } = entry;
    const url = item.url && /^https?:\/\//i.test(item.url) ? item.url : null;
    return <li>{icon}<div>
      <small><time dateTime={item.published_at}>{dateLabel(item.published_at)}</time> · {item.source}{item.synthetic && !/synthetic/i.test(item.source) ? " · Synthetic" : ""}</small>
      <strong>{url ? <a href={url} target="_blank" rel="noreferrer">{item.headline} <span aria-hidden="true">↗</span></a> : item.headline}</strong>
      {item.tickers.length > 0 && <span>{item.tickers.map(tickerLabel).join(" · ")}</span>}
    </div></li>;
  }
  if (entry.kind === "Trades") {
    const { item } = entry;
    return <li>{icon}<div>
      <small>Paper trades filled</small>
      <strong>{inspect ? <button type="button" onClick={() => inspect(item.run_id)}>{item.trigger_text || "Portfolio updated"} ›</button> : <Link to={runRoute(item.run_id) + "?replay=1"}>{item.trigger_text || "Portfolio updated"} ›</Link>}</strong>
      <ul className="history-trades">{item.changes.map(change => <li key={change.ticker + change.action}>
        <span>{words(change.action)} {tickerLabel(change.ticker)}</span><strong>{gbp.format(change.amount_gbp)}</strong>
      </li>)}</ul>
      <span>Trading cost {gbp.format(item.cost_gbp)}</span>
    </div></li>;
  }
  return <li>{icon}<div>
    <small>{entry.item.kind === "construction" ? "Portfolio build" : words(entry.item.kind)} · {runLabel(entry.item)}</small>
    <strong>{inspect && entry.item.status !== "running" ? <button type="button" onClick={() => inspect(entry.item.run_id)}>{entry.item.trigger_text || "Inspect investigation"} ›</button> : <Link to={runLink(entry.item)}>{entry.item.trigger_text || "Open investigation"} ›</Link>}</strong>
  </div></li>;
}

function TimelineView({ portfolioTab, runs, inspect, investigation }: {
  portfolioTab: boolean; runs: { value?: { items: Run[] }; error?: string }; inspect: (id: string) => void; investigation: ReactNode;
}) {
  const history = useResource("history", loadHistory);
  const benchmarks = useResource("benchmarks:" + portfolioTab, signal => portfolioTab ? get<Benchmarks>("/benchmarks", "benchmarks", signal) : Promise.resolve(null));
  const news = useResource("timeline-news", loadNews);
  const rebalances = useResource("timeline-rebalances", loadRebalances);
  const [comparison, setComparison] = useState(false);
  const [activityExpanded, setActivityExpanded] = useState(false);
  const [filter, setFilter] = useState<(typeof activityFilters)[number]>("All");
  const [selectedDate, setSelectedDate] = useState<string>();
  const points = useMemo(() => [...(history.value?.points ?? [])].sort((a, b) => a.date.localeCompare(b.date)), [history.value]);
  const current = points.at(-1);
  const series = benchmarks.value?.series;
  const joined = useMemo(() => {
    const byDate = new Map<string, Record<string, string | number>>();
    for (const point of points) byDate.set(point.date, { date: point.date, ours: point.nav_gbp });
    if (portfolioTab && comparison) {
      for (const [name, records] of Object.entries(series ?? {})) for (const { date, nav_gbp } of records) {
        const row = byDate.get(date) ?? { date };
        if (row[name] == null) row[name] = nav_gbp;
        byDate.set(date, row);
      }
    }
    return [...byDate.values()].sort((a, b) => String(a.date).localeCompare(String(b.date)));
  }, [points, series, portfolioTab, comparison]);
  const weights = useMemo(() => [...new Set(points.flatMap(point => Object.keys(point.weights)))], [points]);
  const visibleWeights = useMemo(() => points.map(point => ({
    date: point.date, ...Object.fromEntries(weights.map(ticker => [ticker, point.weights[ticker] ?? 0])),
  })), [points, weights]);
  const strategies = ["ours", ...Object.keys(series ?? {}).filter(name => name !== "ours" && !name.startsWith("ours_"))];
  const shownStrategies = portfolioTab && comparison ? strategies : strategies.slice(0, 1);
  const grouped = useMemo(() => {
    const entries: Activity[] = [
      ...(runs.value?.items ?? []).map((item): Activity => ({ kind: "Investigations", item, date: item.as_of.slice(0, 10), stamp: item.started_at })),
      ...(news.value?.items ?? []).map((item): Activity => ({ kind: "News", item, date: new Date(item.available_at).toISOString().slice(0, 10), stamp: item.available_at })),
      ...(rebalances.value?.items ?? []).map((item): Activity => ({ kind: "Trades", item, date: item.date, stamp: item.date })),
    ];
    const groups = new Map<string, Activity[]>();
    for (const entry of entries.sort((a, b) => b.date.localeCompare(a.date) || Date.parse(b.stamp) - Date.parse(a.stamp))) {
      const bucket = groups.get(entry.date) ?? [];
      bucket.push(entry);
      groups.set(entry.date, bucket);
    }
    return groups;
  }, [runs.value, news.value, rebalances.value]);
  const visibleGroups = [...grouped].map(([date, entries]) => ({ date, entries: entries.filter(entry => filter === "All" || entry.kind === filter) })).filter(group => group.entries.length);
  const snapshot = selectedDate ? points.filter(point => point.date <= selectedDate).at(-1) : current;
  const previous = snapshot && points[points.indexOf(snapshot) - 1];
  const change = snapshot && previous ? snapshot.nav_gbp - previous.nav_gbp : undefined;
  const holdings = Object.entries(snapshot?.weights ?? {}).filter(([, weight]) => weight > 0).sort((a, b) => b[1] - a[1]);
  const markers = new Map((runs.value?.items ?? []).filter(run => run.kind === "review" || run.proposal_id).map(run => [run.as_of.slice(0, 10), run]));
  const activityError = runs.error || news.error || rebalances.error;

  return <div className="history-desk">
    <aside className="terminal-glass history-pane history-snapshot" aria-label="Portfolio snapshot">
      <div className="history-heading"><h2>Portfolio snapshot</h2>{selectedDate && <button type="button" onClick={() => setSelectedDate(undefined)}>Latest close</button>}</div>
      {snapshot ? <>
        <time dateTime={snapshot.date}>{fullDate.format(new Date(snapshot.date))}</time>
        <strong className="history-nav">{gbp.format(snapshot.nav_gbp)}</strong>
        <dl>{change !== undefined && <div><dt>Change since prior close</dt><dd data-direction={Math.sign(change)}>{signedMoney.format(change)}</dd></div>}
          {snapshot.contributions_gbp !== null && <div><dt>Total paid in</dt><dd>{gbp.format(snapshot.contributions_gbp)}</dd></div>}</dl>
        <h3>Portfolio weights</h3>
        {holdings.length > 0 ? <ul className="history-holdings">{holdings.map(([ticker, weight]) => <li key={ticker}>
          <span>{tickerLabel(ticker)}</span><i aria-hidden="true" style={{ "--weight": (weight * 100) + "%" } as CSSProperties} /><strong>{pct.format(weight)}</strong>
        </li>)}</ul> : <p>No holdings recorded for this close.</p>}
      </> : <p>{selectedDate || history.value ? "No portfolio close available for this date." : history.error ? "Couldn’t load portfolio history." : "Loading portfolio…"}</p>}
    </aside>

    <div className="history-visuals">
      <section className="terminal-glass history-pane">
        <div className="history-heading"><h2>Portfolio value</h2>
          {portfolioTab && strategies.length > 1 && <button type="button" aria-pressed={comparison} onClick={() => setComparison(!comparison)}>Benchmarks</button>}</div>
        {!joined.length ? <p>{history.error ? "Couldn’t load portfolio history." : history.value ? "No recorded closes yet." : "Loading portfolio history…"}</p> :
          <div className="timeline-chart"><ResponsiveContainer width="100%" height="100%"><LineChart data={joined} margin={{ left: 8, right: 12, top: 12, bottom: 2 }}>
            <CartesianGrid stroke="var(--terminal-edge)" />
            <XAxis dataKey="date" tickFormatter={dateLabel} tick={{ fontSize: 11, fill: "var(--terminal-muted)" }} axisLine={false} tickLine={false} minTickGap={28} />
            <YAxis orientation="right" width={65} tickFormatter={close} tick={{ fontSize: 11, fill: "var(--terminal-muted)" }} axisLine={false} tickLine={false} domain={["auto", "auto"]} />
            <Tooltip labelFormatter={dateLabel} formatter={(value: number, name: string) => [gbp.format(value), name]} />
            {shownStrategies.map((name, i) => <Line key={name} name={labels[name] ?? words(name)} dataKey={name} stroke={palette[i % palette.length]}
              strokeWidth={i === 0 ? 2 : 1.25} dot={joined.length === 1} isAnimationActive={false} />)}
            {selectedDate && snapshot && <ReferenceLine x={snapshot.date} stroke="var(--terminal-muted)" strokeDasharray="3 4" />}
            {points.map(point => {
              const run = markers.get(point.date);
              return run ? <ReferenceDot key={run.run_id} x={point.date} y={point.nav_gbp} r={4}
                fill="var(--terminal-text)" stroke="var(--terminal-bg)" style={{ cursor: "pointer" }}
                onClick={() => inspect(run.run_id)} /> : null;
            })}
          </LineChart></ResponsiveContainer></div>}
        <div className="timeline-legend">{shownStrategies.map((name, i) =>
          <span key={name}><i style={{ background: palette[i % palette.length] }} />{labels[name] ?? words(name)}</span>)}
          {markers.size > 0 && <span><i className="history-marker" />Reviews and proposals</span>}
        </div>
      </section>
      {portfolioTab && <section className="terminal-glass history-pane">
        <div className="history-heading"><h2>Allocation over time</h2>{portfolioTab && <Link to="/benchmarks">Benchmark details ›</Link>}</div>
        {weights.length ? <div className="timeline-weights"><ResponsiveContainer width="100%" height="100%">
          <AreaChart data={visibleWeights} margin={{ left: 8, right: 12, top: 12, bottom: 2 }}><CartesianGrid stroke="var(--terminal-edge)" vertical={false} />
            <XAxis dataKey="date" tickFormatter={dateLabel} tick={{ fontSize: 11, fill: "var(--terminal-muted)" }} axisLine={false} tickLine={false} minTickGap={28} />
            <YAxis orientation="right" width={65} tickFormatter={pct.format} tick={{ fontSize: 11, fill: "var(--terminal-muted)" }} axisLine={false} tickLine={false} domain={[0, 1]} />
            <Tooltip labelFormatter={dateLabel} formatter={(value: number, name: string) => [pct.format(value), tickerLabel(name)]} />
            {weights.map((ticker, index) => <Area key={ticker} dataKey={ticker} stackId="weights" stroke={palette[index % palette.length]}
              fill={palette[index % palette.length]} fillOpacity={0.52} isAnimationActive={false} />)}
          </AreaChart></ResponsiveContainer></div> : <p>{history.value ? "No recorded allocations yet." : "Portfolio allocation will appear here."}</p>}
      </section>}
      {!portfolioTab && investigation}
    </div>

    <div className="timeline-feeds">
    <section className="terminal-glass history-pane history-feed" data-expanded={activityExpanded} aria-label="Timeline activity">
      <div className="history-heading"><h2>Activity over time</h2>
        <button type="button" aria-pressed={activityExpanded} onClick={() => setActivityExpanded(!activityExpanded)}>{activityExpanded ? "Collapse" : "Expand"}</button>
      </div>
      <div className="history-filters" role="group" aria-label="Filter activity">{activityFilters.map(value =>
        <button key={value} type="button" aria-pressed={filter === value} onClick={() => setFilter(value)}>{value}</button>)}</div>
      <div className="history-feed-scroll">
        {activityError && <p role="alert">Some timeline activity couldn’t be loaded.</p>}
        {visibleGroups.map(({ date, entries }) => <section key={date} className="history-day">
          <h3><button type="button" aria-pressed={selectedDate === date} onClick={() => setSelectedDate(selectedDate === date ? undefined : date)}>
            <time dateTime={date}>{fullDate.format(new Date(date))}</time><span aria-hidden="true">›</span>
          </button></h3>
          <ul>{entries.map(entry => <ActivityRow key={entry.kind + ("run_id" in entry.item ? entry.item.run_id : entry.item.id)} entry={entry} inspect={inspect} />)}</ul>
        </section>)}
        {!visibleGroups.length && !activityError && <p>{runs.value && news.value && rebalances.value ? "No activity in this view yet." : "Loading activity…"}</p>}
      </div>
    </section>
      <section className="terminal-glass history-pane history-news" aria-label="News over time">
        <div className="history-heading"><h2>News over time</h2></div>
        {news.value?.items.length ? <div className="history-day history-news-scroll">
          <ul>{news.value.items.slice(0, 3).map(item => <ActivityRow key={item.id}
            entry={{ kind: "News", item, date: item.available_at, stamp: item.available_at }} />)}</ul>
          {news.value.items.length > 3 && <details className="desk-disclosure">
            <summary><span>Earlier stories</span><small>{news.value.items.length - 3}</small></summary>
            <ul>{news.value.items.slice(3).map(item => <ActivityRow key={item.id}
              entry={{ kind: "News", item, date: item.available_at, stamp: item.available_at }} />)}</ul>
          </details>}
        </div> : <p>{news.error ? "Couldn’t load news." : news.value ? "No cached news for this period." : "Loading news…"}</p>}
      </section>
    </div>
  </div>;
}

export default function TimelineScreen() {
  const [params, setParams] = useSearchParams();
  const portfolioTab = params.get("view") === "history";
  const runs = useResource("timeline-runs", loadRuns);
  const recordings = useMemo(() => (runs.value?.items ?? []).filter(run => run.status !== "running")
    .sort((a, b) => a.as_of.localeCompare(b.as_of) || Date.parse(a.started_at) - Date.parse(b.started_at)), [runs.value]);
  const runId = params.get("run");
  const active = recordings.find(run => run.run_id === runId) ?? recordings[0];
  const activeIndex = recordings.findIndex(run => run.run_id === active?.run_id);
  const [autoplay, setAutoplay] = useState(false);
  const [session, setSession] = useState(0);
  const panel = useRef<HTMLElement>(null);

  const choose = useCallback((id: string, play = false, reveal = false) => {
    setAutoplay(play);
    setSession(value => value + 1);
    setParams(previous => {
      const next = new URLSearchParams(previous);
      next.set("run", id);
      if (reveal) next.delete("view");
      return next;
    });
    if (reveal) requestAnimationFrame(() => panel.current?.focus({ preventScroll: true }));
  }, [setParams]);

  const continuePlayback = useCallback(() => {
    const next = recordings[activeIndex + 1];
    if (next) choose(next.run_id, true);
  }, [activeIndex, choose, recordings]);

  return <div className="mvp-page mvp-enter timeline-page">
    <header className="mvp-toolbar timeline-heading">
      <h1>Timeline</h1>
      <nav className="workspace-tabs" aria-label="Timeline views">
        <Link to={active ? "?run=" + encodeURIComponent(active.run_id) : "/timeline"} aria-current={!portfolioTab ? "page" : undefined}>Activity</Link>
        <Link to={"?view=history" + (active ? "&run=" + encodeURIComponent(active.run_id) : "")} aria-current={portfolioTab ? "page" : undefined}>Portfolio history</Link>
      </nav>
    </header>
    <TimelineView portfolioTab={portfolioTab} runs={runs} inspect={id => choose(id, false, true)} investigation={
    <section className="timeline-investigation terminal-glass" ref={panel} tabIndex={-1} aria-labelledby="timeline-run-title">
      <div className="mvp-toolbar timeline-run-toolbar">
        <div><h2 id="timeline-run-title">Investigations over time</h2>
          {active && <p className="mvp-muted">{activeIndex + 1} of {recordings.length} · {fullDate.format(new Date(active.as_of))}</p>}
        </div>
        {active && <div className="mvp-toolbar timeline-run-actions">
          <button type="button" className="mvp-action" disabled={activeIndex < 1} aria-label="Previous investigation"
            onClick={() => choose(recordings[activeIndex - 1].run_id)}>‹</button>
          <select className="terminal-field" aria-label="Recorded investigation" value={active.run_id} onChange={event => choose(event.target.value)}>
            {recordings.map(run => <option key={run.run_id} value={run.run_id}>{dateLabel(run.as_of)} · {run.trigger_text || words(run.kind)}</option>)}
          </select>
          <button type="button" className="mvp-action" disabled={activeIndex >= recordings.length - 1} aria-label="Next investigation"
            onClick={() => choose(recordings[activeIndex + 1].run_id)}>›</button>
          {recordings.length > 1 && <button type="button" className="mvp-action" onClick={() => choose(recordings[0].run_id, true)}>Play all from start</button>}
        </div>}
      </div>
      {active ? <RunRoom key={active.run_id + ":" + session} id={active.run_id} embedded autoplay={autoplay}
        onContinue={activeIndex < recordings.length - 1 ? continuePlayback : undefined} /> :
        <div className="terminal-glass history-pane">
          <p>{runs.error ? "Couldn’t load recorded investigations." : runs.value ? "Completed investigations will appear here with their evidence and agent steps." : "Loading investigations…"}</p>
          <Link className="mvp-action" to="/workspace">Open Agents</Link>
        </div>}
    </section>} />
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
