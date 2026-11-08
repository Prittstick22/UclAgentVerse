---
id: 20261108T001304Z-dev-to-all-finance-kit-reviewed-60-how-unseen-data-testing-
from: dev
to: all
type: fyi
status: open
issue: 61
created: 2026-11-08T00:13Z
---
# Finance kit reviewed (#60): how unseen-data testing will likely be judged

Full write-up: docs/finance-kit.md (merged, PR #91).

- The organisers' kit (`bench.py`) has a hidden **challenge** mode: sealed seed, cases in memory only, provenance scan. It's very likely how 'testing on unseen data' gets judged. Organisers run it against **our adapter command**.
- The packs that fit us: **`markets`** and **`real-markets`** (task `market_step`: price history so far → buy/hold/sell; scored vs buy-and-hold). `cashflow`/`transactions` aren't our product; we'll answer `unsupported_task` and say so.
- Dev builds the adapter in #61 (`backend/app/eval/finance_kit_adapter.py`): a deterministic rule on `app.engine.risk`, with no LLM per step and **no kit imports**. **@Cem:** it moved out of `app/sim/`, so nothing to do in your folder.
- The kit lives **outside** the repo at `../agentverse/`. `agentverse/` is gitignored; please don't commit it.
- From the organisers' builder guide: a demo under 3 min, opening on working software within 30 s, with a screen-recording backup. The README must name the user, the **exact model IDs** and the verification loop. Argon ignores `temperature`; use `thinking_level`.

## Replies
