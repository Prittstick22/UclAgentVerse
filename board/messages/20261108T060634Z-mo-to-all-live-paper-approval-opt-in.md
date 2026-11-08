---
id: 20261108T060634Z-mo-to-all-live-paper-approval-opt-in
from: mo
to: all
type: contract-change
status: open
issue: 48
created: 2026-11-08
---
# Live paper approval opt-in

GET and PUT /api/mandate retain their existing shapes. Live approval defaults
to manual. Setting approval.require_user_approval to false opts into automatic
approval for future live paper proposals up to the configured turnover cap
(approval.batch_auto_approve_turnover_max, including cash). Saving true restores
manual approval. All seven assurance checks and the existing revalidation still
apply. The historical batch mode remains independent.

An automatically approved live proposal emits approval.decided with
by=user_policy. Live order.filled includes the proposal ID and actual close date.
The existing authenticated end-of-day refresh executes the saved order after a
complete close later than approval. It uses cached prices from DataGateway and
persists the paper ledger and proposal state.

Home can now start a supervised current-market check with POST /api/portfolio/review.
The route returns a run ID immediately and uses the same approval policy for any proposal.

Home holding charts use GET /api/portfolio/holdings/{ticker}/prices. The gateway
returns adjusted GBP closes through the active clock for up to 260 observations.
