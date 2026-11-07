---
id: 20261107T221853Z-dev-to-all-walk-forward-2-week-forecast-no-peeking-test-61-
from: dev
to: all
type: contract-change
status: open
issue: 
created: 2026-11-07T22:18Z
---
# Walk-forward 2-week forecast + no-peeking test; #61 moved to Dev

Design change (docs/07 §2a, docs/01 §6, docs/10 updated; params.yaml gains a `forecast:` block):
- Every simulated day/week sees ONLY data up to that day. Cem's #72 adds `test_no_peeking`: delete/scramble all data after day t → nothing before t may change. Judged control.
- At each review the engine estimates the next 2 weeks (10 trading days) from past data only (EWMA mean shrunk to 0, EWMA vol, p10/p50/p90 from the Ledoit-Wolf covariance), and the optimiser uses it (−λ_return·μᵀw). Numbers from code, labelled 'estimate', never from the LLM. Cem #73 (MVP).
- Dev #74 (feature): agents give views (direction/confidence/evidence) → code turns them into capped tilts.
- Eval: real-data replay and the organisers' synthetic finance kit are reported SEPARATELY; ablation with/without forecast.
- #61 (finance kit adapter) is now Dev's: kit = organiser synthetic test data; our demo = real market data.

## Replies
