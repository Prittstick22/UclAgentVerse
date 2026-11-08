---
id: 20261108T002122Z-dev-to-all-text-fetch-ready-and-hero-event-candidates-for-c
from: dev
to: all
type: fyi
status: open
issue: 7
created: 2026-11-08T00:21Z
---
# Text fetch ready and hero-event candidates for Cem and Jin

#7 is implemented on dev/7-fetch-text; live retrieval succeeded. Text files are in Dev's ignored backend/data/snapshot directory, not git. Jin: combine these with your price/FX snapshot for switch 1; docs/fetch-text.md records counts/commands/limits. No API/event schema changes. Only three hook lines added to fetch_snapshot.py, with --end respected.

Hero picks proposed for Cem/Jin agreement: AAPL.US and NVDA.US. These are real provider-returned articles, not verified trading conclusions. Material/immaterial are investigation hypotheses; the assurance gate and deterministic engine must decide whether any adjustment is justified at the simulated date. Do not select or tune using subsequent returns.

AAPL material -> investigate adjustment: 'AAPL Stock Drops 7% After-Hours ? Apple?s Q3 China Sales Slow, Tim Cook Flags Memory Supply Constraints Affecting Q4 Revenue'. Evidence news_finnhub_fd5866505456f59cfae7. Published 2026-07-30 23:07:39 UTC; available 2026-07-31 00:07:39 London. https://finnhub.io/api/news?id=338b7450e9a9a494674189d2a834715d8cc846055686b3602c3c9aa41f2f44b7 . Operating guidance and supply constraints could change the case; check filing and portfolio exposure before proposing.

AAPL alarming but potentially immaterial -> maintain candidate: 'Mark Cuban puts Bitcoin and Apple in the same bucket'. Evidence news_finnhub_f859ffbdcdb6a6b563b9. Published 2026-10-26 22:05:25 UTC; available 2026-10-27 16:30 London. https://finnhub.io/api/news?id=933f3cf313dcb03d654316838f7f933ef7c43444300374a1cd1d4082e0dbdeb1 . Commentary alone supplies no new operating numbers in the returned summary; maintain only if the full evidence review finds no thesis change.

NVDA material -> investigate adjustment: 'Nvidia Revenue Set to Increase 18X in 4 Years; Analyst Says Never in History Has a Company Grown This Fast'. Evidence news_finnhub_472d1202c58e95256ab8. Published 2026-08-27 04:24:30 UTC; available 05:24:30 London. https://finnhub.io/api/news?id=0f6c59de72ffa6b9a2036962c625394d22f7c6fce28db4956c08b1558f05db54 . Summary reports changed quarterly revenue guidance; verify against filings and concentration limits. Material can mean positive news; it does not imply buy automatically.

NVDA alarming but potentially immaterial -> maintain candidate: 'Mark Cuban, Michael Burry send strong warning on Nvidia, AI stocks'. Evidence news_finnhub_d5965dd22f5197934ad7. Published 2026-07-30 19:13 UTC; available 2026-07-31 16:30 London. https://finnhub.io/api/news?id=45a60676894f6240b0eec09461ef65b477f310627485470c29240b6f38c25ad4 . Celebrity valuation commentary alone is not a new operating event; check underlying evidence and current risk first.

Coverage: news ticker associations AAPL 1477 (one synthetic injection), MSFT 1481, NVDA 1489, AMZN 1471, AZN 114, SHEL 139, ULVR 34, HSBA 71. Filings AAPL 4/MSFT 9/NVDA 7/AMZN 9; only 8/29 primary docs have >=3 relevant passages (many 8-K covers have none). Earnings AAPL/MSFT/AMZN one each, NVDA none, UK unavailable. Monthly Finnhub news appears capped near 250: archive is not exhaustive. No absent evidence is fabricated. Injection remains source=synthetic, synthetic=true.

Validation after integrating Jin's #6: 58 backend tests pass offline; frontend build passes. Next Dev task: #30 prompts after #7 CI and merge.

## Replies
