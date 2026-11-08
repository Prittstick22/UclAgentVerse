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

`python -m app.sim.evaluate --record runs/year.sqlite --out eval/`:
- writes `eval/metrics.json` + `eval/table.md`
- writes `eval/nav.png` for the deck
- `/api/benchmarks` serves the same numbers
