---
id: 20261108T000007Z-dev-to-mo-3-backend-issues-for-you-9-10-21-contract-guard
from: dev
to: mo
type: handoff
status: open
issue: 
created: 2026-11-08T00:00Z
---
# 3 backend issues for you: #9, #10, #21 + contract guard

You now own three backend endpoints that feed your own screens, so you can build API + UI together:
- #9 Runs API (agent tree + evidence) → workspace (#42), replay (#50)
- #10 Notifications + home status → home (#44), decision cards (#48)
- #21 Portfolio API (/portfolio, /history, /pnl, /rebalances) → home, timeline, rebalances (#44, #46, #49). Use Cem's ledger functions, never compute numbers in the route.

Contract: every endpoint is defined in docs/04-api-contracts.md and CI now enforces it (backend/tests/test_contract.py). If a shape must change: docs/04 + backend/app/schemas.py + frontend/src/lib/types.ts + `make fixtures` in one PR + a board contract-change post. PR template has the checkbox.

Order suggestion: keep building screens on mock mode; pick #21 first (biggest UI payoff), then #9, then #10.

## Replies
