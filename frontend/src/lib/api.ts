// API client. In mock mode (VITE_MOCK=1, default in dev) it serves ../fixtures/*.json, so the UI works without a backend.
import type { AgentEvent, CorrelationReport, Health, Mandate, Portfolio, ProfileResult, Question, RunSummary } from "./types";

export const MOCK = import.meta.env.VITE_MOCK === "1";

const fixtures = import.meta.glob("../../../fixtures/*.json", { eager: true, import: "default" }) as Record<string, unknown>;
const fx = <T,>(name: string): T => {
  const hit = Object.entries(fixtures).find(([k]) => k.endsWith(`/${name}.json`));
  if (!hit) throw new Error(`fixture ${name} missing: run \`make fixtures\``);
  return hit[1] as T;
};

async function get<T>(path: string, mock: string): Promise<T> {
  if (MOCK) return fx<T>(mock);
  const r = await fetch(`/api${path}`);
  if (!r.ok) throw new Error((await r.json()).error?.message ?? r.statusText);
  return r.json();
}
async function post<T>(path: string, body: unknown, mock: string): Promise<T> {
  if (MOCK) return fx<T>(mock);
  const r = await fetch(`/api${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!r.ok) throw new Error((await r.json()).error?.message ?? r.statusText);
  return r.json();
}

export const api = {
  health: () => get<Health>("/health", "health"),
  questions: () => get<{ questions: Question[] }>("/profile/questions", "questions"),
  quiz: (answers: Record<string, string>) => post<{ profile: ProfileResult; mandate: Mandate }>("/profile/quiz", { answers }, "quiz_result"),
  mandate: () => get<Mandate>("/mandate", "mandate"),
  portfolio: () => get<Portfolio>("/portfolio", "portfolio"),
  correlation: () => get<CorrelationReport>("/risk/correlation", "correlation"),
  runs: () => get<{ items: Omit<RunSummary, "agents">[] }>("/runs", "runs"),
  runDetail: (runId: string) => get<RunSummary>(`/runs/${encodeURIComponent(runId)}`, "run_detail"),
  build: () => post<{ run_id: string }>("/portfolio/build", {}, "runs").then((r) => ("run_id" in r ? r : { run_id: "mock" })),
  // TODO(#fe-*): pnl, rebalances, benchmarks, proposals, approve/decline, notifications, evidence, chat, sim controls
};

export const mockEvents = (): AgentEvent[] => fx<AgentEvent[]>("events_construction");
