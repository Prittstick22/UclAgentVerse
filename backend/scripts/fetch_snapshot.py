#!/usr/bin/env python3
"""Fetch the REAL snapshot (run once, from a laptop). Owner: Jin. Spec: docs/06-data-plan.md §4.

SCAFFOLD: argument parsing + step list. Implement each step in its issue.
    python scripts/fetch_snapshot.py --start 2023-01-02 [--out data/snapshot] [--only prices,news]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

STEPS = ["prices", "fx", "news", "filings", "earnings", "macro", "etf_holdings", "checks", "manifest"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2023-01-02")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "data" / "snapshot"))
    ap.add_argument("--only", default=",".join(STEPS))
    a = ap.parse_args()
    for step in a.only.split(","):
        print(f"[{step}] TODO: implement (see docs/06-data-plan.md §4 and the GitHub issue)")
        # prices:  app.data.adapters.eodhd.EODHD(key).eod(ticker, start) for every catalogue ticker → prices_daily.parquet
        # fx:      EODHD eod("GBPUSD.FOREX") → fx_daily.parquet
        # news:    Finnhub company_news per US stock per month; EODHD /api/news for UK stocks (Alpha Vantage is NOT used)
        # filings: Edgar submissions + documents → filings.jsonl (accepted_at → available_at)
        # checks:  GBX normalised, gaps <= 3 days, FX aligned, coverage from 2023-01 → fail loudly
        # manifest: label="eodhd", coverage per ticker, gaps, downloaded_at


if __name__ == "__main__":
    main()
