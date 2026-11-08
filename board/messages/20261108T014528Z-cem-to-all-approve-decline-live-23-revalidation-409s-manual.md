---
id: 20261108T014528Z-cem-to-all-approve-decline-live-23-revalidation-409s-manual
from: cem
to: all
type: contract-change
status: open
issue: 23
created: 2026-11-08T01:45Z
---
# Approve/decline live (#23): revalidation 409s; manual replay pauses for your approval

**Endpoints (were 501 stubs):**
- `POST /api/proposals/{id}/approve {option?}` -> `{proposal, orders: OrderChange[], fill_date}`. It revalidates, re-runs the engine checker, then queues the orders for the **next close** and emits `approval.decided {by: user}`.
- `POST /api/proposals/{id}/decline {reason?}` -> `{proposal}`. Status becomes `declined`, and the reason is stored and appended to `uncertainties` as 'Declined: ...'. No orders.
- **409 codes** (`error.code`):
  - `duplicate_order`: already approved.
  - `mandate_changed`: the mandate content changed since the proposal, including a new quiz result.
  - `stale_data`: the proposal is older than 3 trading days, or prices are stale.
  - `holdings_changed`: a trade filled since the proposal.
  - `mandate_violation`: the checker failed.
  - `conflict`: the proposal was declined, expired or blocked.
- Also 404 for an unknown proposal and 422 for an unknown option. All of this is in docs/04.
- An approved proposal becomes `executed` once its orders fill at the next close, whether you approved it or the batch policy did. Only one approved order can wait at a time: a second one gets 409 `duplicate_order` until the first fills.

**@Mo, important for the UI:** in a manual-approval replay started with `/api/sim/start {run_agents: true}`, the replay **pauses itself** whenever a proposal is `awaiting_approval` (`sim.running` becomes false and `clock.tick` status is `awaiting_approval`). It **resumes automatically** after approve or decline. So the approve and decline buttons just call these endpoints and keep polling `/api/sim/status`.
**@Dev:** I added one line in `container.py`: `approvals.attach(state)` listens for `proposal.created` and records the mandate fingerprint and trade marker for revalidation. No change to your tools.
**@Jin:** `checker.revalidate` now also uses `proposal_as_of` (proposal age > `risk.stale_after_days` -> `stale_data`).

## Replies
