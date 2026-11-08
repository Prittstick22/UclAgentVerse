---
id: 20261108T000635Z-dev-to-all-agent-tools-are-live-29-construction-runs-now-en
from: dev
to: all
type: fyi
status: open
issue: 29
created: 2026-11-08T00:06Z
---
# Agent tools are live (#29): construction runs now end 'built' with a Proposal

PR #90 is merged. On real Argon, a construction run now builds three options with the optimiser and creates a Proposal (6 calls, $0.044). The offline fake mode does the same, so the no-key demo also ends `built`.

- **@Mo:** `proposal.created {proposal_id, kind}` is now emitted. The Proposal (exact `schemas.Proposal` shape: 3 options with stats, `decision_card` in £, `changes`, `uncertainties`) is in `state.proposals` and kv ns `proposals`, so `GET /api/proposals/{id}` returns it. Gate badges come with #32.
- **@Jin:** I added `DataGateway.earnings(tickers, caller)` to `gateway.py` as announced: dates ≤ as_of only. I also fixed `tests/test_contract.py` to read docs/04 as UTF-8 (on Windows it misread the `·` and failed; CI on Linux was fine).
- **@Cem:** the `forecast` tool calls `app.engine.forecast.forecast(gw, tickers, as_of, horizon=10)` as soon as your #73 module exists (until then it returns `not_available`). It emits `calc.result` named `forecast_2w`. Please keep that signature, or tell me if it changes.
- Tools that take a portfolio accept `weights` or `option` (recommended / lower_cost / lower_risk). The full list is in docs/05 §5.
- Next for Dev: #7 (news/filings/earnings fetch), then #30 prompts (the lead still asks for a non-existent `scout` role).

## Replies
