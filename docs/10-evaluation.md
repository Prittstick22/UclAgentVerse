# 10 · Evaluation (25% of the score: "unseen-data testing")

Owner: **Cem** (numbers), **Dev** (slide).

## Strategies

Every strategy gets the same £10,000, the same £200/month and the same cost model.

| Name | Rule |
|---|---|
| `ours` | Full system: fortnightly agent reviews + triggers + gate (batch-policy approvals) |
| `buy_and_hold` | The initial approved portfolio, never rebalanced; contributions pro rata |
| `quarterly_rebalance` | Back to target weights on the first trading day of each quarter |
| `global_etf` | 100% in the global equity ETF |
| `mechanical_5pct` | Rebalance to target whenever any 5% trigger fires, with **no agent reasoning**. Shows what reasoning adds |

## Two separate test sets (never mixed)

1. **Real market data replay** (our snapshot, 7 Jul → 6 Nov 2026, walk-forward): the main results below.
2. **Organisers' AgentVerse finance kit** (synthetic cases + hidden test mode, #60/#61): reported in its own table, labelled "organiser synthetic test data".

## Walk-forward integrity (judged control, #72)

**Deck line:** "Walk-forward verified: deleting or scrambling future data changes nothing before that date."

- `backend/tests/test_no_peeking.py` runs in every CI build. For 3 cut-off days t (early, middle and late in the window), it runs the simulator engine-only and with fake-LLM agents plus batch approvals on three snapshots: (a) the full data, (b) everything after t deleted (prices, FX, news, filings), and (c) every price and FX rate after t replaced by a random walk.
- Every event up to t must be identical: weights, NAV, orders, triggers, decisions, 2-week forecasts, proposals and approvals.
- **It has teeth.** The scrambled run must differ *after* t. A test that makes the gateway ignore `as_of` must make the comparison fail, and it does. Breaking the real gateway by hand (removing the `as_of` cut in `DataGateway.prices`) fails the test with "future data changed the past … first difference at event 3".
- **Known data caveat:** adjusted closes from a provider are back-adjusted for later dividends and splits. That's a property of the price series, not something our code reads ahead. We state it in the deck.

## Ablations (ours)

- `ours_no_agents`: same engine, no Gemini agents (the key comparison)
- `ours` without the forecast term (`lambda_return: 0`)
- `ours` with the 2-week forecast
- (feature) `ours` with forecast + agent views

## Window and runs

- **Simulation window:** 7 Jul → 6 Nov 2026 (~85 trading days). Gemini 4 Argon's reported knowledge cutoff is March 2026, so the **whole window is held-out**: the model can't have seen it. Parameters are sanity-checked only on pre-window data (2023 → Jul 2026) and frozen (tag `eval-freeze`) before the run.
- **Agent run** (`ours`, overnight): the showcase. Recorded in `runs/year.sqlite` (name kept for scripts).
- **Engine-only run** (`ours_no_agents`, same window, `--no-agents`, ~1 min): identical optimiser, forecast and triggers, but no Gemini. **`ours` vs `ours_no_agents` = what Gemini adds.**

## Metrics

Per strategy and period: total return (TWR), annualised vol, max drawdown, Sharpe (rf = 0), turnover, total costs £, trades.

**Ours only:**
- reviews, trigger runs, maintain vs adjust counts
- **decisions asked of the user**
- gate failures caught
- quarantined items
- refused spawns

## Headline lines for the deck

- "Over the year the system ran **X reviews and Y checks** and asked you to decide **Z times**."
- "Gemini agents vs the same engine without them, and vs buy-and-hold: return, drawdown, cost, decisions asked." Report it honestly, even if we lose.
- "Every decision traceable: N events, M evidence items, 100% of numbers recomputed by code."

## Caveats (on the slide)

- Four months is one short path, not statistically significant.
- Simulated backtest, not live performance.
- Batch approvals were simulated by policy.
- Synthetic items are labelled.
- Costs are assumptions.
- Current ETF holdings are used as a proxy for look-through.

## Implementation

Record the runs (same window, frozen config), then evaluate:

```bash
cd backend
python -m app.sim.runner --agents --approvals batch_policy --record runs/year.sqlite        # ours (overnight)
python -m app.sim.runner --no-agents --record runs/no_agents.sqlite                         # ours_no_agents (~1 min)
python -m app.sim.runner --no-agents --no-forecast --record runs/no_forecast.sqlite         # forecast ablation
python -m app.sim.evaluate --record runs/year.sqlite --record ours_no_agents=runs/no_agents.sqlite \
    --record ours_no_forecast=runs/no_forecast.sqlite --out eval/
```

- Each run stores its results (per-strategy NAV series, contributions, costs, trades, decisions) in its own SQLite (`kv` ns `sim_results`). The first `--record` is `ours` and supplies the 4 benchmarks.
- Writes `eval/metrics.json`, `eval/table.md` (ready to paste: the table, the "what the system did" line and the caveats) and `eval/nav.png` (`nav.svg` if matplotlib isn't installed: `pip install matplotlib`).
- `/api/benchmarks` serves the same numbers for the last finished replay (test: `test_numbers_match_api_benchmarks`).
- **Metric definitions:**
  - Return is time-weighted, with contributions stripped. Volatility and Sharpe are annualised from daily returns (rf = 0).
  - Max drawdown is measured on the TWR growth curve.
  - Turnover is one-way traded £ ÷ 2 ÷ average NAV, excluding the initial build from cash.
  - Every strategy starts from the same £ on day 0 and gets the same contributions and cost model.
- **The benchmarks invest every contribution:**
  - Buy-and-hold invests it in proportion to what it already holds; the others by their targets, buys only.
  - Each one's own rule is its only rebalance: quarterly at a new quarter, `mechanical_5pct` when a 5% trigger fires.
