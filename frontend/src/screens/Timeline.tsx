import { useCallback, useMemo, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Area, AreaChart, CartesianGrid, Line, LineChart, ReferenceDot, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import NewsCard from "../components/NewsCard";
import { chartDateTick, chartValueTick, moneyAxisWidth, percentAxisWidth } from "../lib/chartLabels";
import FinanceTerm from "../components/FinanceTerm";
import { finance } from "../lib/financeTerms";
import ScrollArrivalList from "../components/ScrollArrivalList";
import PanelGrip from "../components/PanelGrip";
import { get } from "../lib/api";
import { benchmarkNames, type Benchmarks } from "../lib/benchmarkData";
import type { NewsFeed, PortfolioHistory, PortfolioRebalances, RunSummary } from "../lib/types";
import { useResource } from "../lib/useResource";
import { gbp, pct, words } from "./Decisions";
import { RunRoom } from "./Workspace";

const palette = ["#b4c7da", "#8bbba6", "#b3a3ca", "#bd9a78", "#aa8f9a", "#7c95a7", "#97a780"];
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
  { kind: "Trades"; item: PortfolioRebalances["items"][number] }
);
const activityFilters = ["All", "Investigations", "Trades"] as const;
const runLink = (run: Run) => runRoute(run.run_id) + (run.status === "running" ? "?live=1" : "?replay=1");
const runLabel = (run: Run) => run.outcome ? outcomes[run.outcome] : words(run.status);
const tickerLabel = (ticker: string) => ticker.split(".")[0];

function ActivityIcon({ kind }: { kind: Activity["kind"] }) {
  return <svg viewBox="0 0 20 20" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.35"
    strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {kind === "Trades" ? <path d="M3 7h13m-4-4 4 4-4 4M17 13H4m4-4-4 4 4 4" /> :
        <><circle cx="8.5" cy="8.5" r="4.5" /><path d="m12 12 4 4m-10-7h1l1-2 1 3 1-1h1" /></>}
  </svg>;
}

function ActivityRow({ entry, inspect }: { entry: Activity; inspect?: (id: string) => void }) {
  const icon = <span className="history-event-icon"><ActivityIcon kind={entry.kind} /></span>;
  if (entry.kind === "Trades") {
    const { item } = entry;
    return <li>{icon}<div>
      <small>Paper trades filled</small>
      <strong>{inspect ? <button type="button" className="mvp-action compact" onClick={() => inspect(item.run_id)}>{item.trigger_text || "Portfolio updated"} ›</button> : <Link className="mvp-action compact" to={runRoute(item.run_id) + "?replay=1"}>{item.trigger_text || "Portfolio updated"} ›</Link>}</strong>
      <ul className="history-trades">{item.changes.map(change => <li key={change.ticker + change.action}>
        <span>{words(change.action)} {tickerLabel(change.ticker)} <small>{pct.format(change.from_weight)} → {pct.format(change.to_weight)}</small></span>
        <strong>{gbp.format(change.amount_gbp)}</strong>
      </li>)}</ul>
      <span>Trading cost {gbp.format(item.cost_gbp)}</span>
    </div></li>;
  }
  return <li>{icon}<div>
    <small>{entry.item.kind === "construction" ? "Portfolio build" : words(entry.item.kind)} · {runLabel(entry.item)}</small>
    <strong>{inspect && entry.item.status !== "running" ? <button type="button" className="mvp-action compact" onClick={() => inspect(entry.item.run_id)}>{entry.item.trigger_text || "Inspect investigation"} ›</button> : <Link className="mvp-action compact" to={runLink(entry.item)}>{entry.item.trigger_text || "Open investigation"} ›</Link>}</strong>
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
      ...(rebalances.value?.items ?? []).map((item): Activity => ({ kind: "Trades", item, date: item.date, stamp: item.date })),
    ];
    const groups = new Map<string, Activity[]>();
    for (const entry of entries.sort((a, b) => b.date.localeCompare(a.date) || Date.parse(b.stamp) - Date.parse(a.stamp))) {
      const bucket = groups.get(entry.date) ?? [];
      bucket.push(entry);
      groups.set(entry.date, bucket);
    }
    return groups;
  }, [runs.value, rebalances.value]);
  const visibleGroups = [...grouped].map(([date, entries]) => ({ date, entries: entries.filter(entry => filter === "All" || entry.kind === filter) })).filter(group => group.entries.length);
  const snapshot = selectedDate ? points.filter(point => point.date <= selectedDate).at(-1) : current;
  const previous = snapshot && points[points.indexOf(snapshot) - 1];
  const change = snapshot && previous ? snapshot.nav_gbp - previous.nav_gbp : undefined;
  const holdings = Object.entries(snapshot?.weights ?? {}).filter(([, weight]) => weight > 0).sort((a, b) => b[1] - a[1]);
  const markers = new Map((runs.value?.items ?? []).filter(run => run.kind === "review" || run.proposal_id).map(run => [run.as_of.slice(0, 10), run]));
  const activityError = runs.error || rebalances.error;

  return <div className="history-desk resizable-desk">
    <aside className="terminal-glass glass-feedback history-pane history-snapshot" aria-label="Portfolio snapshot">
      <div className="history-heading"><h2>Portfolio snapshot</h2>{selectedDate && <button type="button" className="mvp-action compact" onClick={() => setSelectedDate(undefined)}>Latest close</button>}</div>
      {snapshot ? <>
        <time dateTime={snapshot.date}>{fullDate.format(new Date(snapshot.date))}</time>
        <strong className="history-nav">{gbp.format(snapshot.nav_gbp)}</strong>
        <dl>{change !== undefined && <div><dt>Change since prior close</dt><dd data-direction={Math.sign(change)}>{signedMoney.format(change)}</dd></div>}
          {snapshot.contributions_gbp !== null && <div><dt>Total paid in</dt><dd>{gbp.format(snapshot.contributions_gbp)}</dd></div>}</dl>
        <h3><FinanceTerm name="Portfolio weights" help={finance.weight} /></h3>
        {holdings.length > 0 ? <ul className="history-holdings">{holdings.map(([ticker, weight]) => <li key={ticker}>
          <span>{tickerLabel(ticker)}</span><i aria-hidden="true" style={{ "--weight": (weight * 100) + "%" } as CSSProperties} /><strong>{pct.format(weight)}</strong>
        </li>)}</ul> : <p>No holdings recorded for this close.</p>}
      </> : <p>{selectedDate || history.value ? "No portfolio close available for this date." : history.error ? "Couldn’t load portfolio history." : "Loading portfolio…"}</p>}
    </aside>

    <div className="history-visuals">
      <section className="terminal-glass glass-feedback history-pane history-value">
        <div className="history-heading"><h2>Portfolio value</h2>
          {portfolioTab && strategies.length > 1 && <button type="button" className="mvp-action compact" aria-pressed={comparison} onClick={() => setComparison(!comparison)}>Benchmarks</button>}</div>
        {!joined.length ? <p>{history.error ? "Couldn’t load portfolio history." : history.value ? "No recorded closes yet." : "Loading portfolio history…"}</p> :
          <div className="timeline-chart"><ResponsiveContainer width="100%" height="100%"><LineChart data={joined} margin={{ left: 16, right: 12, top: 12, bottom: 2 }}>
            <CartesianGrid stroke="var(--terminal-edge)" />
            <XAxis dataKey="date" tickFormatter={dateLabel} tick={chartDateTick} axisLine={false} tickLine={false} interval="preserveStartEnd" minTickGap={24} />
            <YAxis orientation="right" width={moneyAxisWidth} tickFormatter={close} tick={chartValueTick} axisLine={false} tickLine={false} domain={["auto", "auto"]} />
            <Tooltip labelFormatter={dateLabel} formatter={(value: number, name: string) => [gbp.format(value), name]} />
            {shownStrategies.map((name, i) => <Line key={name} name={benchmarkNames[name] ?? words(name)} dataKey={name} stroke={palette[i % palette.length]}
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
          <span key={name}><i style={{ background: palette[i % palette.length] }} />{benchmarkNames[name] ?? words(name)}</span>)}
          {markers.size > 0 && <span><i className="history-marker" />Reviews and proposals</span>}
        </div>
      </section>
      {portfolioTab && <section className="terminal-glass glass-feedback history-pane history-allocation">
        <div className="history-heading"><h2><FinanceTerm name="Allocation over time" help={finance.allocation} /></h2>{portfolioTab && <Link className="mvp-action compact" to="/benchmarks">Benchmark details ›</Link>}</div>
        {weights.length ? <div className="timeline-weights"><ResponsiveContainer width="100%" height="100%">
          <AreaChart data={visibleWeights} margin={{ left: 16, right: 12, top: 12, bottom: 2 }}><CartesianGrid stroke="var(--terminal-edge)" vertical={false} />
            <XAxis dataKey="date" tickFormatter={dateLabel} tick={chartDateTick} axisLine={false} tickLine={false} interval="preserveStartEnd" minTickGap={24} />
            <YAxis orientation="right" width={percentAxisWidth} tickFormatter={pct.format} tick={chartValueTick} axisLine={false} tickLine={false} domain={[0, 1]} />
            <Tooltip labelFormatter={dateLabel} formatter={(value: number, name: string) => [pct.format(value), tickerLabel(name)]} />
            {weights.map((ticker, index) => <Area key={ticker} dataKey={ticker} stackId="weights" stroke={palette[index % palette.length]}
              fill={palette[index % palette.length]} fillOpacity={0.52} isAnimationActive={false} />)}
          </AreaChart></ResponsiveContainer></div> : <p>{history.value ? "No recorded allocations yet." : "Portfolio allocation will appear here."}</p>}
      </section>}
      {!portfolioTab && investigation}
      <PanelGrip edge="bottom" panel=".history-value" neighbor={portfolioTab ? ".history-allocation" : ".timeline-investigation"}
        variable="--timeline-chart-height" min={180} remaining={portfolioTab ? 185 : 300}
        label={portfolioTab ? "Resize portfolio value and allocation heights" : "Resize portfolio value and investigation heights"} />
    </div>

    <div className="timeline-feeds">
    <section className="terminal-glass glass-feedback history-pane history-feed" data-expanded={activityExpanded} aria-label="Timeline activity">
      <div className="history-heading"><h2>Activity over time</h2>
        <button type="button" className="mvp-action compact" aria-pressed={activityExpanded} onClick={event => {
          event.currentTarget.closest<HTMLElement>(".timeline-feeds")?.style.removeProperty("--timeline-activity-height");
          setActivityExpanded(!activityExpanded);
        }}>{activityExpanded ? "Collapse" : "Expand"}</button>
      </div>
      <div className="history-filters" role="group" aria-label="Filter activity">{activityFilters.map(value =>
        <button key={value} type="button" aria-pressed={filter === value} onClick={() => setFilter(value)}>{value}</button>)}</div>
      <div className="history-feed-scroll">
        {activityError && <p role="alert">Some timeline activity couldn’t be loaded.</p>}
        {visibleGroups.map(({ date, entries }) => <section key={date} className="history-day">
          <h3><button type="button" aria-pressed={selectedDate === date} onClick={() => setSelectedDate(selectedDate === date ? undefined : date)}>
            <time dateTime={date}>{fullDate.format(new Date(date))}</time><span aria-hidden="true">›</span>
          </button></h3>
          <ul>{entries.map(entry => <ActivityRow key={entry.kind + entry.item.run_id} entry={entry} inspect={inspect} />)}</ul>
        </section>)}
        {!visibleGroups.length && !activityError && <p>{runs.value && rebalances.value ? "No activity in this view yet." : "Loading activity…"}</p>}
      </div>
    </section>
      <section className="terminal-glass glass-feedback history-pane history-news" aria-label="News over time">
        <div className="history-heading"><h2>News over time</h2></div>
        {news.value?.items.length ? <div className="history-news-scroll">
          <ul className="news-feed-list" data-compact>{news.value.items.slice(0, 3).map(item => <NewsCard key={item.id} item={item} compact />)}</ul>
          {news.value.items.length > 3 && <details className="desk-disclosure">
            <summary><span>Earlier stories</span><small>{news.value.items.length - 3}</small></summary>
            <ScrollArrivalList className="news-feed-list" data-compact>{news.value.items.slice(3).map(item => <NewsCard key={item.id} item={item} compact />)}</ScrollArrivalList>
          </details>}
        </div> : <p>{news.error ? "Couldn’t load news." : news.value ? "No cached news for this period." : "Loading news…"}</p>}
      </section>
      <PanelGrip edge="bottom" panel=".history-feed" neighbor=".history-news" variable="--timeline-activity-height" min={182} remaining={172}
        label="Resize activity and news heights" onResize={() => setActivityExpanded(false)} />
    </div>
    <PanelGrip edge="left" panel=".history-snapshot" neighbor=".history-visuals" variable="--desk-left" min={172} remaining={420} label="Resize portfolio snapshot width" />
    <PanelGrip edge="right" panel=".timeline-feeds" neighbor=".history-visuals" variable="--desk-right" min={230} remaining={420} label="Resize Timeline activity and news width" />
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
    if (play) setSession(value => value + 1);
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
    <section className="timeline-investigation terminal-glass glass-feedback" ref={panel} tabIndex={-1} aria-labelledby="timeline-run-title">
      <div className="mvp-toolbar timeline-run-toolbar">
        <div><h2 id="timeline-run-title" data-tour-target="timeline-intro">Investigations over time</h2>
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
        onContinue={autoplay && activeIndex < recordings.length - 1 ? continuePlayback : undefined} /> :
        <div className="terminal-glass glass-feedback history-pane">
          <p>{runs.error ? "Couldn’t load recorded investigations." : runs.value ? "Completed investigations will appear here with their evidence and agent steps." : "Loading investigations…"}</p>
          <Link className="mvp-action" to="/workspace">Open Agents</Link>
        </div>}
    </section>} />
  </div>;
}
