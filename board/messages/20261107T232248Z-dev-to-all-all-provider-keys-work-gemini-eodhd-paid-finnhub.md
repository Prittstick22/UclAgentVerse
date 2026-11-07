---
id: 20261107T232248Z-dev-to-all-all-provider-keys-work-gemini-eodhd-paid-finnhub
from: dev
to: all
type: fyi
status: open
issue: 55
created: 2026-11-07T23:22Z
---
# All provider keys work: Gemini, EODHD (paid), Finnhub, Alpha Vantage, EDGAR

Dev has shared the keys privately (no secrets here). Put them in your repo-root `.env` (see `.env.example`). Checked with `backend/scripts/check_providers.py` on Sat 7 Nov ~23:20.

## Results
| Provider | Plan | Limits | Result |
|---|---|---|---|
| Gemini | hackathon key | see AI Studio | ✅ `gemini-4-argon` structured output 2.8 s / ~250 tokens · ✅ `gemini-3.8-flash` 2.9 s / ~220 tokens · ✅ `AgentStep` schema round-trip 4.1 s · ✅ Google Search grounding 6.0 s |
| EODHD | **All World, paid** ($19.99, one month) | 100k calls/day, 1,000/min | ✅ every catalogue ticker + `GBPUSD.FOREX` from **2023-01-03 → 2026-11-06** (~974 bars) · ✅ LSE units match the catalogue (AZN/SHEL/ULVR/HSBA = GBX) · ✅ live 15-min delayed quotes work |
| EODHD news | included in paid plan | same | ✅ **dated UK news**: Jul 7 → Aug 7 2026 gave 38 items for `AZN.LSE`, 32 for `SHEL.LSE`, 100+ for `NVDA.US`. Endpoint: `GET /api/news?s=<TICKER>&from=&to=&limit=` |
| Finnhub | free | 60 calls/min | ✅ company news AAPL Jul 2026: 247 items · ✅ NVDA last 7 days · ⚠️ no UK news (expected) · ⚠️ earnings calendar returned empty |
| Alpha Vantage | free | 25 calls/day | ✅ key works (`GLOBAL_QUOTE`) · ❌ **`NEWS_SENTIMENT` is now premium-only**, even without dates |
| SEC EDGAR | no key | 10 req/s, UA needs contact | ✅ Apple submissions with `acceptanceDateTime`. Set `EDGAR_USER_AGENT` to a real team email |
| Alpaca | deferred | n/a | not used for now, see #80 |

## What changes (for @Jin, #6/#7 `fetch_snapshot.py`)
- **News:** use **Finnhub** for US stocks plus **EODHD `/api/news`** for UK stocks (and US as a backup). **Drop Alpha Vantage news** (premium) and the hand-curated UK items, because EODHD has real dated UK headlines. Keep `available_at` (after 16:30 → next trading day).
- **Prices:** EODHD covers everything from 2023-01 → no ineligible tickers.
- **Live mode:** EODHD delayed quotes are fine for display.
- **Gemini: Argon for every agent** (the organisers asked for it): set `GEMINI_MODEL_DEEP=gemini-4-argon` **and** `GEMINI_MODEL_FAST=gemini-4-argon` in your `.env`. Fallback if rate limits bite: `GEMINI_MODEL_FAST=gemini-3.8-flash`. PR #81. Cost per call is still to come: Dev will measure it on the first real agent run (#28). `DAILY_LLM_BUDGET_USD=20` stays the cap.
- **Script fix:** `check_providers.py` used `requests`' `.ok` on `httpx` responses. Fixed in the PR for #55.

## Replies
