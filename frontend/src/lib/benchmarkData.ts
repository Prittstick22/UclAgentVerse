import type { HoldingPrices } from "./types";

export type BenchmarkPoint = { date: string; nav_gbp: number };
export type BenchmarkMetrics = {
  total_return: number; vol_annual: number; max_drawdown: number; sharpe: number;
  turnover?: number; costs_gbp: number; trades: number;
};
export type Benchmarks = {
  series: Record<string, BenchmarkPoint[]>; metrics: Record<string, BenchmarkMetrics>;
  periods: { development: [string, string]; held_out: [string, string | null] };
};

export const sp500Ticker = "VUAG.LSE";
export const sp500Key = "sp500_reference";
export const benchmarkNames: Record<string, string> = {
  ours: "Agent portfolio", ours_no_agents: "Engine only", ours_no_forecast: "Without return forecast",
  buy_and_hold: "Buy and hold", quarterly_rebalance: "Quarterly rebalance",
  global_etf: "Global ETF", mechanical_5pct: "5% rebalance", [sp500Key]: "S&P 500 · ETF",
};

export function joinBenchmarkSeries(series: Benchmarks["series"]) {
  const byDate = new Map<string, Record<string, string | number>>();
  for (const [name, points] of Object.entries(series)) {
    for (const { date, nav_gbp } of points) {
      if (!Number.isFinite(nav_gbp)) continue;
      const row = byDate.get(date) ?? { date };
      row[name] = nav_gbp;
      byDate.set(date, row);
    }
  }
  return [...byDate.values()].sort((a, b) => String(a.date).localeCompare(String(b.date)));
}

export function sp500ReturnSeries(prices: HoldingPrices | null | undefined, start: string, end: string) {
  if (prices?.ticker !== sp500Ticker || prices.as_of < end || start >= end) return [];
  const closes = new Map(prices.points.filter(({ date, close_gbp }) =>
    date >= start && date <= end && Number.isFinite(close_gbp) && close_gbp > 0,
  ).map(({ date, close_gbp }) => [date, close_gbp]));
  const first = closes.get(start);
  // Both endpoints must be available so the return covers the same window as the simulated strategies.
  if (first === undefined || !closes.has(end)) return [];
  return [...closes].sort(([a], [b]) => a.localeCompare(b)).map(([date, close]) => ({
    date, [sp500Key]: close / first - 1,
  }));
}
