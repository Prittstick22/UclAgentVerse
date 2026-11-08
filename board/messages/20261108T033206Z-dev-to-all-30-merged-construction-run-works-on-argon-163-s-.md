---
id: 20261108T033206Z-dev-to-all-30-merged-construction-run-works-on-argon-163-s-
from: dev
to: all
type: fyi
status: open
issue: 30
created: 2026-11-08T03:32Z
---
# #30 merged: construction run works on Argon (163 s, every holding explained); 4-month run unblocked

PR #120 is merged.

- **Construction on real Argon:** lead → equity_scout, bond_scout, risk_analyst, stock_analyst (parallel) → `build_options` → investment cases for every holding → proposal. Run 5: **163 s, 14 calls, $0.18**; 6 holdings, each with a purpose, 'why this rather than that' and evidence ids. The 2-minute target wasn't met; the build is async and streams, and the demo replays.
- **Agents now get code-generated context:** the exact roles they may spawn, implemented tools with argument examples, and a MANDATE line. No more invented roles or tickers.
- **Config:** `agents.yaml` `max_parallel` 3 → 5 (before eval-freeze). **@Cem:** please include it in the freeze.
- **@Mo:** `fixtures/` now come from that real run (`make_fixtures.py --from-db`): the real agent tree, messages, proposal with purposes and why-not, and investment cases. Same shapes. Market data is the synthetic snapshot.
- **Dev:** the 4-month run can start once the real snapshot is fetched and eval-freeze is tagged. It uses the default `--profile balanced` (persona Priya).

## Replies
