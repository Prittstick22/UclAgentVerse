---
id: 20261108T033550Z-jin-to-all-recorded-demo-playback-and-no-provider-request-c
from: jin
to: all
type: contract-change
status: open
issue: 78
created: 2026-11-08T03:35Z
---
# Recorded demo playback and no-provider request checks

Working on jin/78-no-api-waits from latest main. Adding optional RECORDED_RUN path: load a read-only SQLite recording into an isolated in-memory historical view at startup, restore saved proposals and replay recorded events/checkpoints using existing sim controls, never rerun agents/optimiser or overwrite source. Existing endpoint/event shapes remain unchanged; replay controls become playback-only when configured. Date-filter recorded runs/events/proposals; reject historical trading mutations against recordings. Live mode remains cached/background-refresh plus async builds. Small subscriber terminal handling in frontend/src/lib/sse.ts. Shared docs/04 and hosting docs updated, no frozen config/fixtures/deploy edits. Dev: hosted no-key and page-load checks require deploying this branch with the finished recorded artifact; current hosted dry-run has synthetic data and no funded recording. All automated tests/build will pass before PR.

## Replies
