# 07 · Engine and config

Owner: **Cem**. Code: `backend/app/engine/`, `backend/app/sim/`, `backend/app/monitors/`. Config: `backend/app/config/policy.yaml`, `params.yaml`.

## 1. Risk (`engine/risk.py`)

- **Returns:** daily log returns of `adj_close` in GBP.
- **Covariance:** Ledoit-Wolf shrinkage (`sklearn.covariance.LedoitWolf`) over a **504-trading-day lookback (minimum 252)**, annualised ×252.
- **Correlation:** `corr = D⁻¹ Σ D⁻¹`. `correlation_report` adds `avg_pairwise` and callouts for |ρ| ≥ 0.8 ("mostly rise and fall together") and ρ ≤ 0.2 ("diversify each other").
- **Also:** annualised vol, max drawdown, beta vs the global ETF, Herfindahl concentration.
- **Correlation never triggers trades on its own.**

## 2. Optimiser (`engine/optimiser.py`, CVXPY): uses code-made 2-week estimates, never LLM numbers

```
minimise    wᵀΣw − λ_return·μᵀw + λ_track·‖Bw − b*‖² + λ_turn·Σ cᵢ|wᵢ − w_now,ᵢ| + λ_fee·OCFᵀw
subject to  Σw + cash = 1,  w ≥ 0,  cash ≥ cash_min,  wᵢ ≤ capᵢ,
            L ≤ Bw ≤ U (asset-class ranges),  Σ_stocks w ≤ stocks_total,  w_excluded = 0
```

- B maps instruments → asset classes; b* is the midpoint of the mandate ranges.
- **Variants:**
  - `recommended`: the weights in params.yaml
  - `lower_cost`: λ_fee ×5
  - `lower_risk`: b* shifted to the lower equity bound, risk ×2
- **If infeasible,** return `status="infeasible"` + the binding constraints. Never loosen the mandate.
- **Solver:** CLARABEL or OSQP (bundled with cvxpy); fall back to SCS.

## 2a. Walk-forward 2-week forecast (`engine/forecast.py`, #73)

Each review looks **10 trading days ahead using only data up to that day**:
- `mu`: EWMA mean of daily returns (half-life weights the last 2 weeks most), shrunk towards 0 by `forecast.shrink`.
- `sigma`: EWMA volatility.
- Portfolio p10/p50/p90 over the horizon from the Ledoit-Wolf covariance.

Rules:
- It's always labelled **"estimate, not a promise"** and emitted as a `calc.result` (`forecast_2w`) so it's traceable.
- `forecast.lambda_return: 0` reproduces the no-forecast optimiser. Report both in the evaluation (ablation).
- **The forecast may only lean the portfolio, never rebuild it.** `mu` enters the optimiser scaled to the 2-week horizon (×10/252). The optimiser first solves without the forecast; the forecast may then move each holding at most `max_tilt_per_holding` (3 pp) and the portfolio at most `max_tilt_total` (10%, one-way) from that answer. All mandate limits still apply.
- **`lambda_return` is chosen on development data only** (before 7 Jul 2026), never on sim-window results: `python -m app.engine.forecast --calibrate`. Rule, fixed in advance: at each fortnightly development review and for every profile, measure the share of the portfolio the forecast moves on its own (caps off); pick the largest grid value whose median is ≤ 10% for all profiles. The tilt caps are a hard backstop on top.
- (Feature #74) Agent views (direction + confidence + evidence) become **capped** tilts on `mu` via code. Views without supported evidence are dropped.
- Walk-forward integrity is proven by `test_no_peeking` (#72): deleting or scrambling all data after day t changes nothing up to t.

## 3. Checker (`engine/checker.py`): independent, never imports the optimiser

- **`check_proposal`:**
  - weights sum to 1 (±1e-6) incl. cash
  - no negatives
  - per-fund / per-stock / stocks_total caps
  - asset-class ranges, cash_min
  - exclusions, eligibility
  - units/currency sanity
  - recomputed costs and turnover

  Returns a `CheckReport` with `passed`, a `violations[]` list (code, message, ticker, value, limit) and recomputed numbers.
  Violation codes: `not_a_number` (NaN, inf or a non-number; checked first, because NaN would slip through every comparison), `sum` (±1e-4: proposals round to 4 dp), `cash_min`, `ineligible`, `units` (currency/quote unit we can't value, e.g. GBX quoted but USD priced), `short`, `excluded` (ticker or sleeve), `concentration` (per fund / per stock), `equity_range`, `bond_range`, `stocks_total`. `recomputed` = equity, bond, stocks, other (e.g. commodity), cash, sum, `ocf_weighted`, plus `fees_gbp_per_year` (with nav), `turnover` (with current weights) and `cost_gbp` (with both). This is what the `calculation_recomputed` badge shows. Commodities have no range of their own; they're limited by the per-fund cap and by what the equity and bond minimums leave.
- **`revalidate`** (pre-execution, wired into `POST /api/proposals/{id}/approve` by #23): proposal and prices ≤ `risk.stale_after_days` (3) trading days old (`stale_data`), mandate unchanged (`mandate_changed`: version, and in the approval path also the content fingerprint), no trade filled since the proposal (`holdings_changed`), no identical pending order (`duplicate_order`).

## 4. Ledger (`engine/ledger.py`)

- **State:** positions (units, cost basis), GBP cash, pending orders, realised P&L, fills log.
- **Fills** happen at the close of t+1, with cost = `trade_cost × amount` + `fx_cost × amount` (USD instruments), charged on the amount **actually** traded: a sell never exceeds the units held, a buy is capped so that it plus its cost fits in the cash (cash never goes negative), and trades under `min_trade_gbp` (£25) are skipped. Sells run before buys. Each fill emits `order.filled {ticker, action, units, price_gbp, amount_gbp, cost_gbp}` (simulator).
- **Contributions** are invested by target with buys only (never a rebalance). They are cash flows, not returns: TWR strips them (`engine/metrics.py`).
- **Fund fees** accrue daily as `OCF/365 × value`.
- **P&L per holding:** unrealised (value − average cost basis), realised (on sells, at average cost; trading costs are counted separately in `costs_paid_gbp`) and contribution to return. Per period (since_purchase / 1m / 3m / ytd / sim_year) from the daily ledger checkpoints (`engine/portfolio.py`, `/api/portfolio/pnl`).

## 5. Metrics, backtest, exposure

- **`metrics.py`:** total return (money-weighted handling of contributions: report TWR), annualised vol, max drawdown, Sharpe (rf = 0, labelled), turnover, costs, trades.
- **`backtest.py`:** `run(gw, weights, start, end, rebalance)`. Asserts `end ≤ clock.now()`.
- **`exposure.py`:** look-through `Σ_fund w_fund × w_entity_in_fund + w_direct`. Labelled "ownership exposure, not predicted loss".

## 6. Simulator (`sim/`)

- **`runner.py`:** the day loop (03-how-it-works §3). It can run deterministic-only (`run_agents=False`) for the Tier 1 milestone, and emits `clock.tick`.
- **`benchmarks.py`:** `buy_and_hold`, `quarterly_rebalance`, `global_etf`, `mechanical_5pct`, each with the same contributions and cost model.
- **`approvals.py`:** `manual` (waits for the API) vs `batch_policy` (auto-approve if the gate passed and turnover ≤ limit; labelled `by: batch_policy`).

## 7. Monitors (`monitors/`)

- **`rules.py`:** drift, cap breach, price move (day / since review), NAV drop, news relevance (calls the Flash triage via the agents module), correlation regime.
- **`cooldowns.py`:** one ad hoc run per holding per 5 trading days; fold into the review if one is due within 2 days; group same-day price moves.
- **`templates.py`:** monitor spec templates for agent-designed monitors (05-agent-system §8).

## 8. Frozen config values (prototype policy, **not** a suitability assessment)

`policy.yaml`:

| Profile | Equity | Bonds | Cash min | Stocks total | Per stock | Per fund |
|---|---|---|---|---|---|---|
| cautious | 20–40% | 55–75% | 5% | 0% | 0% | 50% |
| balanced | 40–60% | 35–55% | 3% | 10% | 3% | 50% |
| growth | 60–80% | 15–35% | 2% | 15% | 4% | 60% |
| adventurous | 80–98% | 0–15% | 2% | 20% | 5% | 60% |

`params.yaml`:

| Key | Value |
|---|---|
| sim.start / end | 2026-07-07 / latest snapshot date (4 months) |
| capital_gbp / monthly_contribution_gbp | 10000 / 200 |
| review_every_n_days | 10 |
| triggers | drift_pp 0.05 · price_move_day 0.05 · price_move_since_review 0.10 · nav_drop 0.05 · news_relevance 0.7 · corr_jump 0.15 |
| cooldown_days / fold_into_review_days | 5 / 2 |
| min_trade_gbp | 25 |
| costs | trade 0.0010 · fx 0.0015 (labelled assumptions) |
| batch_auto_approve_turnover_max | 0.10 |
| optimiser | λ_track 5 · λ_turn 1 · λ_fee 1 · lookback 504 · min_lookback 252 |
| forecast | horizon_days 10 · ewma_halflife_days 10 · shrink 0.5 · lambda_return 0.05 (calibrated, development data only) · max_tilt_per_holding 0.03 · max_tilt_total 0.10 · max_view_tilt 0.02 |
| periods | development 2023-01-02 → 2026-07-06 (pre-sim, sanity checks only) · held_out 2026-07-07 → end |

**Freeze rule:** sanity-check on 2023–2025 data only; freeze before the full-year run (09-build-plan). Don't tune on sim-year results.
