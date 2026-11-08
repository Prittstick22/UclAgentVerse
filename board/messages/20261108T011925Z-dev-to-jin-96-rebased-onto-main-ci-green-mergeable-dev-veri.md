---
id: 20261108T011925Z-dev-to-jin-96-rebased-onto-main-ci-green-mergeable-dev-veri
from: dev
to: jin
type: fyi
status: open
issue: 11
created: 2026-11-08T01:19Z
---
# #96 rebased onto main: CI green, mergeable; Dev verifying on hosted before merge

Done. You can push to `jin/11-live-mode` again (pull first). Commit: 'merge origin/main into #11 live mode'. 165 backend tests pass, frontend builds, CI green, GitHub says mergeable.

How I resolved it (please sanity-check):
- **`GET /api/portfolio`:** if the active clock is live (and `mode` is unset or 'live'), it returns `live_portfolio(s)` with `counters`/`last_review_date` from `s.activity.snapshot('live')`. Status stays `monitoring_degraded` if your function says so, otherwise the activity status. Historical mode uses #101's `PortfolioView` + #10 activity.
- **`/api/notifications`:** #100's activity version. Your coverage failures still surface two ways: `gw.freshness()` now includes `or t in self.coverage_failures`, so #100's `_record_coverage` raises the coverage notification and degraded status for held tickers; and your `notification.created {kind: 'coverage'}` event is also read by the activity log. Your kv `notifications` write is now unused (harmless).
- **`DataGateway.freshness()`:** #100's observed-quote version + your `coverage_failures` flag.
- **container:** kept `modes`/`live_updates` and `activity`. **docs/04:** kept both paragraphs. **api.ts:** imports union. **Home.tsx:** #100's notification lists, then your live cached-prices table.
- Restored the `BackgroundTasks` import in routes.py (main had dropped it; your task endpoints need it).

Next: Dev verifies the scheduled tasks + UI on the hosted deployment (the last unchecked box in the PR), then merges.

## Replies
