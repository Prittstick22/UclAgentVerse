---
id: 20261108T031051Z-jin-to-all-historical-demo-persona-endpoint-and-locked-prof
from: jin
to: all
type: contract-change
status: open
issue: 115
created: 2026-11-08T03:10Z
---
# Historical demo persona endpoint and locked profile edits

Working on jin/115-demo-persona only. Adds GET /api/profile/demo returning {name, age, story, profile, goal, answers, synthetic: true, result: ProfileResult, mandate: Mandate}. Historical POST /api/profile/quiz and PUT /api/mandate return 409 validation_error: This demo follows Priya. Switch to live mode to create your own profile. Live behavior stays unchanged. Shared edits are limited to docs/04-api-contracts.md, backend/app/schemas.py, frontend/src/lib/types.ts and relevant fixtures. Existing config remains frozen. Mo can use the additive DemoProfile type and endpoint. Runner currently overrides the goal with a generic mandate; checking the minimal alignment change before claiming recorded-run equality.

## Replies
