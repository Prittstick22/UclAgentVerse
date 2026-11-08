---
id: 20261108T021148Z-cem-to-dev-24-covers-api-benchmarks-fixes-3-benchmark-bugs-
from: cem
to: dev
type: handoff
status: open
issue: 20
created: 2026-11-08T02:11Z
---
# #24 covers /api/benchmarks + fixes 3 benchmark bugs: please check #20 overlap

While building the evaluation (#24, branch cem/24-eval-script), I had to touch the benchmark code, which overlaps your **#20** ('Benchmarks in lockstep + /api/benchmarks'). You hadn't changed `sim/benchmarks.py` since the scaffold, so I fixed it rather than block on it. Please check this before you start #20, so we don't both do it.

**Fixed in `backend/app/sim/benchmarks.py`:**
1. Buy-and-hold and global_etf **never invested the monthly £200**. `_pro_rata_targets()` targeted the current weights, which already include the new cash, so it made no trades. The money sat as cash (VWRP made 1 trade in 4 months). Now every benchmark invests each contribution, buys only. Buy-and-hold invests in proportion to its holdings; the others by their targets.
2. `quarterly_rebalance` did a **full rebalance at every monthly contribution**, so it was really monthly. Now it rebalances only at a new quarter.
3. `mechanical_5pct` left contributions in cash until a trigger fired. Now it invests them by target.

**Also in the runner:** benchmarks now start from the same cash we paid in (`led.contributions_gbp`), not our NAV after our own trading costs. Every strategy's series starts at £10,000 on day 0.

**`GET /api/benchmarks` is implemented**, using the contract shape `{series, metrics, periods}` for the last finished replay in that mode's DB. It's the same function the eval uses: `app.sim.evaluate.benchmarks_payload`.

Your #20 may now be just the frontend, or nothing at all. Please reply or close it.

**For the overnight run (#37):** after `python -m app.sim.runner --agents --approvals batch_policy --record runs/year.sqlite`, also run `--no-agents --record runs/no_agents.sqlite` and `--no-agents --no-forecast --record runs/no_forecast.sqlite`. Then run `python -m app.sim.evaluate --record runs/year.sqlite --record ours_no_agents=runs/no_agents.sqlite --record ours_no_forecast=runs/no_forecast.sqlite --out eval/`. That writes `eval/table.md` and `eval/nav.png` for the deck (`pip install matplotlib` for the png; otherwise it writes nav.svg).

## Replies
