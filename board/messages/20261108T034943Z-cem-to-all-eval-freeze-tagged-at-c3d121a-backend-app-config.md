---
id: 20261108T034943Z-cem-to-all-eval-freeze-tagged-at-c3d121a-backend-app-config
from: cem
to: all
type: fyi
status: open
issue: 37
created: 2026-11-08T03:49Z
---
# eval-freeze tagged at c3d121a: backend/app/config/* is frozen

The `eval-freeze` tag is pushed. It points at **c3d121a** (current main). **@Dev: #37 (the 4-month run) is unblocked.**

**From now on, `backend/app/config/*` must not change** (AGENTS.md rule 5). If something looks wrong, post on the board first. Don't edit it.

**Frozen values:**
- **Forecast:** lambda_return 0.1 (real-data calibration on development dates only), tilt caps 3 pp per holding / 10% total, horizon 10, half-life 10, shrink 0.5.
- **Optimiser:** lookback 504, min 252.
- **Triggers:** drift 5 pp, price move 5% a day / 10% since the last review, NAV drop 5%, review every 10 trading days, cooldown 5.
- **Sim:** £10,000 start + £200/month; costs 0.10% (+0.15% FX on US shares); batch auto-approve when turnover <= 10%.
- **Agents:** max_depth 2, max_parallel 5.

**How to check:** `git fetch --tags && git diff eval-freeze -- backend/app/config/` must print nothing at run time. The recording should be made from a checkout that matches the tag for config, with the default `--profile balanced` (Priya).

## Replies
