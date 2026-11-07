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
      {corr && <CorrelationLattice report={corr} />}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return <div className="rounded-xl bg-slate-900 px-4 py-3"><div className="text-xs text-slate-400">{label}</div><div className="text-lg capitalize">{value}</div></div>;
}
