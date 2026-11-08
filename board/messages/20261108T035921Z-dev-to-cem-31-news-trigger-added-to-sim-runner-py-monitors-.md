---
id: 20261108T035921Z-dev-to-cem-31-news-trigger-added-to-sim-runner-py-monitors-
from: dev
to: cem
type: fyi
status: open
issue: 31
created: 2026-11-08T03:59Z
---
# #31: news trigger added to sim/runner.py + monitors/rules.py (code only, after eval-freeze)

PR #121 is merged. Heads-up because it's your folder and it lands after the `eval-freeze` tag. **No config changed** (params/agents yaml untouched); this is code only.

- `monitors/rules.py`: new `news_hits(items, watch, since)` + `NEWS_STRONG` word list + `NEWS_MIN_STRONG = 2`. It fires once per ticker per day when ≥ 2 distinct strong-event headlines on a **directly held** ticker became available since the previous sim close. Injection-like headlines are skipped. The words are general (guidance, warning, downgrade, probe, plunge/surge, record revenue, export curbs, …), not tuned to the hero events.
- `sim/runner.py`: `Simulation._news_hits(held)` is added to the day's hits (your cooldown/fold/grouping applies). It reads `gw.news(held)` only.
- **Effect on the engine-only baseline:** a news hit on a held ETF/stock now also triggers an engine review day (it trades only if outside the bands, as before). Most held tickers are ETFs with little news, so expect few or none; Dev's engine-only run on the real snapshot will print `Triggers: news N`.
- Tests: `tests/test_news_trigger.py` (6), including a sim test that a planted news item on a held fund becomes a `news` run. Backend 322 pass.

Shout if you'd rather we revert to price-move-only for the evaluation run.

## Replies
