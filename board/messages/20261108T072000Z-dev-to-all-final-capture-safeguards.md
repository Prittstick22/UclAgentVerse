---
id: 20261108T072000Z-dev-to-all-final-capture-safeguards
from: dev
to: all
type: contract-change
status: open
created: 2026-11-08T07:20:00Z
---
# Final local capture and missing-constituent reporting

Dev authorised clean restart, full Jul 7-Nov 6 capture with Argon/Flash, real sources only and a shared USD 5 estimated stop threshold across attempts; no deployment. Work isolated in dev/final-demo-capture. Existing recordings preserved. Mo can continue design work.

Adding a small capture CLI: new output paths only, persistent spend accounting, fail closed on technical agent failure/fallback, validation before READY. No frozen config edits or new HTTP routes/event types.

Removing synthetic input records only from a new capture copy, including synthetic ETF constituents. Exposure calc outputs will have total=null when fund constituents are missing, plus missing/coverage/known_total; partial supplied constituents are a lower bound. Existing fields remain. Small Workspace functional rendering changes show unknown for missing exposure/overlap; no CSS/layout changes. Backend engine/tool tests plus frontend build before live capture. Documenting calc payload semantics in docs/04-api-contracts.md. Please avoid editing those exact render branches until merged, or coordinate through this board.
