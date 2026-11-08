import { useEffect, useId, useMemo, useState } from "react";
import type { CSSProperties, KeyboardEvent } from "react";
import { get, MOCK } from "../lib/api";
import type { CorrelationReport, Mode, Portfolio } from "../lib/types";
import HoldingIssuer from "./HoldingIssuer";
import AgentAvatar from "./AgentAvatar";
import "./correlation-lattice.css";

type Holdings = Portfolio["holdings"];
type Group = "Bonds" | "Shares" | "Other";
type Node = { ticker: string; symbol: string; name: string; group: Group; weight?: number; x: number; y: number };
type Pair = { a: Node; b: Node; value: number; id: string };
type DateChoice = { context: string; date: string };

const DAY_MS = 86_400_000;
const PREVIEW_DAYS = 120;
const GROUPS: Group[] = ["Bonds", "Shares", "Other"];
const EMPTY_HOLDINGS: Holdings = [];
const dayNumber = (iso: string) => Date.parse(`${iso}T00:00:00Z`) / DAY_MS;
const isoDate = (day: number) => new Date(day * DAY_MS).toISOString().slice(0, 10);
const displayDate = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
const dateLabel = (iso: string) => displayDate.format(new Date(`${iso}T00:00:00Z`));
const score = (value: number) => (Math.abs(value) < 0.005 ? 0 : value).toFixed(2).replace("-", "−");
const strength = ({ value }: Pair) => Math.min(1, Math.abs(value));
const pairId = (a: string, b: string) => [a, b].sort().join("|");
const includes = (pair: Pair, ticker: string) => pair.a.ticker === ticker || pair.b.ticker === ticker;

function meaning(pair: Pair) {
  if (pair.a === pair.b) return "An investment always moves in sync with itself.";
  if (strength(pair) < 0.25) return "Their daily returns had little relationship in this window.";
  if (pair.value < 0) return "Their daily returns tended to move in opposite directions.";
  return pair.value >= 0.7 ? "They tended to rise and fall closely together."
    : "Their daily returns tended to move in the same direction.";
}

function mapReport(report: CorrelationReport, holdings: Holdings) {
  const byTicker = new Map(holdings.map((holding) => [holding.ticker, holding]));
  const symbols = report.tickers.map((ticker) => ticker.split(".")[0]);
  const nodes: Node[] = report.tickers.map((ticker, index) => {
    const holding = byTicker.get(ticker);
    const symbol = symbols.indexOf(symbols[index]) === symbols.lastIndexOf(symbols[index]) ? symbols[index] : ticker;
    const name = holding?.name ?? ticker;
    return {
      ticker, symbol, name,
      group: holding?.asset_class === "bond" ? "Bonds" : holding?.asset_class === "equity" ? "Shares" : "Other",
      weight: holding?.weight, x: 50, y: 50,
    };
  });
  const activeGroups = GROUPS.map((name) => ({ name, nodes: nodes.filter((node) => node.group === name) }))
    .filter((group) => group.nodes.length > 0);
  const units = activeGroups.reduce((sum, group) => sum + Math.max(2, group.nodes.length), 0);
  const groups = activeGroups.map((group) => ({ ...group, width: 100 * Math.max(2, group.nodes.length) / units }));
  let start = 0;
  for (const group of groups) {
    const center = start + group.width / 2;
    start += group.width;
    for (const [index, node] of group.nodes.entries()) {
      if (group.nodes.length === 1) {
        node.x = center;
      } else {
        const angle = -Math.PI / 2 + index * 2 * Math.PI / group.nodes.length;
        node.x = center + group.width * 0.34 * Math.cos(angle);
        node.y = 50 + 35 * Math.sin(angle);
      }
    }
  }
  const pairs: Pair[] = nodes.flatMap((a, row) => nodes.slice(row + 1).flatMap((b, offset) => {
    const value = report.matrix[row]?.[row + offset + 1];
    return Number.isFinite(value) ? [{ a, b, value, id: pairId(a.ticker, b.ticker) }] : [];
  })).sort((a, b) => strength(b) - strength(a));
  const overview = new Set(groups.flatMap((group) => group.nodes.flatMap(({ ticker }) => {
    const related = pairs.filter((pair) => includes(pair, ticker));
    const internal = related.filter(({ a, b }) => a.group === b.group);
    const bridge = related.find(({ a, b }) => a.group !== b.group);
    const nearby = group.nodes.length > 5 ? internal.slice(0, 2) : internal;
    return [...nearby, ...(bridge ? [bridge] : [])].map(({ id }) => id);
  })));
  return { groups, nodes, pairs, overview };
}

export default function CorrelationLattice({ report, holdings = EMPTY_HOLDINGS, mode, startDate }: {
  report: CorrelationReport; holdings?: Holdings; mode?: Mode; startDate?: string;
}) {
  const titleId = useId();
  const dateId = useId();
  const [view, setView] = useState<"network" | "matrix">("network");
  const [allLinks, setAllLinks] = useState(false);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [inspectedPair, setInspectedPair] = useState<{ a: string; b: string } | null>(null);
  const [choice, setChoice] = useState<DateChoice | null>(null);
  const [dated, setDated] = useState<(DateChoice & { report: CorrelationReport }) | null>(null);
  const [failed, setFailed] = useState<DateChoice | null>(null);
  const [retry, setRetry] = useState(0);

  const latest = dayNumber(report.as_of);
  const earliest = startDate ? dayNumber(startDate) : NaN;
  const first = Number.isFinite(earliest) ? Math.min(latest, earliest) : latest - PREVIEW_DAYS;
  const canBrowse = mode === "historical" && !MOCK && first < latest;
  const tickers = report.tickers.join(",");
  const context = `${mode}:${report.lookback}:${tickers}`;
  const requested = canBrowse && choice?.context === context && dayNumber(choice.date) >= first && choice.date < report.as_of
    ? choice.date : report.as_of;
  const isPast = requested !== report.as_of;
  const prior = dated?.context === context && dated.date <= report.as_of ? dated : null;
  const current = isPast && prior ? prior.report : report;
  const hasDate = prior?.date === requested;
  const hasError = isPast && failed?.context === context && failed.date === requested;
  const isPending = isPast && !hasDate && !hasError;

  useEffect(() => {
    if (!isPast || hasDate || mode !== "historical") return;
    const controller = new AbortController();
    const query = new URLSearchParams({ mode, as_of: requested, lookback: String(report.lookback), tickers });
    const timer = window.setTimeout(() => {
      get<CorrelationReport>(`/risk/correlation?${query}`, "correlation", controller.signal).then((next) => {
        if (controller.signal.aborted) return;
        if (next.as_of !== requested) throw new Error("Correlation date did not match the request");
        setDated({ context, date: requested, report: next });
      }).catch(() => {
        if (!controller.signal.aborted) setFailed({ context, date: requested });
      });
    }, 180);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [context, hasDate, isPast, mode, report.lookback, requested, retry, tickers]);

  const { groups, nodes, pairs, overview } = useMemo(() => mapReport(current, holdings), [current, holdings]);
  const node = nodes.find(({ ticker }) => selectedNode === ticker);
  const related = node ? pairs.filter((pair) => includes(pair, node.ticker)) : [];
  const selected = pairFor(current, nodes, inspectedPair);
  const visiblePairs = pairs.filter((pair) => allLinks || overview.has(pair.id) || (node && includes(pair, node.ticker)));
  const showGroups = groups.length > 1 || groups[0]?.name !== "Other";

  function changeView(next: "network" | "matrix") {
    setView(next);
    setInspectedPair(null);
  }

  function inspect(pair: Pair) {
    setInspectedPair({ a: pair.a.ticker, b: pair.b.ticker });
  }

  return <section className="correlation-lattice" aria-labelledby={titleId} onKeyDown={(event) => {
    if (event.key === "Escape") {
      setInspectedPair(null);
      setSelectedNode(null);
    }
  }}>
    <header className="correlation-heading">
      <AgentAvatar role="risk_analyst" />
      <div className="correlation-heading-copy">
        <h2 id={titleId}>{view === "network" ? "Holding connections" : "Correlation matrix"}</h2>
        <p>How these investments moved together</p>
      </div>
      <div className="correlation-switch" role="group" aria-label="Correlation view">
        <button type="button" aria-pressed={view === "network"} onClick={() => changeView("network")}>Links</button>
        <button type="button" aria-pressed={view === "matrix"} onClick={() => changeView("matrix")}>Matrix</button>
      </div>
    </header>

    <div className="correlation-chart" aria-busy={isPending}>
      {nodes.length === 0 ? <p className="correlation-empty">No correlation values are available for this date</p> : view === "network" ? <>
        <div className="correlation-field" tabIndex={nodes.length > 6 ? 0 : undefined} aria-label="Holding connections map">
          <div className="correlation-network" style={{ "--network-min": `${nodes.length > 14 ? 744 : nodes.length > 10 ? 588 : nodes.length > 6 ? 376 : 0}px` } as CSSProperties}>
            {showGroups && <div className="correlation-groups">
              {groups.map(({ name, nodes: members, width }) => {
                const showWeight = current.as_of === report.as_of && members.every((member) => member.weight !== undefined);
                const weight = members.reduce((total, member) => total + (member.weight ?? 0), 0);
                return <span key={name} style={{ width: `${width}%` }}>{name}{showWeight && <> <b>{(100 * weight).toFixed(1)}%</b> <small>of portfolio</small></>}</span>;
              })}
            </div>}
            <div className="correlation-network-plot">
              <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
                {visiblePairs.map((pair) => {
                  const { a, b, id, value } = pair;
                  const active = selected?.id === id;
                  const coords = { x1: a.x, y1: a.y, x2: b.x, y2: b.y };
                  return <g key={id} onPointerEnter={() => inspect(pair)}>
                    <line {...coords} className={value < 0 ? "correlation-link is-negative" : "correlation-link"}
                      strokeWidth={active ? 3 : 0.85 + strength(pair) * 2.2}
                      opacity={active ? 1 : (0.27 + strength(pair) * 0.61) * (!node || includes(pair, node.ticker) ? 1 : 0.28)} />
                    <line {...coords} className="correlation-link-hit" />
                  </g>;
                })}
              </svg>
              {nodes.map((item) => <button key={item.ticker} type="button" className="correlation-node"
                style={{ left: `${item.x}%`, top: `${item.y}%` }} aria-pressed={node === item}
                aria-label={`Inspect ${item.ticker}, ${item.name}`} title={item.name}
                onFocus={() => { setSelectedNode(item.ticker); setInspectedPair(null); }}
                onClick={() => { setSelectedNode(item.ticker); setInspectedPair(null); }}>
                <span className="correlation-mark"><HoldingIssuer name={item.name} ticker={item.ticker} /></span>
                {item.symbol}
              </button>)}
            </div>
          </div>
        </div>
        {pairs.length > 0 && <div className="correlation-link-controls">
          <span>Stronger links are thicker · Opposite moves are dashed</span>
          <button type="button" className="correlation-button" aria-pressed={allLinks}
            onClick={() => setAllLinks(!allLinks)}>{allLinks ? "Fewer links" : `All ${pairs.length} links`}</button>
        </div>}
      </> : <Matrix report={current} nodes={nodes} selected={selected} inspect={inspect} />}

      <div className="correlation-legend" aria-label="Correlation scale from negative one to positive one">
        <span>−1 Opposite</span><span>0 Little relationship</span><span>+1 In sync</span>
      </div>
    </div>

    <div className="correlation-insight" aria-live="polite">
      <div>
        {selected ? <>
          <strong>{selected.a.symbol} / {selected.b.symbol} <span>{score(selected.value)}</span></strong>
          <p>{meaning(selected)}</p>
        </> : node ? <>
          <strong>{node.symbol} · {node.name}</strong>
          <p>{related.length ? `Strongest ${partner(related[0], node)} ${score(related[0].value)}${related.length > 1
            ? ` · Weakest ${partner(related[related.length - 1], node)} ${score(related[related.length - 1].value)}` : ""}`
            : "No other investment to compare"}</p>
        </> : <>
          <strong>Weaker links can help spread risk</strong>
          <p>{view === "network" ? "Select a holding or hover over a line to inspect its links" : "Hover or focus a cell to inspect the pair"}</p>
        </>}
      </div>
      {pairs.length > 0 && <div className="correlation-average"><span>Average link</span><b>{score(current.avg_pairwise)}</b></div>}
    </div>

    {current.callouts.length > 0 && <details className="correlation-callouts">
      <summary>Correlation callouts ({current.callouts.length})</summary>
      <ul>{current.callouts.map((callout) => <li key={pairId(callout.a, callout.b)}>{callout.text}</li>)}</ul>
    </details>}

    <footer className="correlation-footer">
      <div className="correlation-source">
        <span>{current.history_days} daily returns to <time dateTime={current.as_of}>{dateLabel(current.as_of)}</time></span>
        {current.short_history && <strong>Limited price history</strong>}
        {mode === "historical" && MOCK && <span>Sample universe · One fixture date</span>}
      </div>
      {canBrowse && <div className="correlation-date">
        <label htmlFor={dateId}>As of <time dateTime={requested}>{dateLabel(requested)}</time></label>
        <input id={dateId} type="range" min={first} max={latest} value={dayNumber(requested)}
          aria-valuetext={dateLabel(requested)} onChange={(event) => {
            setFailed(null);
            setChoice({ context, date: isoDate(event.currentTarget.valueAsNumber) });
          }} />
      </div>}
      {isPending && <p className="correlation-request" role="status">Loading {dateLabel(requested)} · Showing {dateLabel(current.as_of)}</p>}
      {hasError && <p className="correlation-request" role="alert">
        Couldn’t load {dateLabel(requested)} · Showing {dateLabel(current.as_of)}
        <button type="button" className="correlation-button" onClick={() => { setFailed(null); setRetry(retry + 1); }}>Retry</button>
      </p>}
    </footer>
  </section>;
}

const partner = (pair: Pair, node: Node) => (pair.a === node ? pair.b : pair.a).symbol;

function pairFor(report: CorrelationReport, nodes: Node[], inspected: { a: string; b: string } | null): Pair | undefined {
  if (!inspected) return;
  const i = nodes.findIndex(({ ticker }) => ticker === inspected.a);
  const j = nodes.findIndex(({ ticker }) => ticker === inspected.b);
  const value = report.matrix[i]?.[j];
  if (Number.isFinite(value)) return { a: nodes[i], b: nodes[j], value, id: pairId(inspected.a, inspected.b) };
}

function Matrix({ report, nodes, selected, inspect }: {
  report: CorrelationReport; nodes: Node[]; selected?: Pair; inspect: (pair: Pair) => void;
}) {
  const [focus, setFocus] = useState([0, 0]);
  const n = nodes.length;
  function moveFocus(event: KeyboardEvent<HTMLButtonElement>, row: number, column: number) {
    const directions: Record<string, [number, number]> = {
      ArrowUp: [row - 1, column], ArrowDown: [row + 1, column], ArrowLeft: [row, column - 1],
      ArrowRight: [row, column + 1], Home: [row, 0], End: [row, n - 1],
    };
    const target = directions[event.key];
    if (!target) return;
    event.preventDefault();
    const [i, j] = target.map((value) => Math.max(0, Math.min(n - 1, value)));
    event.currentTarget.closest("table")?.querySelector<HTMLButtonElement>(`[data-cell="${i}-${j}"]`)?.focus();
  }

  return <div className="correlation-matrix-scroll">
    <table className="correlation-matrix" aria-label="Correlation matrix" style={{ minWidth: `${48 + 32 * n}px` }}>
      <thead><tr><td />{nodes.map(({ ticker, symbol }) => <th key={ticker} scope="col" title={ticker}>{symbol}</th>)}</tr></thead>
      <tbody>{nodes.map((a, i) => <tr key={a.ticker}>
        <th scope="row" title={a.ticker}>{a.symbol}</th>
        {nodes.map((b, j) => {
          const value = report.matrix[i]?.[j];
          if (!Number.isFinite(value)) return <td key={b.ticker} aria-label="Unavailable">–</td>;
          const pair = { a, b, value, id: pairId(a.ticker, b.ticker) };
          const tint = i === j ? "neutral" : value < 0 ? "negative" : "positive";
          return <td key={b.ticker}><button type="button" className="correlation-cell" data-tint={tint} data-cell={`${i}-${j}`}
            data-inspected={selected?.id === pair.id} tabIndex={Math.min(n - 1, focus[0]) === i && Math.min(n - 1, focus[1]) === j ? 0 : -1}
            style={{ "--correlation-strength": `${Math.round(strength(pair) * 54)}%` } as CSSProperties}
            aria-label={`${a.ticker} and ${b.ticker}, ${score(value)}. ${meaning(pair)}`}
            onFocus={() => { setFocus([i, j]); inspect(pair); }} onMouseEnter={() => inspect(pair)}
            onClick={() => inspect(pair)} onKeyDown={(event) => moveFocus(event, i, j)}>{score(value)}</button></td>;
        })}
      </tr>)}</tbody>
    </table>
  </div>;
}
