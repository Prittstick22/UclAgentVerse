---
id: 20261108T020512Z-dev-to-all-38-retrospective-now-runs-after-every-agent-run-
from: dev
to: all
type: fyi
status: open
issue: 38
created: 2026-11-08T02:05Z
---
# #38 retrospective now runs after every agent run (not monthly)

Spec change (decision: Dev). Docs/05 and #38 are updated (PR #107).

- The retrospective runs **after every agent run**: each fortnightly review and each ad-hoc trigger run.
- It reviews decisions that have **matured since the last retrospective** (≥ 10 trading days old, one 2-week horizon, so outcomes are known), using data ≤ the sim date only. If nothing has matured, it stops after one step without proposing.
- Still ≤ 1 rule per run; rule_tester checks it on earlier episodes; promotion is code; effective from its creation date only (no hindsight).
- **@Cem:** when #38 is built, the sim calls it right after each review/trigger `supervisor.start(...)`, as a separate `retrospective` run. Nothing to change yet. #38 is still a **feature**, after the core path.

## Replies
