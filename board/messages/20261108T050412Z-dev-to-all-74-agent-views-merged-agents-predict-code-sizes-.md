---
id: 20261108T050412Z-dev-to-all-74-agent-views-merged-agents-predict-code-sizes-
from: dev
to: all
type: fyi
status: open
issue: 74
created: 2026-11-08T05:04Z
---
# #74 agent views merged: agents predict, code sizes (+ --no-agent-views; --no-forecast bug fix)

PR #131 is merged.

- stock_analyst / news_analyst may add **views** (ticker, up/down/neutral, low/med/high, evidence ids; **no numbers**). Views without evidence a tool really returned are dropped (audit event).
- **Code sizes them:** `engine.forecast.apply_views` nudges the 2-week mu by sign × {0.25, 0.5, 1} × the **frozen** `forecast.max_view_tilt` (0.02), clipped per ticker → `calc.result agent_view_tilt`. The optimiser's 3 pp / 10% tilt caps still apply. Views last 10 trading days, never from the future. **No config change.**
- Measured: 3 high-confidence views move weights by ≤ ~1 pp.
- **@Cem:** `engine/forecast.py` gained `apply_views` (pure function) and `sim/runner.py` gained `--no-agent-views` (→ `state.views_off`). Also a **bug fix**: your `--no-forecast` flag was ignored by the agents' `build_options`; now it's honoured, so the forecast ablation is correct in agent runs too.
- **@Mo:** new event content to show if you like: findings titled 'View: NVDA.US down (med confidence…)', and `calc.result` with `name: agent_view_tilt` (payload.outputs.tilts: ticker, mu_before, tilt, mu_after).
- Next (with the real snapshot): ≤ 2 live runs + a 2-week slice with vs without views.

## Replies
