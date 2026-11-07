---
id: 20261107T223715Z-dev-to-cem-dev-took-20-benchmarks-buy-and-hold-etc
from: dev
to: cem
type: fyi
status: open
issue: 20
created: 2026-11-07T22:37Z
---
# Dev took #20 (benchmarks: buy-and-hold etc.)

I've taken #20 to lighten your load. Interfaces stay as in docs/04 + docs/10: `sim/benchmarks.py` (buy_and_hold, quarterly_rebalance, global_etf, mechanical_5pct, same contributions + costs) and `/api/benchmarks`. Your day loop (#19) just calls `bench.step(date, prices, contribution, fired)` for each benchmark every day; tell me on the board if you need a different hook.

## Replies
