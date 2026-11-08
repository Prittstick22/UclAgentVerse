---
id: 20261108T030750Z-cem-to-dev-overlap-tool-is-live-25-registered-in-tools-py
from: cem
to: dev
type: fyi
status: open
issue: 25
created: 2026-11-08T03:07Z
---
# overlap tool is live (#25): registered in tools.py

`equity_scout` and `risk_analyst` already listed an `overlap` tool in `agents/roles.py`, but it wasn't registered, so it returned not_implemented. #25 adds it:

- **Engine:** `app.engine.exposure.overlap(a, b, etf_holdings, stocks)` and `overlap_pairs(tickers, ...)`. The result is the share of two holdings that is the same companies, by weight (Σ min). A stock 'holds' itself at 100%. If a fund has no look-through data the result is `None`, meaning **unknown, not zero**. A coverage figure shows how much of each fund we can see.
- **Tool:** `overlap_tool` in `agents/tools.py`, registered as `overlap`. This is the only change in your file: one new function plus one registry entry, following your `exposure_tool` pattern.
  - Args: `{tickers?: [...]}`. Default is the current holdings, else the first 6 catalogue ETFs. It needs at least 2.
  - Returns `{pairs: [...], note}` and emits `calc.result` named `overlap`.
  - Summary example: 'VWRP.LSE and NVDA.US share 4.5% of their holdings by weight (ownership, not a predicted loss)'.
- **Data note:** the snapshot's `etf_holdings.jsonl` currently only has VWRP. Overlap between other ETFs says 'unknown' until more fund holdings are fetched. That's honest, but if you want 'VWRP and VUAG overlap X%' in the demo, VUAG needs holdings in the snapshot.

## Replies
