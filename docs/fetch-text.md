# Dated text snapshot (#7)

From `backend`, run `LLM_MODE=fake .venv/Scripts/python scripts/fetch_text.py`.
On PowerShell set `$env:LLM_MODE='fake'` first. Use `--only news,filings,earnings`,
`--out <directory>` and optionally `--end YYYY-MM-DD`. The same steps work through
`fetch_snapshot.py --only news,filings,earnings`. Output files are replaced atomically
per step; price, FX and manifest files are untouched. Provider failures leave that
step's previous file intact and suppress credential-bearing request URLs.

News uses Finnhub for US stocks and paginated EODHD for UK stocks, monthly from
1 June 2026. Duplicate URLs merge ticker associations. Timestamps require a timezone;
weekdays through 16:30 London retain publication time, otherwise availability moves
to the next weekday at 16:30. This follows the agreed weekday rule, without a bank
holiday calendar. The single synthetic injection article remains explicitly labelled.

EDGAR uses acceptance time, not the report date. The primary document is stripped
of markup and up to ten relevant passages are retained, capped at 600 characters.
Short 8-K cover documents sometimes have fewer than three relevant passages; the
script reports these rather than inventing evidence or silently skipping filings.
Finnhub calls are spaced by 1.1 seconds; SEC requests by 0.15 seconds. Configure a
real team contact in the ignored `.env` variable `EDGAR_USER_AGENT`.

## Live retrieval on 8 November 2026

| Ticker | News associations | Filings | Earnings |
|---|---:|---:|---:|
| AAPL.US | 1477 (includes one synthetic item) | 4 | 1 |
| MSFT.US | 1481 | 9 | 1 |
| NVDA.US | 1489 | 7 | 0 |
| AMZN.US | 1471 | 9 | 1 |
| AZN.LSE | 114 | 0 | 0 |
| SHEL.LSE | 139 | 0 | 0 |
| ULVR.LSE | 34 | 0 | 0 |
| HSBA.LSE | 71 | 0 | 0 |

These are retrieved coverage counts, not completeness guarantees. Finnhub monthly
news responses appear capped near 250 records and are not an exhaustive archive.
Only eight of 29 primary filing documents yielded at least three relevant passages.
UK earnings are unavailable on these free plans; US earnings responses are sparse.
Do not interpret absent rows as proof that no event occurred. Files stay in the
ignored local snapshot directory; teammates need the separate snapshot handoff.

Hero-event candidates and evidence IDs are posted to the board for Cem/Jin to
review. Their materiality labels are hypotheses for the assurance gate and engine,
not pre-approved trades or promises of returns.
