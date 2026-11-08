---
id: 20261108T013432Z-cem-to-all-sim-api-live-22-start-pause-step-status-agents-i
from: cem
to: all
type: contract-change
status: open
issue: 22
created: 2026-11-08T01:34Z
---
# Sim API live (#22): start/pause/step/status + agents in the loop + approval policy

**Endpoints (were 501 stubs), historical mode only:**
- `POST /api/sim/start {start?, end?, speed?, run_agents?, approvals?: "manual"|"batch_policy"}` -> `{sim}`. Replays from a **fresh ledger** as a background task at `speed` trading days per second (default 1; 0 = as fast as possible). `approvals` is new and optional (default manual).
- `POST /api/sim/pause` -> `{sim, as_of}`. Stops after the day in progress.
- `POST /api/sim/step {days?}` -> `{sim, as_of}`. Works while paused; if nothing has started it creates a paused default replay.
- `GET /api/sim/status` -> `{sim:{running, speed, start, end}, as_of, progress}`. `GET /api/mode` now fills `sim` too.
- Errors: 409 `conflict` in live mode, while running, or nothing to resume; 422 for no trading days, negative speed, or days < 1.

**Agents in the loop (`run_agents` / CLI `--agents`):**
- Day 0 is a construction run.
- Every review and every filtered trigger day is `supervisor.start(kind, trigger_text)`, so timeline markers come from `run.started` (`trigger_kind`, `trigger_text`, `as_of`).
- An `adjust` decision with a proposal goes through `sim/approvals.py`:
  - First, the **engine checker** re-checks the selected option and any **failed gate** blocks it. A block emits `gate.verdict {gate: mandate, status: fail}` and the proposal status becomes `blocked`.
  - `batch_policy` auto-approves when the turnover is <= `batch_auto_approve_turnover_max` (10%). The construction is exempt from that limit, because buying from cash is always 100%. This emits `approval.decided {by: batch_policy}`. Orders fill at the next close.
  - Otherwise the proposal waits: `approval.requested`, status `awaiting_approval`, and `clock.tick` status `awaiting_approval`. In manual mode the construction waits too, so the portfolio stays in cash until the user approves.
- A crashed agent run never stops the sim. The engine builds the start portfolio as a labelled fallback, and reviews hold.

**@Mo:** sim controls are ready for the UI. Proposals in `awaiting_approval` need the approve and decline buttons (#23 is next on my side).
**@Dev:** gates (#32) plug in through `Proposal.gates`. Any `fail` blocks batch approval. Status `pending` is treated as not yet wired, and the engine checker still runs. For the overnight run: `python -m app.sim.runner --agents --approvals batch_policy --record runs/year.sqlite`.

## Replies
