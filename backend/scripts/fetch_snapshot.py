#!/usr/bin/env python3
"""Fetch the REAL snapshot (run once, from a laptop). Owner: Jin. Spec: docs/06-data-plan.md §4.

SCAFFOLD: argument parsing + step list. Implement each step in its issue.
    python scripts/fetch_snapshot.py --start 2023-01-02 [--out data/snapshot] [--only prices,news]
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

STEPS = ["prices", "fx", "news", "filings", "earnings", "macro", "etf_holdings", "checks", "manifest"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2023-01-02")
    ap.add_argument("--end", default=(date.today() - timedelta(days=1)).isoformat())
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "data" / "snapshot"))
    ap.add_argument("--only", default=",".join(STEPS))
    a = ap.parse_args()
    steps = a.only.split(",")
    if set(steps) - set(STEPS):
        ap.error("Unknown snapshot step")
    if a.start > a.end:
        ap.error("--start must not be after --end")
    import httpx
    import pandas as pd

    from app.config import catalogue_raw
    from app.data.adapters.eodhd import EODHD
    from app.data.snapshot_fetch import fx_frame, price_frame, validate, write_manifest
    from app.settings import Settings

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    instruments = catalogue_raw()
    if {"prices", "fx"} & set(steps):
        key = Settings().eodhd_api_key
        if not key:
            ap.error("EODHD_API_KEY is required for prices/FX")
        provider = EODHD(key)
        try:
            if "prices" in steps:
                prices = price_frame(provider, instruments, a.start, a.end)
            else:
                prices = pd.read_parquet(out / "prices_daily.parquet")
            if "fx" in steps:
                fx = fx_frame(provider, a.start, a.end)
            else:
                fx = pd.read_parquet(out / "fx_daily.parquet")
            validate(prices, fx, instruments, a.start, a.end)
            if "prices" in steps:
                prices.to_parquet(out / "prices_daily.parquet", index=False)
            if "fx" in steps:
                fx.to_parquet(out / "fx_daily.parquet", index=False)
        except httpx.HTTPError:
            ap.exit(1, "EODHD request failed; check credentials, connectivity and plan coverage.\n")
        finally:
            provider.client.close()
    if {"checks", "manifest"} & set(steps):
        coverage = validate(pd.read_parquet(out / "prices_daily.parquet"),
                            pd.read_parquet(out / "fx_daily.parquet"), instruments, a.start, a.end)
        if "manifest" in steps:
            write_manifest(out, coverage)
    for step in a.only.split(","):
        if step in {"prices", "fx", "checks", "manifest"}:
            print(f"[{step}] complete")
            continue
        print(f"[{step}] TODO: implement (see docs/06-data-plan.md §4 and the GitHub issue)")
        # prices:  app.data.adapters.eodhd.EODHD(key).eod(ticker, start) for every catalogue ticker → prices_daily.parquet
        # fx:      EODHD eod("GBPUSD.FOREX") → fx_daily.parquet
        # news:    Finnhub company_news per US stock per month; EODHD /api/news for UK stocks (Alpha Vantage is NOT used)
        # filings: Edgar submissions + documents → filings.jsonl (accepted_at → available_at)
        # checks:  GBX normalised, gaps <= 3 days, FX aligned, coverage from 2023-01 → fail loudly
        # manifest: label="eodhd", coverage per ticker, gaps, downloaded_at


if __name__ == "__main__":
    main()
