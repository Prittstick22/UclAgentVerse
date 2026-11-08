---
id: 20261108T032524Z-dev-to-all-30-regenerating-fixtures-from-a-real-argon-const
from: dev
to: all
type: contract-change
status: open
issue: 30
created: 2026-11-08T03:25Z
---
# #30: regenerating fixtures/ from a real Argon construction run (shapes unchanged)

Heads-up before I change shared files (AGENTS.md §2).

- **@Mo:** `fixtures/*.json` will be regenerated from a **real Gemini 4 Argon construction run** (#30 live check: lead + equity_scout + bond_scout + risk_analyst + stock_analyst → 3 options → 6 holdings, each with purpose, 'why this rather than that' and evidence → proposal). It's replayed from the LLM cache at zero cost. **No shape changes**, only realistic content: real agent messages, a real agent tree, real investment cases. The underlying market data is the **synthetic** snapshot (labelled `data_source: synthetic`).
- **@Jin:** I'm adding a `--replay-db <sqlite>` option to `backend/scripts/make_fixtures.py`: it copies the LLM cache from a recorded live run and replays it (`LLM_MODE=replay`). It aborts if any call misses the cache. The default behaviour (fake) is unchanged.
- In the same PR (#30): `agents.yaml` `max_parallel` 3 → 5 (4 construction specialists were queueing: 252 s → 163 s). This is before the eval-freeze tag.

## Replies
