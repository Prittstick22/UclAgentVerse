import { get } from "./api";
import type { CorrelationReport, Notification, PnlPeriod, Portfolio, PortfolioHistory, PortfolioPnl, RunSummary } from "./types";

export type ReviewSummary = Omit<RunSummary, "agents">;

export const portfolioQueries = {
  summary: (signal: AbortSignal) => get<Portfolio>("/portfolio", "portfolio", signal),
  history: (signal: AbortSignal) => get<PortfolioHistory>("/portfolio/history", "history", signal),
  async pnl(period: PnlPeriod, signal: AbortSignal) {
    const result = await get<PortfolioPnl>(`/portfolio/pnl?period=${period}`, "pnl", signal);
    if (result.period !== period) throw new Error("The selected period is unavailable in this data source.");
    return result;
  },
  correlations: (tickers: string, signal: AbortSignal) =>
    get<CorrelationReport>(`/risk/correlation?tickers=${encodeURIComponent(tickers)}`, "correlation", signal),
  reviewDetail: (id: string, signal: AbortSignal) =>
    get<RunSummary>(`/runs/${encodeURIComponent(id)}`, "run_detail", signal),
  notifications: (signal: AbortSignal) => get<{ items: Notification[] }>("/notifications", "notifications", signal),
  async reviews(signal: AbortSignal) {
    const { items } = await get<{ items: ReviewSummary[] }>("/runs?kind=review&limit=100", "runs", signal);
    return items.filter((item) => item.kind === "review").reverse();
  },
};
