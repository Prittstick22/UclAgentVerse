# AgentVerse finance kit: what it is and how we use it (#60, #61)

Owner: Dev. The kit is the organisers' testing harness for the Finance track. Their **challenge mode** (hidden, sealed-seed cases) is very likely how "testing on unseen data" is judged, so we plug our real code into it. Our own real-data replay (7 Jul → 6 Nov 2026) stays a **separate** result.

## Where it is
- The organisers' download sits **next to** the repo, not inside it: `../agentverse/` (Dev's PC: `UCL Agent Verse hackathon/agentverse/`). **Never commit it.** `agentverse/` is in `.gitignore` in case someone drops it into the repo.
- Entry points: `agentverse/START-HERE.md`, `agentverse/finance/TESTING.md` (full protocol), `agentverse/finance/DATA.md`, `agentverse/finance/bench.py` (CLI). Python 3.9+, standard library only, no keys. Checked on Dev's PC: `bench.py generate` + `run --baseline` work.

## What the kit tests (built-in packs)

| Pack | Task sent to our adapter | What is scored | Fits our product? |
|---|---|---|---|
| `markets` (synthetic paths) | `market_step`: `input.history` (prices so far, pence), `cash_pence`, `shares`, `fee_pence`, `slippage_bps` → reply `{"action": "buy" \| "hold" \| "sell"}` | Sequential runner fills at the **next** price, then reports P&L, costs, drawdown and wins vs buy-and-hold with a sign-test p-value. Completion is not a pass. | **Yes: our risk/rebalancing rules, applied to one asset.** |
| `real-markets` | same, on **real** Binance hourly/4-hourly windows (rebased, anonymised, half inverted) | same | **Yes** (needs internet; Binance Vision data, CC BY-NC-SA 4.0) |
| `cashflow` | opening balance + dated payments → closing/minimum balance, shortfall, first negative date | exact match | No (not our product). Skip. |
| `transactions` | transfers → 3-account cycles, large transfers, total | exact match | No (AML-style). Skip. |
| custom (`import`) | any task with our own inputs + independently written answers | exact match | Useful as **practice** evidence for our verification layer (mandate checker, costs), but custom packs can't run in challenge mode. |

`mixed` mixes cashflow, transactions and markets. For us, the meaningful challenge packs are **`markets`** and **`real-markets`**. If the organisers run `mixed` on everyone, our adapter answers `{"error": "unsupported_task"}` for cashflow/transactions; we say so openly rather than bolting on features that aren't our product. (The kit's own guidance: *testing a kit example does not count as testing your submission*.)

## Protocol (adapter)
- `bench.py` starts our adapter command once and sends **one JSON request per line on stdin**: `{"request_id", "case_id", "task", "input"}`. We reply with one line per request on stdout: `{"request_id": ..., "output": {...}}`, flushed. **Logs go to stderr only**: a stray `print` to stdout stops the run.
- Default limits: 10 s per response, 120 s per practice run (900 s in challenge). Market cases make one request per bar, so **no LLM call per step**: Argon takes about 10 s per call.
- Money is integer GBP pence. Market fills: buy uses all cash, sell closes the position, integer shares, fixed fee, adverse slippage, forced liquidation at the end.
- **Challenge mode** (`bench.py challenge`): a secret seed with a public SHA-256 commitment; cases exist in memory only; `AGENTVERSE_CHALLENGE=1` disables the kit's reference code; the project is scanned for imports of kit code or answer files. **Our adapter must not import anything from the kit.** Organiser judging: `challenge --seed-prompt --team "<name>" --pack <pack> --project <repo> --adapter <our command>`.

## How we plug in (#61)
- **Adapter:** `backend/app/eval/finance_kit_adapter.py` (new, Dev's area). It reads stdin JSONL and, for `market_step`, calls a deterministic rule built from **our engine** (`app.engine.risk`: trailing volatility and drawdown from the observed history only). The rule is the same risk discipline the product uses: stay invested; step aside to cash when trailing drawdown or volatility breaches a fixed band; re-enter when conditions normalise. Parameters are constants fixed **before** any challenge run (never tuned on challenge results); they're disclosed in the README. Agents are not called per step (timeout); that's stated plainly.
- **Command:** `cd backend && .venv/Scripts/python -m app.eval.finance_kit_adapter`.
- **Practice:** `python ../agentverse/finance/bench.py generate --pack markets --cases 25 --seed 1 --output <scratch>/m` → `bench.py run --dataset <scratch>/m --output <scratch>/r --limit 25 --adapter <cmd>`. Practice numbers are for debugging only and **must never be quoted**.
- **Claimable result:** `bench.py challenge --pack markets --cases 60 --project . --output eval/finance-kit/challenge-1 --adapter <cmd>`, then `--pack real-markets`. Commit the `REPORT.md`, `COMMITMENT.txt` and `SEED-REVEAL.txt` and disclose any reruns. Report honestly against buy-and-hold: "not distinguishable from buy-and-hold" is an acceptable, honest result.
- **Offline test** (`backend/tests/test_finance_kit_adapter.py`): pipe two fake `market_step` lines into the adapter and check the reply format, that it never looks past `history`, and that unsupported tasks return an error. No kit import in tests either.
- Label everywhere: **"organiser synthetic test data"** (markets) / **"real Binance windows, anonymised"** (real-markets). Add Binance Vision (CC BY-NC-SA 4.0, non-commercial) to `docs/DATA_SOURCES.md` if we run real-markets.

## Not used
- `cashflow`, `transactions`: not our product.
- The optional MCP server, `live` forward test (30 min per run; only if time is spare) and `review-and-push` (we already have CI + PR flow; its Gitleaks scan is a good **pre-submission secret check**, see the Sunday checklist).

## Takeaways from the organisers' builder guide (UCL AgentVerse 2026)
- **Judging:** live working software; a named user; a verification loop; a human in control of money actions; a live demo **under 3 minutes**, opening on working software within 30 s, with a local screen recording as backup; a README naming the user problem, the **exact model IDs** and how the verification loop works. We match these: first-time UK investor, engine checker + assurance gate, approval before any trade.
- **Argon API notes:** Argon **ignores `temperature`** (deprecation warning). Reasoning depth is `thinking_level` (`low` | `medium` default | `high`) on the Interactions API. Implicit prefix caching gives a 95% input discount automatically. Pricing is $2 in / $10 out per 1M tokens to 30 Nov 2026 (matches `agents.yaml`).
- **Best Use of Gemini prize** wants 2+ modalities in one loop. A cheap fit for us, *only if MVP is done*: read the decision card aloud with `gemini-3.8-flash-tts`, or have the news analyst read an earnings webcast. Not planned yet.
- **Pre-submission:** feature freeze 2 h before the deadline; audit the repo and history for secrets.
