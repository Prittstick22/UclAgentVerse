# Live cache and mode switching (#11)

Implementation is on `jin/11-live-mode`; deployments remain Dev's responsibility.

## Modes

`POST /api/mode {"mode":"live"}` selects a separate app state with a
`LiveClock`, paper ledger, mandate, proposals, runs, gateway and database.
Switching back restores the historical clock and portfolio without resetting
them. Both states are warmed during app startup. Switching does not start an
agent, call a provider or trade. Invalid modes are rejected with HTTP 422.

The selected mode is shared by this single-user demo server, not per browser.
In-process switching preserves each portfolio; durable ledger reconstruction
across server restarts remains part of the ledger/portfolio work, not this cache.

## Refresh jobs

Use the existing secret-protected endpoints:

- `POST /api/tasks/live-eod`: London weekdays, after 17:00 for UK instruments
  and GBPUSD, and after 21:30 for US instruments.
- `POST /api/tasks/live-news`: held instruments only; Finnhub for US holdings,
  EODHD for London holdings. Once per holding per London hour.

Handlers authenticate `X-Task-Secret`, schedule a background job, and return
the existing `{ok, fetched, stale}` shape immediately. `ok: true` means the
job was accepted; `fetched: 0` is not a completion count. `stale` reports the
cache at acceptance. Observe existing `tool.call`/`tool.result` events for
completion and the persistent coverage notifications for failures. The worker
method returns its actual refresh result for tests/internal callers.

GET requests never call providers. Refresh jobs always target the live
namespace even when the UI is viewing the historical demo. Jobs are serialized
with a nonblocking in-process lock. Run **one application worker**; distributed
locking and a multi-worker counter are not implemented.

Each attempted provider request increments a persistent daily counter in the
live database (`live_provider_calls`, London date). The cap is 99, including
failed calls. Successful EOD requests are skipped for the rest of the day once
today's bar exists; absent current bars remain retryable. Successful news
requests are skipped for the current hour. This keeps retries below 100 calls
per day but can exhaust news capacity with many holdings; failures then remain
visible as coverage degradation rather than calling beyond the cap.

## Data and failures

Live files are written below `SNAPSHOT_DIR/live/`, never over the historical
snapshot. Rows are upserted by `(date,ticker)` and `(date,pair)`; articles by
stable source/URL ID. Price units remain raw in Parquet and are normalised by
the gateway's snapshot loader. Cache files use per-file atomic replacement.
On restart, the live namespace reloads the live cache if present.

The injection guard runs before new live news is published; quarantined text
is not included in the cache. Future-dated news is rejected. Synthetic seed
data is not relabelled as wholly real: mixed prices use `synthetic+eodhd`.

On provider/persistence failure, retain cached values, record a coverage
notification and mark affected tickers stale. Exception messages and provider
URLs are not logged because they may contain credentials. Successful refreshes
clear the corresponding price/news failure, without clearing failures in the
other category. Failure state and call counts survive process restarts.

Freshness uses each ticker's original raw bar dates, not the forward-filled
valuation matrix. More than the frozen stale-day threshold of missing weekdays
sets stale. Weekdays approximate exchange calendars and may conservatively
flag extended holiday closures. The live portfolio response exposes existing
holding fields `price_as_of` and `stale`, and `monitoring_degraded` when cache
coverage is stale or a refresh has failed. The UI labels cached closes and
shows the original price date rather than presenting an old value as live.

## Validation and deployment

Run the offline backend tests and frontend build. Tests use fake providers;
they do not read provider credentials or call the network. No new API or event
shape was introduced. Existing cron examples are in
[hosting and deploy](12-hosting-and-deploy.md); this issue does not change
Dev's deploy files or install cron on the droplet. Hosted task execution and
remote UI verification remain deployment checks.
