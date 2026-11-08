import { useCallback, useEffect, useState } from "react";
import { Area, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid } from "recharts";
import CorrelationLattice from "../components/CorrelationLattice";
import AgentAvatar from "../components/AgentAvatar";
import { Link } from "react-router-dom";
import { ProposalDialog } from "./Decisions";
import HoldingIssuer from "../components/HoldingIssuer";
import { TerminalBrand } from "../components/TerminalShellUi";
import { api, get, MOCK } from "../lib/api";
import { portfolioQueries, type ReviewSummary } from "../lib/portfolioQueries";
import type { Holding, NewsFeed, Notification, PnlPeriod, Portfolio, PortfolioHistory, PortfolioPnl } from "../lib/types";
import "./portfolio-home.css";

const money = new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP" });
const signedMoney = new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP", signDisplay: "exceptZero" });
const percent = new Intl.NumberFormat("en-GB", { style: "percent", maximumFractionDigits: 1 });
const signedPercent = new Intl.NumberFormat("en-GB", { style: "percent", maximumFractionDigits: 2, signDisplay: "exceptZero" });
const units = new Intl.NumberFormat("en-GB", { maximumFractionDigits: 4 });
const shortDate = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });
const chartMoney = new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP", maximumFractionDigits: 0 });
const periods: Record<PnlPeriod, string> = {
  since_purchase: "Since purchase", "1m": "1 month", "3m": "3 months", ytd: "Year to date", sim_year: "Replay window",
};
const statuses: Record<Portfolio["status"], string> = {
  monitoring_normally: "Monitoring normally", investigating: "Review in progress",
  awaiting_approval: "Awaiting your decision", monitoring_degraded: "Price coverage degraded",
};
const chartViews = ["Connections", "Performance", "Split view"] as const;
const activityViews = ["Reviews", "Watch", "Decisions"] as const;
type ChartView = typeof chartViews[number];
type ActivityView = typeof activityViews[number];
type HistoryPoint = PortfolioHistory["points"][number];
type Loader<T> = (signal: AbortSignal) => Promise<T>;

const tone = (n?: number) => n === undefined || n === 0 ? "" : n > 0 ? "is-positive" : "is-negative";
const positionId = (ticker: string) => `portfolio-position-${ticker}`;
const assetLabel = (ticker: string) => ticker.split(".")[0];
const shortHoldingName = (name: string) => name.replace(/^(Vanguard|iShares) /, "").replace(/ UCITS ETF\b.*$/, "");

function dateLabel(value?: string | null) {
  const time = Date.parse(value ?? "");
  return Number.isFinite(time) ? shortDate.format(time) : "—";
}

function useQuery<T>(load: Loader<T>, revision: number) {
  const [state, setState] = useState<{ load: Loader<T>; value: T | null; error: string; pending: boolean }>({
    load, value: null, error: "", pending: true,
  });
  useEffect(() => {
    const controller = new AbortController();
    setState((previous) => ({ load, value: previous.load === load ? previous.value : null, error: "", pending: true }));
    load(controller.signal).then((value) => {
      if (!controller.signal.aborted) setState({ load, value, error: "", pending: false });
    }).catch((reason: unknown) => {
      if (!controller.signal.aborted) setState((previous) => ({
        ...previous, error: reason instanceof Error ? reason.message : "Please try again", pending: false,
      }));
    });
    return () => controller.abort();
  }, [load, revision]);
  return state.load === load ? state : { value: null, error: "", pending: true };
}

function ViewIcon({ view }: { view: ChartView }) {
  return <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
    {view === "Connections" && <><path d="M10 6.5v3m-5 3 5-3 5 3" /><circle cx="10" cy="4.5" r="2" /><circle cx="5" cy="14.5" r="2" /><circle cx="15" cy="14.5" r="2" /></>}
    {view === "Performance" && <path d="M3 4v12h14M6 12l3-3 3 1 4-4" strokeLinecap="round" strokeLinejoin="round" />}
    {view === "Split view" && <><rect x="3.5" y="4" width="13" height="12" rx="1.5" /><path d="M10 4v12" /></>}
  </svg>;
}

function HoldingMark({ ticker, name }: { ticker: string; name: string }) {
  return <span className="portfolio-holding-mark"><HoldingIssuer name={name} ticker={ticker} /></span>;
}

function WeightSparkline({ ticker, history }: { ticker: string; history: HistoryPoint[] }) {
  const sample = history.slice(-24).flatMap((point) => {
    const weight = point.weights[ticker];
    return weight === undefined ? [] : [weight];
  });
  if (sample.length < 2) return null;
  const low = Math.min(...sample);
  const span = Math.max(...sample) - low;
  const points = sample.map((value, index) => `${2 + index * 196 / (sample.length - 1)},${span ? 16 - (value - low) * 12 / span : 10}`);
  return <svg className="portfolio-weight-sparkline" viewBox="0 0 200 20" preserveAspectRatio="none" role="img" aria-label={`${ticker} portfolio weight trend`}>
    <polyline points={points.join(" ")} />
  </svg>;
}

function Allocation({ portfolio }: { portfolio: Portfolio }) {
  if (portfolio.nav_gbp <= 0) return null;
  const groups = [
    { kind: "equity", label: "Shares" }, { kind: "bond", label: "Bonds" }, { kind: "commodity", label: "Commodities" },
  ].map(({ kind, label }) => ({ kind, label, weight: portfolio.holdings.reduce((sum, holding) => (
    holding.asset_class === kind ? sum + holding.weight : sum
  ), 0) }));
  const cash = { kind: "cash", label: "Cash", weight: portfolio.cash_gbp / portfolio.nav_gbp };
  const allocation = [...groups.filter(({ weight }) => weight !== 0), cash];
  return <section className="portfolio-allocation" aria-label="Portfolio allocation">
    <h2>Allocation</h2>
    <div className="portfolio-allocation-bar" aria-hidden="true">
      {allocation.filter(({ weight }) => weight > 0).map(({ kind, weight }) => (
        <span key={kind} data-kind={kind} style={{ flexGrow: weight }} />
      ))}
    </div>
    <ul>{allocation.map(({ kind, label, weight }) => (
      <li key={kind}><i data-kind={kind} aria-hidden="true" /><span>{label}</span><strong>{percent.format(weight)}</strong></li>
    ))}</ul>
  </section>;
}

function Watchlist({ portfolio, holdings, history, selected, select, pending }: {
  portfolio: Portfolio | null; holdings: Holding[]; history: HistoryPoint[]; selected: string | null;
  select: (ticker: string) => void; pending: boolean;
}) {
  return <aside className="portfolio-panel terminal-glass portfolio-watchlist" aria-labelledby="watchlist-heading">
    <div className="portfolio-panel-heading"><h1 id="watchlist-heading">My holdings</h1></div>
    <div className="portfolio-watch-labels"><span>Asset{portfolio && ` (${holdings.length})`}</span><span>Price / date</span></div>
    {holdings.length > 0 ? <ul className="portfolio-watch-rows">{holdings.map((holding) => (
      <li key={holding.ticker}>
        <button type="button" className="portfolio-watch-row" aria-current={selected === holding.ticker ? "true" : undefined}
          aria-label={`Show ${holding.name} in Positions`} onClick={() => select(holding.ticker)}>
          <span className="portfolio-watch-asset">
            <HoldingMark ticker={holding.ticker} name={holding.name} />
            <span><strong title={holding.name}>{shortHoldingName(holding.name)}</strong><small>{assetLabel(holding.ticker)}</small></span>
          </span>
          <WeightSparkline ticker={holding.ticker} history={history} />
          <span className="portfolio-watch-price">
            <strong>{holding.price_gbp > 0 ? money.format(holding.price_gbp) : "—"}</strong>
            <small className={holding.stale ? "is-stale" : undefined}>
              {holding.stale && "Stale · "}<time dateTime={holding.price_as_of}>{dateLabel(holding.price_as_of)}</time>
            </small>
          </span>
        </button>
      </li>
    ))}</ul> : <p className="portfolio-empty">{portfolio ? "No paper holdings yet" : pending ? "Loading holdings" : "Holding data is unavailable"}</p>}
    {portfolio && <Allocation portfolio={portfolio} />}
  </aside>;
}

function PerformanceChart({ points, reviews }: { points: HistoryPoint[]; reviews: ReviewSummary[] }) {
  const paidIn = points.some((point) => point.contributions_gbp !== null);
  const last = points.at(-1);
  const reviewsByDate = new Map<string, ReviewSummary>();
  for (const review of reviews) {
    if (!reviewsByDate.has(review.as_of)) reviewsByDate.set(review.as_of, review);
  }
  const series = points.map((point) => ({ ...point, review_nav: reviewsByDate.has(point.date) ? point.nav_gbp : null }));
  const byDate = new Map(series.map((point) => [point.date, point]));
  const hasMarkers = series.some((point) => point.review_nav !== null);
  return <section className="portfolio-performance" aria-labelledby="performance-heading">
    <header><div><h2 id="performance-heading">Portfolio performance</h2><p>Recorded value at each close</p></div>
      {last && <strong>{money.format(last.nav_gbp)}</strong>}
    </header>
    {!last ? <p className="portfolio-empty">No portfolio closes recorded yet</p> : <>
      <div className="portfolio-performance-plot" role="region" aria-label="Portfolio value over the recorded closes">
        <ResponsiveContainer width="100%" height="100%" minWidth={0}>
          <ComposedChart data={series} margin={{ left: 0, right: 16, top: 12, bottom: 4 }} accessibilityLayer>
            <defs><linearGradient id="portfolio-value-fill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--terminal-chart)" stopOpacity={.14} />
              <stop offset="100%" stopColor="var(--terminal-chart)" stopOpacity={0} />
            </linearGradient></defs>
            <CartesianGrid stroke="var(--terminal-edge)" strokeOpacity={.68} />
            <XAxis dataKey="date" tickFormatter={dateLabel} tickLine={false} minTickGap={28}
              tick={{ fill: "var(--terminal-muted)", fontSize: 11 }} axisLine={{ stroke: "var(--terminal-edge)" }} />
            <YAxis orientation="right" tickFormatter={(value: number) => chartMoney.format(value)} tickLine={false} width={66}
              tick={{ fill: "var(--terminal-muted)", fontSize: 11 }} axisLine={false} domain={["auto", "auto"]} />
            <Tooltip content={({ active, label }) => {
              const point = typeof label === "string" ? byDate.get(label) : undefined;
              if (!active || !point) return null;
              const review = reviewsByDate.get(point.date);
              return <div className="portfolio-performance-tooltip">
                <strong>{dateLabel(point.date)}</strong><span>Portfolio value {money.format(point.nav_gbp)}</span>
                {point.contributions_gbp !== null && <span>Paid in {money.format(point.contributions_gbp)}</span>}
                {review && <span className="portfolio-performance-review">{reviewResult(review)}</span>}
              </div>;
            }} />
            <ReferenceLine y={last.nav_gbp} stroke="var(--terminal-chart)" strokeOpacity={.38} strokeDasharray="3 4" />
            <Area type="linear" dataKey="nav_gbp" name="Portfolio value" stroke="var(--terminal-chart)" strokeWidth={1.8}
              fill="url(#portfolio-value-fill)" fillOpacity={1} isAnimationActive={false} dot={points.length === 1} />
            {paidIn && <Line type="stepAfter" dataKey="contributions_gbp" name="Paid in" stroke="var(--terminal-muted)"
              strokeDasharray="4 4" dot={false} isAnimationActive={false} />}
            {hasMarkers && <Line dataKey="review_nav" name="Recorded review" stroke="none" activeDot={false}
              dot={{ r: 4, fill: "var(--terminal-positive)", stroke: "var(--terminal-bg)", strokeWidth: 1.5 }} isAnimationActive={false} />}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <div className="portfolio-performance-legend"><span><i />Portfolio value</span>
        {paidIn && <span><i className="portfolio-paid-in-key" />Paid in</span>}
        {hasMarkers && <span><i className="portfolio-review-key" />Recorded review</span>}
      </div>
    </>}
  </section>;
}

function HoldingsTabs({ news, setNews }: { news: boolean; setNews: (news: boolean) => void }) {
  return <div className="portfolio-content-tabs" role="group" aria-label="Portfolio details">
    <button type="button" aria-pressed={!news} onClick={() => setNews(false)}>Positions</button>
    <button type="button" aria-pressed={news} onClick={() => setNews(true)}>Latest news</button>
  </div>;
}

const loadNews = (signal: AbortSignal) => get<NewsFeed>("/news", "news", signal);

function LatestNews({ portfolio, revision, setNews }: { portfolio: Portfolio | null; revision: number; setNews: (news: boolean) => void }) {
  const feed = useQuery(loadNews, revision);
  const held = new Set(portfolio?.holdings.map(holding => holding.ticker));
  const [holdingsOnly, setHoldingsOnly] = useState(false);
  const items = (feed.value?.items ?? []).filter(item => !holdingsOnly || item.tickers.some(ticker => held.has(ticker)));
  return <section className="portfolio-panel terminal-glass portfolio-positions" aria-label="Latest news" aria-busy={feed.pending}>
    <header className="portfolio-panel-heading">
      <HoldingsTabs news setNews={setNews} />
      {held.size > 0 && <label><input type="checkbox" checked={holdingsOnly} onChange={event => setHoldingsOnly(event.currentTarget.checked)} /> My holdings</label>}
    </header>
    {items.length > 0 ? <ul className="portfolio-news-list">{items.map(item => {
      const url = item.url && /^https?:\/\//i.test(item.url) ? item.url : null;
      return <li key={item.id}>
        <div className="portfolio-news-meta"><time dateTime={item.published_at}>{dateLabel(item.published_at)}</time>
          <span>{item.source}{item.synthetic && !/synthetic/i.test(item.source) ? " · Synthetic" : ""}</span></div>
        <h3>{url ? <a href={url} target="_blank" rel="noreferrer">{item.headline} ↗</a> : item.headline}</h3>
        {item.summary && <p>{item.summary}</p>}
        {item.tickers.length > 0 && <div className="portfolio-news-tags">{item.tickers.map(ticker =>
          <span key={ticker} data-held={held.has(ticker)}>{assetLabel(ticker)}</span>)}</div>}
      </li>;
    })}</ul> : <p className="portfolio-empty" role={feed.error ? "alert" : "status"}>
      {feed.error ? "Couldn’t load news" : feed.pending ? "Loading latest news…" : holdingsOnly ? "No cached stories match your holdings" : "No news available for this date"}
    </p>}
    {feed.value && <footer>Cached news · As of {dateLabel(feed.value.as_of)}</footer>}
  </section>;
}

function Positions({ portfolio, holdings, pnl, period, selectPeriod, selected, pending, error, setNews }: {
  portfolio: Portfolio | null; holdings: Holding[]; pnl: PortfolioPnl | null; period: PnlPeriod;
  selectPeriod: (period: PnlPeriod) => void; selected: string | null; pending: boolean; error: string; setNews: (news: boolean) => void;
}) {
  const byTicker = new Map(pnl?.rows.map((row) => [row.ticker, row]));
  const holdingTickers = new Set(holdings.map((holding) => holding.ticker));
  const rows = [
    ...holdings.map((holding) => ({ ticker: holding.ticker, name: holding.name, holding })),
    ...(pnl?.rows.filter((row) => !holdingTickers.has(row.ticker)) ?? []).map(({ ticker, name }) => ({ ticker, name, holding: undefined })),
  ];
  return <section className="portfolio-panel terminal-glass portfolio-positions" aria-label="Positions" aria-busy={pending}>
    <header className="portfolio-panel-heading">
      <HoldingsTabs news={false} setNews={setNews} />
      <label><span>P&amp;L period</span><select value={period} onChange={(event) => selectPeriod(event.currentTarget.value as PnlPeriod)}>
        {Object.entries(periods).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </select></label>
    </header>
    {error && <p className="portfolio-inline-error" role="alert">P&amp;L unavailable · {error}</p>}
    {rows.length ? <div className="portfolio-table-scroll" tabIndex={0} aria-label="Positions table">
      <table>
        <thead><tr><th scope="col">Holding</th><th scope="col">Units</th><th scope="col">Price</th><th scope="col">Value</th>
          <th scope="col">Gain / loss</th><th scope="col">Realised / unrealised</th><th scope="col">Contribution</th></tr></thead>
        <tbody>{rows.map(({ ticker, name, holding }) => {
          const gain = byTicker.get(ticker);
          return <tr key={ticker} id={positionId(ticker)} tabIndex={-1} data-selected={selected === ticker || undefined}>
            <th scope="row"><div className="portfolio-position-name"><HoldingMark ticker={ticker} name={name} /><span>
              <strong title={name}>{shortHoldingName(name)}</strong><small title={holding?.purpose ?? undefined}>{holding ? assetLabel(ticker) : "Closed position"}</small>
            </span></div></th>
            <td>{holding ? units.format(holding.units) : "—"}</td>
            <td>{holding && holding.price_gbp > 0 ? money.format(holding.price_gbp) : "—"}
              {holding && <small className={holding.stale ? "is-stale" : undefined}>
                {holding.stale && "Stale · "}<time dateTime={holding.price_as_of}>{dateLabel(holding.price_as_of)}</time>
              </small>}
            </td>
            <td>{holding ? money.format(holding.value_gbp) : "—"}</td>
            <td className={tone(gain?.pnl_gbp)}>{gain ? signedMoney.format(gain.pnl_gbp) : "—"}
              {gain && <small>{signedPercent.format(gain.pnl_pct)}</small>}
            </td>
            <td>{gain ? <><span className={tone(gain.realised_gbp)}>{signedMoney.format(gain.realised_gbp)}</span>
              <small className={tone(gain.unrealised_gbp)}>{signedMoney.format(gain.unrealised_gbp)}</small></> : "—"}</td>
            <td className={tone(gain?.contribution_to_return)}>{gain ? signedPercent.format(gain.contribution_to_return) : "—"}</td>
          </tr>;
        })}</tbody>
      </table>
    </div> : <p className="portfolio-empty">{pending ? "Loading position performance" : "No positions in this period"}</p>}
    {(portfolio || pnl) && <footer>
      {portfolio && <><span>Cash <strong>{money.format(portfolio.cash_gbp)}</strong></span><span>Portfolio <strong>{money.format(portfolio.nav_gbp)}</strong></span></>}
      {pnl && <span>Period result <strong className={tone(pnl.total_pnl_gbp)}>{signedMoney.format(pnl.total_pnl_gbp)}</strong></span>}
    </footer>}
  </section>;
}

function reviewResult(review: ReviewSummary) {
  if (review.status === "running") return "Review in progress";
  if (review.status === "failed") return "Review failed";
  if (review.status === "cancelled") return "Review cancelled";
  if (review.outcome === "maintain") return "Portfolio kept as is";
  if (review.outcome === "adjust") return "Adjustment proposed";
  if (review.outcome === "investigate_further") return "Further investigation needed";
  return "Review completed";
}

function ReviewPanel({ portfolio, reviews, notifications, reviewError, notificationError, markRead, marking, revision }: {
  portfolio: Portfolio | null; reviews: ReviewSummary[]; notifications: Notification[];
  reviewError: string; notificationError: string; markRead: (id: string) => void; marking: string | null; revision: number;
}) {
  const [view, setView] = useState<ActivityView>("Reviews");
  const [selected, setSelected] = useState<string | null>(null);
  const review = reviews.find((item) => item.run_id === selected) ?? reviews[0];
  const [proposal, setProposal] = useState("");
  const reviewId = view === "Reviews" ? review?.run_id : undefined;
  const loadReview = useCallback((signal: AbortSignal) =>
    reviewId ? portfolioQueries.reviewDetail(reviewId, signal) : Promise.resolve(null), [reviewId]);
  const detail = useQuery(loadReview, revision);
  const agents = detail.value?.run_id === reviewId ? detail.value?.agents ?? [] : [];
  const activity = notifications.filter((item) => view === "Decisions" ? item.kind === "decision" : item.kind !== "decision");
  const pending = portfolio?.status === "awaiting_approval" ? notifications.find(item => item.kind === "decision" && item.proposal_id) : undefined;
  return <aside className="portfolio-panel terminal-glass portfolio-review" aria-labelledby="portfolio-review-heading">
    <div className="portfolio-panel-heading"><span className="portfolio-review-glyph"><TerminalBrand /></span>
      <h2 id="portfolio-review-heading">Agent review</h2></div>
    <div className="portfolio-review-switch" role="group" aria-label="Review views">
      {activityViews.map((item) => <button type="button" key={item} aria-pressed={view === item} onClick={() => setView(item)}>{item}</button>)}
    </div>
    {pending?.proposal_id && <div className="proposal-nudge"><span>Decision needed</span><button className="mvp-action primary"
      onClick={() => setProposal(pending.proposal_id ?? "")}>Review proposal</button></div>}
    <section className="portfolio-overview" aria-label="Portfolio overview">
      {view === "Reviews" && review && <div className="portfolio-review-detail">
        <div><span>{selected === review.run_id ? "Selected review" : "Latest recorded review"}</span>
          <time dateTime={review.as_of}>{dateLabel(review.as_of)}</time></div>
        <strong>{reviewResult(review)}</strong><p>{review.trigger_text}</p>
      </div>}
      <div className="portfolio-overview-title"><h3>Portfolio overview</h3><time dateTime={portfolio?.as_of}>{dateLabel(portfolio?.as_of)}{portfolio && " close"}</time></div>
      <div className="portfolio-overview-value"><div><span>Portfolio value</span><strong>{portfolio ? money.format(portfolio.nav_gbp) : "—"}</strong></div>
        <div><span>{portfolio?.mode === "live" ? "Total return" : "Replay return"}</span>
          <strong className={tone(portfolio?.total_return)}>{portfolio ? signedPercent.format(portfolio.total_return) : "—"}</strong></div>
      </div>
      {portfolio && <><span className="portfolio-status" data-status={portfolio.status}>{statuses[portfolio.status]}</span>
        <dl className="portfolio-overview-stats">
          <div><dt>Cash available</dt><dd>{money.format(portfolio.cash_gbp)}</dd></div>
          <div><dt>Paid in</dt><dd>{money.format(portfolio.contributions_gbp)}</dd></div>
          <div><dt>Last review</dt><dd><time dateTime={portfolio.last_review_date ?? undefined}>{dateLabel(portfolio.last_review_date)}</time></dd></div>
          <div><dt>Next review</dt><dd><time dateTime={portfolio.next_review_date ?? undefined}>{dateLabel(portfolio.next_review_date)}</time></dd></div>
        </dl>
        <p className="portfolio-counts"><strong>{portfolio.counters.reviews}</strong> reviews, <strong>{portfolio.counters.checks}</strong> checks,
          {" "}<strong>{portfolio.counters.decisions_asked}</strong> decisions asked of you</p></>}
    </section>
    {view === "Reviews" ? <section className="portfolio-activity" aria-label="Review history">
      {agents.length > 0 && <>
        <h3>Review team</h3>
        <ul className="portfolio-review-team">{agents.map((agent) => <li key={agent.agent_id} data-status={agent.status}>
          <AgentAvatar role={agent.role} />
          <div><strong>{agent.role === "lead" ? "Lead agent" : agent.role.replaceAll("_", " ")}</strong>
            {agent.purpose && <p title={agent.purpose}>{agent.purpose}</p>}</div>
          <span>{agent.status}</span>
        </li>)}</ul>
      </>}
      <h3>Review history</h3>
      {review && <Link className="mvp-link" to={"/runs/" + encodeURIComponent(review.run_id)}>Open investigation ↗</Link>}
      {reviewError && <p className="portfolio-inline-error" role="alert">Couldn’t load review history</p>}
      {reviews.length > 0 ? <ul className="portfolio-review-history">{reviews.map((item) => <li key={item.run_id}>
        <button type="button" aria-pressed={item.run_id === review?.run_id} onClick={() => setSelected(item.run_id)}>
          <time dateTime={item.as_of}>{dateLabel(item.as_of)}</time><span>{reviewResult(item)}</span><b aria-hidden="true">›</b>
        </button>
      </li>)}</ul> : !reviewError && <p className="portfolio-empty">No recorded reviews yet</p>}
    </section> : <section className="portfolio-activity" aria-label={view === "Watch" ? "Portfolio activity digest" : "Decision notifications"}>
      <h3>{view === "Watch" ? "Activity digest" : "Decisions"}</h3>
      {notificationError && <p className="portfolio-inline-error" role="alert">{notificationError}</p>}
      {activity.length > 0 ? <ul className="portfolio-notification-list">{activity.map((item) => <li key={item.id}>
        <strong>{item.title}</strong><p>{item.body}</p>
        {item.proposal_id && <button className="mvp-link" onClick={() => setProposal(item.proposal_id ?? "")}>Review proposal</button>}
        <div><time dateTime={item.created_at}>{dateLabel(item.created_at)}</time>
          {!item.read && <button type="button" disabled={marking !== null} onClick={() => markRead(item.id)}>
            {marking === item.id ? "Marking…" : "Mark as read"}
          </button>}</div>
      </li>)}</ul> : !notificationError && <p className="portfolio-empty">{view === "Watch" ? "No activity notices yet" : "No decisions to review"}</p>}
    </section>}
    {portfolio && <footer><span>{portfolio.counters.adjustments} filled {portfolio.counters.adjustments === 1 ? "adjustment" : "adjustments"}</span></footer>}
    {proposal && <ProposalDialog key={proposal} id={proposal} mode={portfolio?.mode} close={() => setProposal("")} />}
  </aside>;
}

export default function Home({ onClockChange }: { onClockChange?: (date: string) => void }) {
  const [revision, setRevision] = useState(0);
  const refresh = useCallback(() => setRevision((current) => current + 1), []);
  const [view, setView] = useState<ChartView>("Performance");
  const [period, setPeriod] = useState<PnlPeriod>("since_purchase");
  const [selected, setSelected] = useState<string | null>(null);
  const [showNews, setNews] = useState(false);
  const [read, setRead] = useState<string[]>([]);
  const [marking, setMarking] = useState<string | null>(null);
  const [markError, setMarkError] = useState("");
  const loadPnl = useCallback((signal: AbortSignal) => portfolioQueries.pnl(period, signal), [period]);
  const summary = useQuery(portfolioQueries.summary, revision);
  const history = useQuery(portfolioQueries.history, revision);
  const tickers = (summary.value?.holdings ?? []).map(({ ticker }) => ticker).sort().join(",");
  const loadCorrelation = useCallback((signal: AbortSignal) =>
    tickers ? portfolioQueries.correlations(tickers, signal) : Promise.resolve(null), [tickers]);
  const correlation = useQuery(loadCorrelation, revision);
  const pnl = useQuery(loadPnl, revision);
  const notifications = useQuery(portfolioQueries.notifications, revision);
  const reviews = useQuery(portfolioQueries.reviews, revision);

  useEffect(() => {
    if (MOCK) return;
    const stream = new EventSource("/api/events/stream");
    let timer: number | undefined;
    let connected = false;
    const schedule = () => {
      if (timer === undefined) timer = window.setTimeout(() => { timer = undefined; refresh(); }, 120);
    };
    stream.addEventListener("open", () => {
      if (connected) schedule();
      connected = true;
    });
    stream.addEventListener("clock.tick", (message: MessageEvent<string>) => {
      const { as_of } = JSON.parse(message.data) as { as_of: string };
      onClockChange?.(as_of);
      schedule();
    });
    for (const type of ["run.started", "run.completed", "notification.created", "approval.decided", "order.filled", "mode.changed"]) {
      stream.addEventListener(type, schedule);
    }
    return () => { window.clearTimeout(timer); stream.close(); };
  }, [onClockChange, refresh]);

  function markRead(id: string) {
    if (marking) return;
    setMarkError("");
    setMarking(id);
    api.markNotificationRead(id).then(() => {
      setRead((current) => [...current, id]);
      if (!MOCK) refresh();
    }).catch(() => setMarkError("Couldn’t mark this item as read")).finally(() => setMarking(null));
  }

  function selectHolding(ticker: string) {
    if (showNews) {
      setNews(false);
      setSelected(ticker);
      return;
    }
    setSelected(ticker);
    const row = document.getElementById(positionId(ticker));
    row?.focus({ preventScroll: true });
    row?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }

  const portfolio = summary.value;
  const holdings = [...(portfolio?.holdings ?? [])].sort((a, b) => b.weight - a.weight);
  const points = history.value?.points ?? [];
  const availableNotifications = notifications.value?.items.map((item) => read.includes(item.id) ? { ...item, read: true } : item) ?? [];
  return <div className="portfolio-home">
    {summary.error && <div className="portfolio-summary-error" role="alert"><span>Couldn’t load the latest portfolio summary · {summary.error}</span>
      <button type="button" onClick={refresh}>Retry</button></div>}
    <Watchlist portfolio={portfolio} holdings={holdings} history={points} selected={selected} select={selectHolding} pending={summary.pending} />
    <section className="portfolio-panel terminal-glass portfolio-chart" aria-label="Portfolio charts">
      <nav className="portfolio-chart-switch" aria-label="Portfolio chart views">
        {chartViews.map((item) => <button type="button" key={item} aria-pressed={view === item} onClick={() => setView(item)}>
          <ViewIcon view={item} />{item}
        </button>)}
      </nav>
      <div className={`portfolio-chart-content${view === "Split view" ? " is-split" : ""}`}>
        {view !== "Performance" && (correlation.value ? <CorrelationLattice report={correlation.value} holdings={holdings}
          mode={portfolio?.mode} startDate={points[0]?.date} /> : <p className="portfolio-empty" role={correlation.error ? "alert" : undefined}>
          {correlation.error || summary.error ? "Holding connections are unavailable" :
            summary.pending || correlation.pending ? "Loading holding connections" : "Connections appear after you add holdings"}
        </p>)}
        {view !== "Connections" && (history.error ? <p className="portfolio-inline-error" role="alert">Couldn’t load portfolio history · {history.error}</p>
          : history.pending && !history.value ? <p className="portfolio-empty">Loading recorded closes</p>
            : <PerformanceChart points={points} reviews={reviews.value ?? []} />)}
      </div>
    </section>
    {showNews ? <LatestNews portfolio={portfolio} revision={revision} setNews={setNews} /> :
      <Positions portfolio={portfolio} holdings={holdings} pnl={pnl.error ? null : pnl.value} period={period} selectPeriod={setPeriod}
        selected={selected} pending={pnl.pending} error={pnl.error} setNews={setNews} />}
    <ReviewPanel portfolio={portfolio} reviews={reviews.value?.slice(0, 8) ?? []} notifications={availableNotifications}
      reviewError={reviews.error} notificationError={markError || (notifications.error && "Couldn’t load portfolio activity")}
      markRead={markRead} marking={marking} revision={revision} />
  </div>;
}
