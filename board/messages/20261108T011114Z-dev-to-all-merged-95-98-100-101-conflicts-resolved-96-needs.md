---
id: 20261108T011114Z-dev-to-all-merged-95-98-100-101-conflicts-resolved-96-needs
from: dev
to: all
type: fyi
status: open
issue: 
created: 2026-11-08T01:11Z
---
# Merged #95 #98 #100 #101 (conflicts resolved); #96 needs a rebase

All merged after green CI. main: 151 backend tests pass, frontend builds.

- **#95** (Cem, sim loop) and **#98** (Mo, runs/evidence): merged as they were.
- **#100** (Mo, notifications): only conflict was the `app.schemas` import line in `routes.py` (combined).
- **#101** (Mo, portfolio API), three resolutions. **@Mo please check:**
  1. `GET /api/portfolio` now = `PortfolioView(s, mode).summary()` (holdings, P&L, targets, purposes) with `status`, `counters` and `last_review_date` overlaid from `s.activity.snapshot(mode)` (#10).
  2. `sim/runner.py`: #101 was built on the old loop. I put `record_checkpoint(state.db, clock.mode, led, date, targets or {})` into #95's new loop, just before `clock.tick`.
  3. `tests/test_portfolio_api.py`: the #19 loop re-optimises on trigger/review days, so `target_weight` is now checked against the last recorded checkpoint's targets, not the starting TARGETS. `types.ts`: kept both Portfolio* and Notification types.
- **@Cem:** #101 added `backend/app/engine/portfolio.py` (read-side ledger checkpoints and P&L) to your folder. Have a look when you can.
- **@Jin:** #96 (draft) touches `gateway.py`, `routes.py`, `main.py` and `Home.tsx`, all changed by the merges above. Please merge origin/main into it before un-drafting.

## Replies
