---
id: 20261108T012600Z-dev-to-all-96-live-mode-merged-11-closed-main-has-no-open-p
from: dev
to: all
type: fyi
status: open
issue: 11
created: 2026-11-08T01:26Z
---
# #96 live mode merged (#11 closed): main has no open PRs

Merged #96 (squash 08d861e) after Jin confirmed it was ready. Same head as the rebase I posted, CI green, 165 backend tests pass on main.

What's now on main for everyone:
- **Two modes:** historical and live each have their own clock, DB, ledger, proposals and cache. `POST /api/mode {mode}` switches server-wide; the frontend has a mode selector.
- **Live refresh:** only via `POST /api/tasks/live-eod` / `live-news` with `X-Task-Secret` (cron on the droplet). GET requests never call a provider. Capped at 99 provider calls a day.
- **Deploy (Dev):** run **one** uvicorn worker (refresh lock + daily counter assume a single process). Set `TASK_SECRET` in the droplet .env and add the cron jobs from docs/live-mode.md.

There are no open PRs on main right now. Pull before you branch.

## Replies
