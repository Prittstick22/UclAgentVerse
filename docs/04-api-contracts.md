# 04 · API contracts (CONTRACT FILE)

> **Enforced by CI:** `backend/tests/test_contract.py` fails if an endpoint exists in code but not here, or here but not in code.
>
> Changing anything here requires, in the same PR, updates to `backend/app/schemas.py` / `backend/app/core/events.py`, `frontend/src/lib/types.ts`, `fixtures/` (run `make fixtures`), plus a `contract-change` post on the board.

## 0. Conventions

- **Base path** `/api`. JSON, `snake_case` fields. Dates are `YYYY-MM-DD`; timestamps are ISO-8601 UTC.
- **Money** is GBP as a number with 2 dp (`value_gbp`). **Weights** are fractions 0–1, not percent. **Returns** are fractions (`0.052` = 5.2%).
- **Mode:** most `GET`s accept `?mode=historical|live` (default: the current server mode). Responses include `mode` and `as_of`.
- **Errors:** HTTP 4xx/5xx with:
  ```json
  {"error": {"code": "mandate_violation", "message": "Per-stock cap 5% exceeded for NVDA (25%)", "details": {}}}
  ```
  Codes: `not_found`, `validation_error`, `mandate_violation`, `asof_violation`, `infeasible`, `budget_exceeded`, `stale_data`, `duplicate_order`, `unauthorized`, `rate_limited`, `internal`.
- **Protected endpoints** (live investigations, chat in public deploy, `/api/tasks/*`) need the `X-Demo-Passcode` or `X-Task-Secret` header.

## 1. Shared models

```ts
type Mode = "historical" | "live";
type AssetClass = "equity" | "bond" | "cash" | "commodity";
type ProfileName = "cautious" | "balanced" | "growth" | "adventurous";
type HomeStatus = "monitoring_normally" | "investigating" | "awaiting_approval" | "monitoring_degraded";
type TriggerKind = "construction" | "review" | "drift" | "cap_breach" | "price_move" | "nav_drop" | "news" | "corr_regime" | "chat" | "retrospective" | "manual";
type GateName = "injection_guard" | "evidence" | "numbers" | "mandate" | "critic" | "compliance" | "qa" | "revalidation";
type GateStatus = "pending" | "pass" | "pass_with_flags" | "fail" | "skipped";
type Badge = "source_retrieved" | "claim_supported" | "relationship_uncertain" | "calculation_recomputed" | "judgement_uncertain";

interface Instrument {
  ticker: string;            // provider symbol, e.g. "VWRP.LSE", "AAPL.US"
  name: string;
  isin: string | null;
  asset_class: AssetClass;
  sleeve: string;            // "global_equity" | "us_equity" | "uk_gilts" | ...
  currency: "GBP" | "USD" | "EUR";
  quote_unit: "GBP" | "GBX" | "USD";
  ocf: number;               // annual fee, fraction
  accumulating: boolean;
  kind: "etf" | "stock";
  eligible: boolean;
  data_source: string;       // "eodhd" | "yfinance" | "synthetic"
}

interface Mandate {
  version: number;
  profile: ProfileName;
  goal: { name: string; target_date: string; starting_amount_gbp: number; monthly_contribution_gbp: number };
  ranges: { equity: [number, number]; bond: [number, number]; cash_min: number };
  caps: { per_fund: number; per_stock: number; stocks_total: number };
  exclusions: string[];      // tickers or sleeves
  review_every_n_days: number;           // 10 = fortnightly
  triggers: { drift_pp: number; price_move_day: number; price_move_since_review: number; nav_drop: number; news_relevance: number };
  approval: { require_user_approval: boolean; batch_auto_approve_turnover_max: number };
}

interface Holding {
  ticker: string; name: string; asset_class: AssetClass;
  units: number; price_gbp: number; value_gbp: number;
  weight: number; target_weight: number;
  cost_basis_gbp: number;
  unrealised_pnl_gbp: number; unrealised_pnl_pct: number;
  realised_pnl_gbp: number;
  contribution_to_return: number;        // fraction of portfolio return over the selected period
  price_as_of: string; stale: boolean;
  purpose: string | null; case_id: string | null;
}

interface Portfolio {
  mode: Mode; as_of: string;
  nav_gbp: number; cash_gbp: number; invested_gbp: number; contributions_gbp: number;
  total_return: number; status: HomeStatus;
  last_review_date: string | null; next_review_date: string | null;
  holdings: Holding[];
  counters: { reviews: number; checks: number; decisions_asked: number; adjustments: number };
}

interface Evidence {
  id: string; kind: "price" | "news" | "filing" | "calc" | "catalogue" | "web";
  title: string; source: string; url: string | null;
  published_at: string | null; available_at: string; excerpt: string | null;
  data: Record<string, unknown> | null;  // e.g. calc inputs/outputs
  quarantined: boolean;
}

interface ProposedHolding { ticker: string; weight: number; purpose: string; why_not_alternatives: string; evidence_ids: string[] }
interface PortfolioOption {
  label: "recommended" | "lower_cost" | "lower_risk" | "current" | "proposed";
  holdings: ProposedHolding[];
  stats: { vol_annual: number; ocf_weighted: number; turnover: number; cost_gbp: number; max_drawdown_backtest: number | null };
}
interface GateResult { gate: GateName; status: GateStatus; issues: string[]; agent_id: string | null }
interface OrderChange { ticker: string; action: "buy" | "sell"; amount_gbp: number; from_weight: number; to_weight: number }
interface DecisionCard { headline: string; body: string; changes: OrderChange[]; risk_warning: string; simulated: boolean }

interface Proposal {
  id: string; run_id: string; kind: "construction" | "adjustment"; as_of: string; created_at: string;
  options: PortfolioOption[]; selected: string;
  gates: GateResult[];
  decision_card: DecisionCard;
  uncertainties: string[];
  status: "draft" | "awaiting_approval" | "approved" | "declined" | "blocked" | "expired" | "executed";
}

interface RunSummary {
  run_id: string; kind: TriggerKind; trigger_text: string; as_of: string;
  status: "running" | "completed" | "failed" | "cancelled";
  outcome: "maintain" | "adjust" | "investigate_further" | "built" | "answered" | null;
  started_at: string; finished_at: string | null;
  agents: AgentNode[]; proposal_id: string | null;
}
interface AgentNode {
  agent_id: string; parent_agent_id: string | null; depth: number; role: string; model: string;
  question: string; purpose: string; status: "queued" | "running" | "done" | "failed" | "denied";
  badges: Badge[];
}
```

## 2. Endpoints

| Method + path | Body / query | Response | Owner |
|---|---|---|---|
| `GET /api/health` | — | `{status:"ok", mode, as_of, version, llm_mode, data_source}` | Jin |
| `GET /api/mode` | — | `{mode, as_of, sim:{running, speed, start, end}}` | Jin |
| `POST /api/mode` | `{mode}` | same as GET | Jin |
| `GET /api/profile/questions` | — | `{questions: Question[]}`, where `Question = {id, text, help, measures: "tolerance"\|"capacity"\|"context", options: {id, label}[]}` | Jin |
| `POST /api/profile/quiz` | `{answers: {[qid]: option_id}, goal: Mandate.goal, exclusions: string[]}` | `{profile: {name, tolerance_score, capacity_score, conflict: boolean, follow_up_question: string\|null, explanation: string}, mandate: Mandate}` | Jin |
| `GET /api/mandate` | — | `Mandate` | Jin |
| `PUT /api/mandate` | `Mandate` | `Mandate` (version+1), or 422 `validation_error` | Jin |
| `GET /api/catalogue` | — | `{instruments: Instrument[]}` | Jin |
| `POST /api/portfolio/build` | `{mandate_version?: number}` | `{run_id}` (202) | Dev |
| `GET /api/portfolio` | `?mode` | `Portfolio` | Mo |
| `GET /api/portfolio/history` | `?mode&start&end` | `{points: {date, nav_gbp, weights: {[ticker]: number}, contributions_gbp: number\|null}[]}` | Mo |
| `GET /api/portfolio/pnl` | `?mode&period=since_purchase\|1m\|3m\|ytd\|sim_year` | `{period, rows: {ticker, name, pnl_gbp, pnl_pct, realised_gbp, unrealised_gbp, contribution_to_return}[], total_pnl_gbp}` | Mo |
| `GET /api/portfolio/rebalances` | `?mode&limit=20` | `{items: {date, run_id, trigger_kind, trigger_text, changes: OrderChange[], cost_gbp}[]}` | Mo |
| `GET /api/benchmarks` | `?mode` | `{series: {[name]: {date, nav_gbp}[]}, metrics: {[name]: Metrics}, periods: {development: [start, end], held_out: [start, end]}}`, where `Metrics = {total_return, vol_annual, max_drawdown, sharpe, turnover, costs_gbp, trades}`; names: `ours`, `buy_and_hold`, `quarterly_rebalance`, `global_etf`, `mechanical_5pct` | Cem |
| `GET /api/risk/correlation` | `?mode&as_of&lookback&tickers` (`lookback` default = params `optimiser.lookback`, 504; `as_of` = any past date, future → 400 `asof_violation`) | `{as_of, lookback, tickers: string[], matrix: number[][], avg_pairwise: number, callouts: {a, b, corr, text}[], history_days: number, short_history: boolean}` (`short_history` = fewer than 252 return rows were available; used anyway, flagged) | Cem |
| `GET /api/runs` | `?mode&kind&limit` | `{items: RunSummary[]}` (agents omitted) | Jin |
| `GET /api/runs/{run_id}` | — | `RunSummary` | Jin |
| `GET /api/runs/{run_id}/events` | `?after=seq&format=sse\|json` | SSE stream of `Event` (default), or `{items: Event[]}` | Jin |
| `GET /api/events/stream` | `?mode` | SSE of **all** new events (home/timeline live updates) | Jin |
| `GET /api/proposals/{id}` | — | `Proposal` | Dev |
| `POST /api/proposals/{id}/approve` | `{option?: label}` | `{proposal: Proposal, orders: OrderChange[], fill_date: string}` or 409 `stale_data` / `duplicate_order` / `mandate_violation` | Cem |
| `POST /api/proposals/{id}/decline` | `{reason?: string}` | `{proposal: Proposal}` | Cem |
| `GET /api/evidence/{id}` | — | `Evidence` | Jin |
| `GET /api/notifications` | `?mode&unread=true` | `{items: {id, kind: "decision"\|"digest"\|"coverage", title, body, proposal_id, run_id, created_at, read}[]}` | Jin |
| `POST /api/notifications/{id}/read` | — | `{ok: true}` | Jin |
| `POST /api/sim/start` | `{start?: date, end?: date, speed?: number, run_agents?: boolean}` | `{sim}` | Cem |
| `POST /api/sim/pause` · `POST /api/sim/step` | `{days?: number}` | `{sim, as_of}` | Cem |
| `GET /api/sim/status` | — | `{sim, as_of, progress: number}` | Cem |
| `POST /api/chat` | `{message, conversation_id?}` | `{conversation_id, run_id, answer, citations: string[], proposal_id: string\|null}` | Dev |
| `POST /api/tasks/live-eod` · `POST /api/tasks/live-news` | header `X-Task-Secret` | `{ok, fetched, stale: string[]}` | Jin |

Portfolio dates are inclusive and capped at the active `as_of`. History points from older `clock.tick` recordings use `null` when contributions were never recorded. Portfolio detail or period P&L returns `409 validation_error` when the available recording lacks the ledger data needed for the response. Rebalances list filled approvals newest first and use the recorded execution date and costs.

## 3. Events (SSE)

The SSE frame is `event: <type>\ndata: <Event JSON>\n\n`. A heartbeat comment `: ping` is sent every 15 s.

```ts
interface Event {
  id: string;                 // ulid
  run_id: string | null;      // null for clock/system events
  seq: number;                // monotonic per run (global for run_id=null)
  ts_wall: string;            // real time emitted
  as_of: string;              // sim date (historical) or now (live)
  mode: Mode;
  type: EventType;
  agent_id: string | null; parent_agent_id: string | null; depth: number | null; role: string | null;
  title: string;              // short, human-readable, shown in UI
  purpose: string | null;
  status: "started" | "running" | "ok" | "failed" | "denied" | null;
  trigger_kind: TriggerKind | null; trigger_text: string | null;
  case_id: string | null;
  evidence_ids: string[];
  payload: Record<string, unknown>;   // per-type, see below
}
```

| `type` | Emitted by | `payload` |
|---|---|---|
| `run.started` | supervisor | `{kind, trigger_text, limits}` |
| `run.completed` | supervisor | `{outcome, proposal_id, tokens, cost_estimate_usd, duration_s}` |
| `agent.spawn_requested` | supervisor | `{role, question, purpose, deep}` |
| `agent.spawned` | supervisor | `{role, model, question}` |
| `agent.spawn_denied` | supervisor | `{role, reason: "max_depth"\|"max_agents"\|"budget"\|"role_not_allowed"}` |
| `agent.status` | supervisor | `{status}` |
| `agent.message` | agent (concise explanation, not raw thoughts) | `{text}` |
| `tool.call` | tool wrapper | `{tool, args}` |
| `tool.result` | tool wrapper | `{tool, ok, summary, result_ref}` |
| `source.inspect` | tool wrapper | `{evidence_id, kind, title, source, published_at}` |
| `calc.result` | engine tool | `{name, inputs, outputs}` |
| `finding` | agent | `{claim, confidence, uncertainties, recommendation}` |
| `gate.started` / `gate.verdict` | gate | `{gate, status, issues, required_changes}` |
| `revision.requested` | gate | `{by_gate, points}` |
| `content.quarantined` | guard | `{evidence_id, reason}` |
| `budget.exceeded` | supervisor | `{limit, value}` |
| `asof.violation` | gateway | `{requested_end, as_of, caller}` |
| `decision.made` | lead | `{action: "maintain"\|"adjust"\|"investigate_further", reason}` |
| `proposal.created` | supervisor | `{proposal_id, kind}` |
| `approval.requested` / `approval.decided` | approvals | `{proposal_id, decision, by: "user"\|"batch_policy"}` |
| `order.filled` | ledger | `{ticker, action, units, price_gbp, amount_gbp, cost_gbp}` |
| `monitor.fired` | monitors | `{monitor_id, rule, ticker, value, threshold}` |
| `monitor.created` / `monitor.shadow_result` / `monitor.activated` / `monitor.disabled` | monitors | `{monitor_id, spec?, result?}` |
| `rule.proposed` / `rule.tested` / `rule.promoted` / `rule.applied` | learning | `{rule_id, text, results?}` |
| `clock.tick` | simulator | `{nav_gbp, weights, benchmarks: {[name]: nav_gbp}, status}` |
| `mode.changed` | api | `{mode}` |
| `notification.created` | api | `{notification_id, kind}` |

## 4. Python ↔ Python interfaces (between owners)

```python
# Engine (Cem), called by agents' tools (Dev) and the simulator
engine.risk.covariance(returns: pd.DataFrame) -> pd.DataFrame          # Ledoit-Wolf, annualised
engine.risk.correlation_report(prices, as_of, lookback=None, names=None) -> CorrelationReport   # lookback None = params 504
engine.risk.risk_stats(weights, prices, benchmark=None, lookback=None) -> RiskStats   # vol, max_drawdown, beta, herfindahl, history flag
engine.optimiser.optimise(req: OptimiseRequest) -> OptimiseResult        # variant: recommended|lower_cost|lower_risk; optional req.mu (pd.Series, from engine.forecast, #73); status "error" if a candidate has no risk data
engine.forecast.forecast(gw, tickers, as_of, horizon=None, weights=None) -> Forecast   # #73: mu (annualised, dict), assets[{ticker, mu_annual, sigma_annual, band{p10,p50,p90}, obs}], portfolio band, skipped, label 'estimate, not a promise'
engine.checker.check_proposal(proposal_weights, mandate, catalogue, prices) -> CheckReport   # numbers + mandate
engine.checker.revalidate(proposal, ledger, gw) -> CheckReport
engine.backtest.run(gw, weights, start, end, rebalance="quarterly") -> BacktestResult   # end <= as_of enforced
engine.exposure.look_through(holdings, etf_holdings, entity) -> ExposureResult

# Data (Jin), the ONLY way to read data
gw.prices(tickers, start, end=None) -> pd.DataFrame   # end defaults to clock.now(); end > now -> AsOfViolation
gw.fx(pair, start, end=None) -> pd.Series
gw.news(tickers, since, until=None) -> list[NewsItem] # available_at <= now
gw.filings(company, since, until=None) -> list[Filing]
gw.catalogue() -> list[Instrument]
gw.freshness() -> dict[str, Freshness]

# Events (Jin)
events.emit(type, *, run_id=None, title, **fields) -> Event
```
