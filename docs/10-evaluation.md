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

1. **Real market data replay** (our snapshot, Nov 2025 → Nov 2026, walk-forward): the main results below.
2. **Organisers' AgentVerse finance kit** (synthetic cases + hidden test mode, #60/#61): reported in its own table, labelled "organiser synthetic test data".

## Ablations (ours)

- `ours` without the forecast term (`lambda_return: 0`)
- `ours` with the 2-week forecast
- (feature) `ours` with forecast + agent views

## Periods

- **Development:** 2025-11-07 → 2026-03-31. Gemini 4 Argon's reported knowledge cutoff is March 2026, so the model may "know" this period.
- **Held-out:** 2026-04-01 → latest date. This is after the model's cutoff: our honest unseen-data claim.
- **Report the two separately.** Config is frozen (tag `eval-freeze`) before either is run. Disclose any reruns.

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
- "On the held-out period, ours vs buy-and-hold: return, drawdown and cost." Report it honestly, even if we lose.
- "Every decision traceable: N events, M evidence items, 100% of numbers recomputed by code."

## Caveats (on the slide)

- One year is one path, not statistically significant.
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
