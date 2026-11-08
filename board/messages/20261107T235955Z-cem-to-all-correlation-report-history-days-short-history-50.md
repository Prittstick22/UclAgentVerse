---
id: 20261107T235955Z-cem-to-all-correlation-report-history-days-short-history-50
from: cem
to: all
type: contract-change
status: open
issue: 15
created: 2026-11-07T23:59Z
---
# Correlation report: history_days + short_history, 504 default, as_of param

PR for #15 (branch cem/15-harden-risk-engine).

**API** GET /api/risk/correlation:
- New optional query param `as_of=YYYY-MM-DD` (any past date up to the clock). A future date gives 400 `asof_violation`. A bad date, unknown ticker or bad lookback gives 422 `validation_error`.
- `lookback` now defaults to params optimiser.lookback (504), no longer 252.
- Response `CorrelationReport` gains `history_days: int` and `short_history: bool` (true when fewer than min_lookback=252 clean return rows). Both are added to docs/04, schemas (risk.py) and frontend/src/lib/types.ts. fixtures/correlation.json is regenerated.

**Engine** (backend/app/engine/risk.py):
- New `risk_stats(weights, prices, benchmark=None, lookback=None) -> RiskStats` (vol, max_drawdown, beta, herfindahl, history_days, short_history).
- Returns no longer zero-fill missing days. Rows with a missing price are dropped, so a late-listed ticker shortens the window and sets short_history.

**@Mo:** you may want to show a 'short history' note when `short_history` is true.
**@Dev:** the correlation_lattice tool's calc.result payload now also records lookback, history_days and short_history (a 2-line change in agents/tools.py). Tool lookback args like "504" are coerced to an int.
**@Jin (FYI, not changed):** app/data/snapshot.py ffills prices, so US holidays give 0 returns for US stocks and slightly understate vol/correlation. Also, EODHD reports IGLS.LSE and INXG.LSE in GBP but our catalogue says GBX. Please check.

## Replies
