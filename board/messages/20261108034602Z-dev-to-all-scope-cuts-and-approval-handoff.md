---
id: 20261108034602Z-dev-to-all-scope-cuts-and-approval-handoff
from: dev
to: all
type: handoff
status: open
issue: 32
created: 2026-11-08
---
# Dev scope cuts, Cem handoff and portfolio approval requirement

Direct decisions from Dev on 8 November 2026:

- Closed as not planned: #65 FCA-grounded compliance, #63 Companies House, #64 macro data, #36 monitor designer/tester, #35 chat.
- #80 closed: Alpaca is not used; retain EODHD/Finnhub. This is a scope decision, not a claim that every old cleanup acceptance criterion is complete.
- Keep the existing fixed triggers in backend/app/monitors/rules.py and the simulator. Agent-designed monitoring is out of scope.
- Cem (@cempnrbs) owns #32 assurance gate and #34 decision cards, including their backend/app/agents/ changes. Issue body owners and assignees now match. Basic compliance checks remain in #32; FCA rule sourcing (#65) is excluded.
- @Mo / @Cem: Dev requires Approve and Decline / Keep current portfolio before manual rebalance execution, plus explicit optional auto-approval. #43 and #48 now contain the acceptance criteria. Decline must call the existing endpoint, not merely dismiss the card.
- Current code: backend/app/sim/approvals.py implements approve_by_user and decline_by_user; manual mode emits approval.requested; batch_policy auto-approves eligible simulation proposals. approval.require_user_approval currently has no execution consumer. The checked frontend proposal/decision routes are placeholders, with no user auto-approval setting.
- Do not count batch_policy as a finished user-facing auto-approval feature. Default manual; persist explicit opt-in and enforce its limits before advertising the control. All required assurance checks apply in either mode. No response is not approval.
- Scope decisions take priority over older planning docs that still list the cancelled features. Do not restart those integrations.

Verification: focused offline tests/test_approve_decline.py and tests/test_sim_agents.py passed, 27 tests. These establish backend behavior, not completed frontend integration.

## Replies
