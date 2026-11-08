import { finance } from "../lib/financeTerms";
import { record, recordedValuePoints } from "../lib/investigation";
import type { AgentEvent, PortfolioRebalances } from "../lib/types";
import { gbp, pct } from "../screens/Decisions";

const chartMoney = new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP", maximumFractionDigits: 0 });

export function FilledAllocation({ fill }: { fill?: PortfolioRebalances["items"][number] }) {
  const changes = fill?.changes.filter(row => Number.isFinite(row.from_weight) && Number.isFinite(row.to_weight)) ?? [];
  if (!changes.length) return null;
  const scale = Math.max(...changes.flatMap(row => [row.from_weight, row.to_weight]), 0.01);
  return <figure className="report-figure">
    <figcaption><strong>Allocation before and after the latest trades</strong>
      <span>Share of the portfolio on {fill?.date} · {finance.weightChange}</span></figcaption>
    <ul className="report-allocation">
      {changes.map(row => <li key={row.ticker}>
        <strong>{row.ticker}</strong>
        <div className="report-weight-bars" aria-hidden="true">
          <span style={{ width: 100 * row.from_weight / scale + "%" }} />
          <span style={{ width: 100 * row.to_weight / scale + "%" }} />
        </div>
        <span>{pct.format(row.from_weight)} → <strong>{pct.format(row.to_weight)}</strong></span>
      </li>)}
    </ul>
  </figure>;
}

export function RecordedValuePath({ event, asOf }: { event?: AgentEvent; asOf: string }) {
  if (event?.type !== "calc.result") return null;
  const outputs = record(event.payload.outputs);
  const points = recordedValuePoints(outputs.backtest_nav ?? outputs.nav, event.as_of || asOf);
  const first = points[0];
  const last = points.at(-1);
  if (!first || !last || first.time === last.time) return null;
  const valuesInPounds = points.map(point => point.value);
  const bottom = Math.min(...valuesInPounds);
  const top = Math.max(...valuesInPounds);
  const span = top - bottom || 1;
  const line = points.map(point =>
    (79 + 543 * (point.time - first.time) / (last.time - first.time)).toFixed(2) + "," +
    (15 + 100 * (top - point.value) / span).toFixed(2)).join(" ");
  const ticks = bottom === top ? [top] : [top, (top + bottom) / 2, bottom];
  return <figure className="report-figure">
    <figcaption><strong>Historical simulation</strong>
      <span>{first.date} to {last.date} · Simulated value moved from {gbp.format(first.value)} to {gbp.format(last.value)} using past prices.</span></figcaption>
    <svg className="report-value-path" viewBox="0 0 642 142" role="img" aria-label="Historical simulated portfolio value in pounds">
      {ticks.map(value => {
        const y = 15 + 100 * (top - value) / span;
        return <g key={value}><line x1="79" x2="622" y1={y} y2={y} />
          <text x="70" y={y + 4} textAnchor="end">{chartMoney.format(value)}</text></g>;
      })}
      <polyline points={line} />
      <text x="79" y="136">{first.date}</text><text x="622" y="136" textAnchor="end">{last.date}</text>
    </svg>
  </figure>;
}
