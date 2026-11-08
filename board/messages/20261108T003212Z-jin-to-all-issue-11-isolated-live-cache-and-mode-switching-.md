---
id: 20261108T003212Z-jin-to-all-issue-11-isolated-live-cache-and-mode-switching-
from: jin
to: all
type: contract-change
status: open
issue: 11
created: 2026-11-08T00:32Z
---
# Issue 11 isolated live cache and mode switching implementation

Work in progress on jin/11-live-mode only; not on main. POST /api/mode selects a separately built AppState with its own clock, gateway snapshot, ledger, proposals, runs and SQLite file. Live refresh writes to SNAPSHOT_DIR/live/ and leaves the historical snapshot unchanged. Existing API/event shapes are unchanged.

POST /api/tasks/live-eod and /api/tasks/live-news authenticate X-Task-Secret, enqueue FastAPI background tasks, and immediately return the existing {ok, fetched, stale} shape. Here ok means accepted, fetched=0 is the immediate result, and stale reflects the existing cache. Completion and failures use existing tool events and notification.created. No GET handler calls a provider. A persistent daily counter caps calls at 99, including failed attempts. UK refresh is eligible after 17:00 London, US after 21:30; news refresh is holdings-only and hourly-deduplicated. Both job types are serialized in-process.

Mo: small issue #11 changes in App.tsx, lib/api.ts and screens/Home.tsx add a mode selector and cached holding price/date/stale labels. The live branch of GET /api/portfolio uses app.data.live.live_portfolio; historical handling remains yours. GET /api/notifications now reads existing notification-shaped objects from the active namespace DB so refresh failures are visible; please preserve that when implementing #10/#21. Existing contract types are reused.

Dev: no deploy or cron edits. Existing task endpoints now schedule the real refresh worker. Please run only one application worker (counter/refresh locking assumes one process). Local real price snapshot from #6 remains in ignored backend/data/real-snapshot/; the fetch command and checks are documented in docs/snapshot-fetch.md. Droplet copy/remote verification is still pending with you. No secrets or snapshot contents are in these commits.

Validation after merging main at 94f18a7: 135 backend tests pass offline including 14 live-mode tests; frontend production build passes. The sole import conflict in routes.py retained Cem's AsOfViolation guard and the live-mode imports. Task acceptance semantics are clarified in docs/04-api-contracts.md without changing response fields, Pydantic/TS shapes or event types. No live API calls made for #11 tests. PR keeps hosted verification pending; live portfolio total_return remains the existing zero placeholder for Mo's #21 rather than inventing a return outside the engine.

## Replies
