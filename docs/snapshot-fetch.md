# Price/FX snapshot acquisition (#6)

Use Python 3.11+ and the installed backend dependencies. Set `EODHD_API_KEY`
through the approved environment; never put it in commands or source control.

From `backend/`:

```sh
python scripts/fetch_snapshot.py --start 2023-01-02 --end 2026-11-06 --only prices,fx,manifest --out data/real-snapshot
```

Use a separate directory until the real snapshot has passed review. Do not
overwrite the synthetic development snapshot during acquisition.

The script preserves raw quote units in Parquet. `Snapshot.adj_close_gbp()`
normalises GBX and converts USD for valuation. It rejects missing tickers,
duplicate rows, non-positive/non-finite prices, unexpected date ranges,
catalogue unit mismatches, gaps longer than three weekdays (including the
window boundaries), and missing initial FX coverage. Weekdays are a
conservative calendar approximation, allowing up to three missing days for
exchange holidays. FX is forward-filled only for validation, never backfilled.

The manifest preserves other source records and adds EODHD coverage and
download time. Metadata checks cannot establish the raw provider's true
unit scale: confirm IGLS/INXG GBP and SGLN GBX against provider/issuer values
before accepting the real download. Do not infer units from price magnitude
alone. Correlation of VWRP and VUAG (>0.8), health source label, fetch duration
(<2 minutes), and the droplet copy remain real-data acceptance checks.
Deployments and droplet transfer are coordinated with Dev.

## Local real-data verification (8 November 2026)

Downloaded all 18 catalogue instruments plus GBPUSD for 2 January 2023
through 6 November 2026 in approximately 7 seconds. The first trading day
is 3 January 2023. There are 17,501 price rows; the three snapshot files
total 674,726 bytes. All coverage, gap, unit-metadata and FX checks passed.

With `snapshot_dir=data/real-snapshot`, the application health endpoint
returns `data_source: eodhd`. At the 7 July simulation start, the gateway
exposes nothing after that date. VWRP/VUAG daily-return correlation over
the visible history is 0.9577 (acceptance threshold >0.8).

Latest raw provider closes (6 November): IGLS 125.98 GBP, INXG 11.03 GBP,
SGLN 5,892 GBX. These agree with the catalogue unit correction and the
issuer listing conventions recorded in [the catalogue audit](catalogue-verification.md).
The round-trip unit test confirms GBX is divided by 100 once, not twice.
The separate real-data directory is Git-ignored; the synthetic snapshot is
unchanged. Droplet transfer and remote health verification remain pending
with Dev; the local result does not establish a deployment.

News/filings/earnings are owned by Dev under #7; this change implements only
prices, FX, checks and manifest. The other acquisition steps remain scaffolded.
