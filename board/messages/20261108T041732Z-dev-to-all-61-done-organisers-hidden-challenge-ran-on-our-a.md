---
id: 20261108T041732Z-dev-to-all-61-done-organisers-hidden-challenge-ran-on-our-a
from: dev
to: all
type: fyi
status: open
issue: 61
created: 2026-11-08T04:17Z
---
# #61 done: organisers' hidden challenge ran on our adapter (no edge claimed, 0 provenance flags)

PR #124 is merged. Details and the exact command are in docs/finance-kit.md; evidence is in `eval/finance-kit/` (REPORT, COMMITMENT, SEED-REVEAL).

| Pack | Paths | W/L/T vs buy-and-hold | Sign-test p | Kit verdict |
|---|---|---|---|---|
| markets (synthetic) | 60 | 24/11/25 | 0.041 | not distinguishable |
| real-markets (real, anonymised) | 60 | 14/14/32 | 1.00 | not distinguishable |

- 0 errors; **provenance review: none flagged**. A first markets run made before the adapter was committed is kept and disclosed, not quoted.
- **For the deck (Jin #84, Dev #39):** an honest slide: 'On the organisers' hidden test with real price paths, our risk rule matched buy-and-hold (no claimed edge) with no look-ahead.' Pair it with our own real-data replay (#24).
- **@Jin (#70 README):** please add *'Organisers: please run the finance-kit challenge with `--pack markets` and `--pack real-markets`; adapter command: `cd backend && python -m app.eval.finance_kit_adapter`. Cashflow/transactions are outside our product.'*
- `.gitignore`: `eval/` is now `/eval/*` + `!/eval/finance-kit/` (the old rule also hid `backend/app/eval/`). **@Cem:** your generated `eval/metrics.json` etc. are still ignored.

## Replies
