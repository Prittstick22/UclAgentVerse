// CONTRACT FILE: mirror of docs/04-api-contracts.md and backend/app/schemas.py + core/events.py.
// Change only together with those files + a board `contract-change` post.

export type Mode = "historical" | "live";
export type AssetClass = "equity" | "bond" | "cash" | "commodity";
export type ProfileName = "cautious" | "balanced" | "growth" | "adventurous";
export type HomeStatus = "monitoring_normally" | "investigating" | "awaiting_approval" | "monitoring_degraded";
export type TriggerKind =
  | "construction" | "review" | "drift" | "cap_breach" | "price_move" | "nav_drop" | "news"
  | "corr_regime" | "chat" | "retrospective" | "manual";
export type GateName = "injection_guard" | "evidence" | "numbers" | "mandate" | "critic" | "compliance" | "qa" | "revalidation";
export type GateStatus = "pending" | "pass" | "pass_with_flags" | "fail" | "skipped";
export type Badge = "source_retrieved" | "claim_supported" | "relationship_uncertain" | "calculation_recomputed" | "judgement_uncertain";

export interface Health { status: string; mode: Mode; as_of: string; version: string; llm_mode: string; data_source: string }

export interface NewsItem {
  id: string; tickers: string[]; headline: string; summary: string; url: string | null;
  source: string; published_at: string; available_at: string; synthetic: boolean;
}
export interface NewsFeed { as_of: string; items: NewsItem[] }

export interface Evidence {
  id: string; kind: "price" | "news" | "filing" | "calc" | "catalogue" | "web" | "case" | "proposal" | "earnings";
  title: string; source: string; url: string | null;
  published_at: string | null; available_at: string; excerpt: string | null;
  data: Record<string, unknown> | null; quarantined: boolean;
}

export interface QuestionOption { id: string; label: string }
export interface Question { id: string; text: string; help: string; measures: "tolerance" | "capacity" | "context"; options: QuestionOption[] }

export interface Goal { name: string; target_date: string; starting_amount_gbp: number; monthly_contribution_gbp: number }
export interface Mandate {
  version: number; profile: ProfileName; goal: Goal;
  ranges: { equity: [number, number]; bond: [number, number]; cash_min: number };
  caps: { per_fund: number; per_stock: number; stocks_total: number };
  exclusions: string[]; review_every_n_days: number;
  triggers: { drift_pp: number; price_move_day: number; price_move_since_review: number; nav_drop: number; news_relevance: number };
  approval: { require_user_approval: boolean; batch_auto_approve_turnover_max: number };
}
export interface ProfileResult { name: ProfileName; tolerance_score: number; capacity_score: number; conflict: boolean; follow_up_question: string | null; explanation: string }
export interface QuizRequest {
  answers: Record<string, string>; goal?: Goal | null; exclusions?: string[];
  follow_up_answer?: "yes" | "no" | null;
}
export interface DemoProfile {
  name: string; age: number; story: string; profile: ProfileName; goal: Goal;
  answers: Record<string, string>; synthetic: true; result: ProfileResult; mandate: Mandate;
}

export interface Holding {
  ticker: string; name: string; asset_class: AssetClass; units: number; price_gbp: number; value_gbp: number;
  weight: number; target_weight: number; cost_basis_gbp: number; unrealised_pnl_gbp: number; unrealised_pnl_pct: number;
  realised_pnl_gbp: number; contribution_to_return: number; price_as_of: string; stale: boolean;
  purpose: string | null; case_id: string | null;
}
export interface Portfolio {
  mode: Mode; as_of: string; nav_gbp: number; cash_gbp: number; invested_gbp: number; contributions_gbp: number;
  total_return: number; status: HomeStatus; last_review_date: string | null; next_review_date: string | null;
  holdings: Holding[]; counters: { reviews: number; checks: number; decisions_asked: number; adjustments: number };
}

export interface HoldingPrices { ticker: string; as_of: string; points: { date: string; close_gbp: number }[] }

export interface PortfolioHistory {
  points: { date: string; nav_gbp: number; weights: Record<string, number>; contributions_gbp: number | null }[];
}

export type PnlPeriod = "since_purchase" | "1m" | "3m" | "ytd" | "sim_year";
export interface PortfolioPnl {
  period: PnlPeriod;
  rows: { ticker: string; name: string; pnl_gbp: number; pnl_pct: number; realised_gbp: number;
    unrealised_gbp: number; contribution_to_return: number }[];
  total_pnl_gbp: number;
}

export interface PortfolioRebalances {
  items: { date: string; run_id: string; trigger_kind: TriggerKind; trigger_text: string;
    changes: OrderChange[]; cost_gbp: number }[];
}

export interface Notification {
  id: string; kind: "decision" | "digest" | "coverage"; title: string; body: string;
  proposal_id: string | null; run_id: string | null; created_at: string; read: boolean;
}

export interface CorrelationReport { as_of: string; lookback: number; tickers: string[]; matrix: number[][]; avg_pairwise: number; callouts: { a: string; b: string; corr: number; text: string }[]; history_days: number; short_history: boolean }

export interface AgentNode { agent_id: string; parent_agent_id: string | null; depth: number; role: string; model: string; question: string; purpose: string; status: "queued" | "running" | "done" | "failed" | "denied"; badges: Badge[] }
export interface RunSummary {
  run_id: string; kind: TriggerKind; trigger_text: string; as_of: string; status: "running" | "completed" | "failed" | "cancelled";
  outcome: "maintain" | "adjust" | "investigate_further" | "built" | "answered" | null;
  started_at: string; finished_at: string | null; agents: AgentNode[]; proposal_id: string | null;
}

export interface GateResult { gate: GateName; status: GateStatus; issues: string[]; agent_id: string | null }
export interface OrderChange { ticker: string; action: "buy" | "sell"; amount_gbp: number; from_weight: number; to_weight: number }
export interface DecisionCard { headline: string; body: string; changes: OrderChange[]; risk_warning: string; simulated: boolean }

export type EventType =
  | "run.started" | "run.completed" | "agent.spawn_requested" | "agent.spawned" | "agent.spawn_denied" | "agent.status"
  | "agent.message" | "tool.call" | "tool.result" | "source.inspect" | "calc.result" | "finding" | "gate.started"
  | "gate.verdict" | "revision.requested" | "content.quarantined" | "budget.exceeded" | "asof.violation" | "decision.made"
  | "proposal.created" | "approval.requested" | "approval.decided" | "order.filled" | "monitor.fired" | "monitor.created"
  | "monitor.shadow_result" | "monitor.activated" | "monitor.disabled" | "rule.proposed" | "rule.tested" | "rule.promoted"
  | "rule.applied" | "clock.tick" | "mode.changed" | "notification.created" | "mandate.updated";

export interface AgentEvent {
  id: string; run_id: string | null; seq: number; ts_wall: string; as_of: string; mode: Mode; type: EventType;
  agent_id: string | null; parent_agent_id: string | null; depth: number | null; role: string | null;
  title: string; purpose: string | null; status: "started" | "running" | "ok" | "failed" | "denied" | null;
  trigger_kind: TriggerKind | null; trigger_text: string | null; case_id: string | null;
  evidence_ids: string[]; payload: Record<string, unknown>;
}
