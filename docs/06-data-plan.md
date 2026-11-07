# 06 · Data plan

Owner: **Jin**. Code: `backend/app/data/`, `backend/scripts/fetch_snapshot.py`.

## 1. Summary

- **Historical: preload once, reveal day by day.** The historical demo never calls an external API.
- **Live: an end-of-day pull after each close, plus optional display quotes while someone is watching.** Well under 100 provider calls/day.
- **One subscription:** EODHD "EOD Historical Data — All World" ($19.99/month, one month, cancel afterwards). It allows 100,000 calls/day and 1,000/min; a multi-ticker request counts one call per symbol. Test LSE coverage on the free plan first (20 calls/day, past year only).
- **Free:**
  - Alpaca (US stock quotes/history)
  - Finnhub (US company news, earnings calendar)
  - Alpha Vantage (news for 2–3 hero tickers; 25/day)
  - SEC EDGAR (filings)
  - Gemini grounding (live only)
- **Fallback:** yfinance from a laptop for the snapshot (Yahoo often blocks cloud IPs, so never use it from the server).
- **Dev data now:** `python scripts/make_synthetic_snapshot.py` writes a **synthetic** snapshot with the same schema, so everyone can build before the real data lands. It's labelled `data_source: synthetic` everywhere.

## 2. Snapshot layout (`backend/data/snapshot/`)

| File | Schema |
|---|---|
| `prices_daily.parquet` | `date, ticker, open, high, low, close, adj_close, volume, currency, quote_unit, source`. Range **2023-01-02 → yesterday** |
| `fx_daily.parquet` | `date, pair, rate, source` (`GBPUSD`) |
| `news.jsonl` | `{id, tickers[], headline, summary, url, source, published_at, available_at, synthetic: bool}` |
| `filings.jsonl` | `{id, company, ticker, form, accepted_at, available_at, url, passages: [{id, text}]}` |
| `earnings.jsonl` | `{ticker, date, source}` |
| `macro.parquet` | `date, series, value, source` (UK base rate, CPI) |
| `etf_holdings.jsonl` | `{etf, as_of_download, holdings: [{name, ticker, weight}]}`. Current holdings, labelled as a proxy in historical mode |
| `manifest.json` | `{created_at, sources: {name: {downloaded_at, coverage: {ticker: [first, last]}, gaps: [...], delay}}}` |

The catalogue lives in `backend/app/config/catalogue.json` (hand-verified, versioned).

## 3. Rules (enforced in `DataGateway`)

- `prices(..., end)`: if `end > clock.now()` → `AsOfViolation` + `asof.violation` event.
- The sim acts at the **16:30 London close**: bars dated ≤ today are visible.
- **`available_at`:** news published after 16:30 becomes available the next trading day. Filings use EDGAR `accepted_at`. Only `available_at ≤ now` is returned.
- **GBX normalisation:** if `quote_unit == "GBX"`, divide by 100 in the loader. Store `quote_unit` for audit (unit-guard control).
- **Returns use `adj_close`.** USD instruments are converted with GBPUSD on the same date. Trade on the LSE calendar; forward-fill US prices over UK-only trading days, and vice versa.
- **Freshness:** `gw.freshness()` returns per-ticker `last_date`, `stale` (more than 3 trading days behind `as_of`) and `source`. It drives the badges and the "Monitoring degraded" status.

## 4. Fetch script (tonight)

`python scripts/fetch_snapshot.py --start 2023-01-02 --tickers config` steps:

1. **EODHD EOD** for every catalogue ticker + `GBPUSD.FOREX` (~30 calls).
2. **Finnhub** company news for US stocks, Nov 2025 → today, one call per stock per month (~120 calls at 60/min).
3. **Alpha Vantage** `NEWS_SENTIMENT` for 2–3 hero tickers (spread across keys).
4. **EDGAR** submissions + filing docs for US stocks. The SEC asks for a contact in the User-Agent: use a team address in `EDGAR_USER_AGENT`.
5. **Finnhub** earnings calendar; **macro** from Bank of England / ONS CSVs (manual download is fine).
6. **Sanity checks** (fail loudly): GBX normalised, no gaps > 3 trading days, FX aligned, every ticker covered from 2023-01 or marked ineligible before its start.
7. **Write `manifest.json`.**

Commit the snapshot if under ~50 MB, otherwise upload it to a GCS bucket and copy it in at build time.

## 5. Live mode

| Job | When (UK, weekdays) | Calls |
|---|---|---|
| EOD UK lines + FX | 17:00 | ~16 symbol-calls (EODHD) |
| EOD US stocks | 21:30 | ~10 (EODHD or Alpaca) |
| Display quotes, US | Every 30 min in US hours, only while the app is open or during judging | Alpaca free, batched |
| Display quotes, UK | Same | EODHD live (delayed) **if** the plan includes it (`s=` batching, 15–20 per request); otherwise "last close" with its date |
| News for holdings | Hourly | Finnhub, ~10/hour |
| Web context | Only inside triggered investigations | Gemini grounding |

- **Live = snapshot + top-up.** Same gateway code path; the scheduler appends new days.
- **On failure:** keep the last value, set `stale`, set status "Monitoring degraded", and emit a `notification(kind=coverage)`. Never present stale data as live.
- **Cron on the droplet** (see 12-hosting-and-deploy) calls `POST /api/tasks/live-eod` and `/api/tasks/live-news` with `X-Task-Secret`.

## 6. Hero events and synthetic items

- Pick 2–3 real events from **Apr–Nov 2026** (after Argon's reported knowledge cutoff) that hit holdings: one material (→ adjust), one alarming but immaterial (→ maintain).
- The **injection-guard** demo article is synthetic and must have `synthetic: true` and a visible "synthetic test item" label.
