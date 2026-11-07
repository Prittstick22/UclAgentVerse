// SCAFFOLD: CSS-grid heatmap. TODO(#fe-lattice): date slider, hover detail, legend, network view (T3).
import { Fragment } from "react";
import type { CorrelationReport } from "../lib/types";

const colour = (c: number) => (c >= 0 ? `rgba(16,185,129,${Math.min(c, 1)})` : `rgba(244,63,94,${Math.min(-c, 1)})`);

export default function CorrelationLattice({ report }: { report: CorrelationReport }) {
  const n = report.tickers.length;
  return (
    <div>
      <h2 className="text-sm text-slate-400 mb-2">How your holdings move together (as of {report.as_of})</h2>
      <div className="inline-grid gap-px text-[10px]" style={{ gridTemplateColumns: `80px repeat(${n}, 36px)` }}>
        <div />
        {report.tickers.map((t) => <div key={t} className="truncate text-slate-400">{t.split(".")[0]}</div>)}
        {report.matrix.map((row, i) => (
          <Fragment key={i}>
            <div className="truncate text-slate-400">{report.tickers[i].split(".")[0]}</div>
            {row.map((c, j) => <div key={`${i}-${j}`} title={c.toFixed(2)} className="h-9 w-9" style={{ background: colour(c) }} />)}
          </Fragment>
        ))}
      </div>
      <ul className="mt-3 text-sm text-slate-300 space-y-1">{report.callouts.slice(0, 4).map((c) => <li key={c.a + c.b}>{c.text}</li>)}</ul>
    </div>
  );
}
