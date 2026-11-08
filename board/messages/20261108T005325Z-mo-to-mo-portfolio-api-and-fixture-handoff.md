---
id: 20261108T005325Z-mo-to-mo-portfolio-api-and-fixture-handoff
from: mo
to: mo
type: handoff
status: open
issue: 21
created: 2026-11-08T00:53Z
---
# Portfolio API and fixture handoff

Home can use GET /api/portfolio. History accepts mode, start and end, and P&L accepts a documented period. Rebalances uses approval and fill events, with the run ID for replay links.

Daily ledger checkpoints use the ledger_checkpoints:<mode> KV namespace and app.engine.portfolio.record_checkpoint. The current simulator records one at each close. For #18, reuse the checkpoint hook when wiring ledger snapshots. For #23, emit approval.decided and order.filled with the same run_id, or include proposal_id on fills so they can join the approval. Older clock.tick data still provides history with null contributions if unknown. Detail and P&L return 409 when a recording has no usable ledger basis.

The typed DTOs and four generated portfolio fixtures match docs/04. No event payload change is required.

## Replies
