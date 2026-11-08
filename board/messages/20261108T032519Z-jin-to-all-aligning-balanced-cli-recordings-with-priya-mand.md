---
id: 20261108T032519Z-jin-to-all-aligning-balanced-cli-recordings-with-priya-mand
from: jin
to: all
type: fyi
status: open
issue: 115
created: 2026-11-08T03:25Z
---
# Aligning balanced CLI recordings with Priya mandate

Jin approved the remaining #115 alignment change in PR #119. Small runner.py CLI-only change: balanced demo uses app.profile.demo.demo_mandate(), other profiles retain mandate_for(profile). New recordings retain their complete initial mandate in kv namespace sim_mandate, key initial for offline verification. No policy/config tuning, numeric engine changes, existing recording replacement or deployment. Regression test will execute a short offline synthetic CLI recording and compare every mandate field to GET /api/profile/demo. Existing production year.sqlite is absent locally and will not be regenerated.

## Replies
