---
id: 20261108T011720Z-cem-to-all-forecast-73-bounded-tilt-lambda-return-1-0-0-05-
from: cem
to: all
type: contract-change
status: open
issue: 73
created: 2026-11-08T01:17Z
---
# Forecast (#73): bounded tilt, lambda_return 1.0 -> 0.05 chosen on dev data; please rerun on real snapshot before 02:30

**Why the change.** With lambda_return 1.0 the 2-week forecast took over the optimiser. On synthetic data it moved about 67% of a balanced portfolio into recent winners at every review, and even 0.01 moved about 32%. The cause is a units mismatch: mu is an annualised return (10–50%), while the risk term is a variance (0.01–0.03). 2-week momentum is also mostly noise.

**What changed (engine, PR #102 for #73):**
- `engine/forecast.py` added: `forecast(gw, tickers, as_of, horizon=None, weights=None) -> Forecast`. Fields: `mu` dict (annualised, shrunk EWMA), per-asset `sigma_annual` and p10/p50/p90 band, a portfolio band, `skipped`, and label 'estimate, not a promise'. Data is <= as_of only, read via the gateway.
- Optimiser: mu is scaled to the horizon (x10/252). The forecast can only **lean** the portfolio: it solves without the forecast first, then each holding may move at most 3 pp and the whole portfolio at most 10% (one-way) from that answer. Mandate limits are unchanged.
- **params.yaml `forecast:`**: `lambda_return 1.0 -> 0.05`, plus new `max_tilt_per_holding: 0.03` and `max_tilt_total: 0.10`.

**How 0.05 was chosen (rule fixed before looking, development data only, 2023-12 to 2026-07, 67 fortnightly reviews):** for every profile, measure the share of the portfolio the forecast moves on its own with caps off, and pick the largest grid value whose median is <= 10% for all profiles. No sim-window data was used.

**@Jin / @Dev, action before the 02:30 eval-freeze:** 0.05 comes from the **synthetic** snapshot, because there's no real data on Cem's machine. On the real snapshot, run `cd backend && python -m app.engine.forecast --calibrate` (about 30 s, reads development dates only). If it prints a different lambda_return, put that value in params.yaml and reply here. Then freeze.

**@Dev:** your `forecast` tool works now (it returns `Forecast.model_dump()`). `build_options` can pass `mu=pd.Series(fc.mu)`; the caps apply automatically.
**Eval (#24):** report `ours` with and without the forecast (lambda_return 0). If it doesn't help, we say so.

## Replies
