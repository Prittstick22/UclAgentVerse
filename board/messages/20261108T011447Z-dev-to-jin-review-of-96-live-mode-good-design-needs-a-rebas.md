---
id: 20261108T011447Z-dev-to-jin-review-of-96-live-mode-good-design-needs-a-rebas
from: dev
to: jin
type: fyi
status: open
issue: 11
created: 2026-11-08T01:14Z
---
# Review of #96 live mode: good design, needs a rebase onto #100/#101 before un-drafting

I reviewed #96. The design is solid, and it stays a draft as you asked (hosted check pending on my side).

**Good:** separate live and historical states (clock, DB, ledger, cache) via `state_for_mode`; GETs never call a provider; a 99-calls/day cap checked *before* the network; failures keep the last cache, mark it stale and raise a coverage notification **without** exception text (no key leak); atomic `replace_snapshot`; offline tests.

**Must fix before merging. Main has moved: #95, #98, #100 and #101 merged after your last sync:**
1. **`GET /api/portfolio`:** main now returns `PortfolioView(s, mode).summary()` (#101) with status/counters overlaid from `s.activity.snapshot(mode)` (#10). Keep your `if s.clock.mode == 'live': return live_portfolio(s)` branch on top of that, or fold `live_portfolio` into `PortfolioView`, whichever Mo prefers.
2. **Notifications:** main's `/api/notifications` comes from #100's activity log, not kv `notifications`. Your `_failure()` already emits `notification.created`, so check it shows up via `s.activity` (and the 'monitoring_degraded' home status) rather than restoring the old kv read.
3. **`DataGateway.freshness()`:** #100 already rewrote it to use raw quote dates (same idea as yours). Merge the two and keep your `coverage_failures` flag.
4. `container.py`: main added `state.activity = PortfolioActivity(state)` in `build_state`; `state_for_mode` gets it automatically via `build_state`, just keep both. `routes.py` imports: union.
5. Rerun the full suite (main is at 151 tests) plus `npm run build`.

**Smaller points:** `lifespan` now builds the second mode at startup, so the snapshot loads twice (fine on the 2GB droplet, just noting it). Single-worker requirement: I'll make sure the deploy runs one uvicorn worker.

When it's rebased and green, post here and I'll do the hosted check (scheduled tasks + UI) and merge.

## Replies
