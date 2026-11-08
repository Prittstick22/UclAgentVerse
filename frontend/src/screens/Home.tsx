// SCAFFOLD: portfolio summary + correlation lattice. TODO(#fe-home, #fe-pnl, #fe-lattice, #fe-rebalances): full home screen.
import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { CorrelationReport, Portfolio } from "../lib/types";
import CorrelationLattice from "../components/CorrelationLattice";

export default function Home() {
  const [p, setP] = useState<Portfolio | null>(null);
  const [corr, setCorr] = useState<CorrelationReport | null>(null);
  useEffect(() => { api.portfolio().then(setP); api.correlation().then(setCorr); }, []);
  return (
    <div className="space-y-6">
      <div className="flex gap-6">
        <Stat label="Portfolio value" value={p ? `£${p.nav_gbp.toLocaleString()}` : "…"} />
        <Stat label="Status" value={p?.status.replaceAll("_", " ") ?? "…"} />
        <Stat label="Decisions asked of you" value={String(p?.counters.decisions_asked ?? 0)} />
      </div>
      {p?.mode === "live" && <section className="rounded-xl bg-slate-900 p-4">
        <h2 className="font-semibold mb-2">Cached market prices</h2>
        {p.holdings.length === 0 ? <p className="text-sm text-slate-400">No paper holdings yet.</p> :
          <table className="w-full text-sm text-left">
            <thead><tr><th>Holding</th><th>Price</th><th>Price date</th><th>Coverage</th></tr></thead>
            <tbody>{p.holdings.map((holding) => <tr key={holding.ticker}>
              <td className="py-2">{holding.name}</td>
              <td>£{holding.price_gbp.toFixed(2)}</td><td>{holding.price_as_of}</td>
              <td>{holding.stale ? "Stale · last available" : "Cached close"}</td>
            </tr>)}</tbody>
          </table>}
      </section>}
      {corr && <CorrelationLattice report={corr} />}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return <div className="rounded-xl bg-slate-900 px-4 py-3"><div className="text-xs text-slate-400">{label}</div><div className="text-lg capitalize">{value}</div></div>;
}
