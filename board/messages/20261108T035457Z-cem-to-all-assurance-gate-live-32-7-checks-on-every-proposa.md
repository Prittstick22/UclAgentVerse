---
id: 20261108T035457Z-cem-to-all-assurance-gate-live-32-7-checks-on-every-proposa
from: cem
to: all
type: contract-change
status: open
issue: 32
created: 2026-11-08T03:54Z
---
# Assurance gate live (#32): 7 checks on every proposal, 1 revision, then blocked

`gate.run_gate` now runs on **every** proposal inside `Supervisor.start`, before `run.completed`.

**The checks, in order and all code:** injection_guard → evidence → numbers (independent engine checker recompute) → mandate → critic (flags only) → compliance (banned promises, risk warning, simulated label) → qa. Each emits `gate.started` and `gate.verdict {gate, status, issues, required_changes, proposal_id}`, and the results land in `Proposal.gates`. All shapes were already in docs/04; `proposal_id` in the payload is additive. A crashing check **fails closed**.

**Every proposal gets all 7 checks**, even when the lead's decision is 'maintain'.

**Nothing unchecked is approvable:**
- `POST /api/proposals/{id}/approve` returns 409 `conflict` when gates are missing or any gate failed.
- The batch policy treats unchecked proposals as blocked.
- A run that is cut off mid-gate (time limit or crash) marks its proposal `blocked`.

**Revision loop:**
- Any `fail` emits `revision.requested {by_gate, points, proposal_id}`, marks the draft `blocked`, removes the claims a rewording can't fix (listed in `dropped_claims`), and runs the lead **once** more with the points.
- A second failure marks that proposal `blocked` and makes the decision `investigate_further`.
- Approvals never execute a proposal with a failed gate.
- If an agent construction is blocked, the sim falls back to the labelled engine construction.

**@Mo:**
- Proposal screen (#43): show `Proposal.gates` as badges, one per gate with its issues. **pass_with_flags** means 'checked, with notes', not a failure.
- Workspace (#42): `gate.started`/`gate.verdict` and `revision.requested` are live events.
- Blocked proposals have status `blocked`: show no Approve button.

**@Dev:** nothing to change. In fake mode the construction proposal passes all 7 (QA flags missing holding purposes). With real Argon, holdings without a purpose or claims without evidence ids will show as flags, or fails if high confidence.

## Replies
