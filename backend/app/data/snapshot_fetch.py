"""Price/FX snapshot preparation; provider calls stay outside business logic."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd


def price_frame(provider, instruments: list[dict], start: str, end: str) -> pd.DataFrame:
    frames = []
    for instrument in instruments:
        ticker = instrument["ticker"]
        frame = pd.DataFrame(provider.eod(ticker, start, end))
        if frame.empty:
            raise ValueError(f"Missing prices for {ticker}")
        frame = frame.rename(columns={"adjusted_close": "adj_close"})
        frame["ticker"] = ticker
        frame["currency"] = instrument["currency"]
        frame["quote_unit"] = instrument["quote_unit"]
        frame["source"] = "eodhd"
        frames.append(frame[["date", "ticker", "open", "high", "low", "close", "adj_close",
                             "volume", "currency", "quote_unit", "source"]])
    return pd.concat(frames, ignore_index=True).sort_values(["date", "ticker"])


def fx_frame(provider, start: str, end: str) -> pd.DataFrame:
    frame = pd.DataFrame(provider.eod("GBPUSD.FOREX", start, end))
    if frame.empty:
        raise ValueError("Missing GBPUSD FX")
    return frame.rename(columns={"close": "rate"}).assign(pair="GBPUSD", source="eodhd")[
        ["date", "pair", "rate", "source"]
    ].sort_values("date")


def validate(prices: pd.DataFrame, fx: pd.DataFrame, instruments: list[dict], start: str, end: str) -> dict:
    expected = {row["ticker"] for row in instruments}
    if set(prices["ticker"]) != expected:
        raise ValueError("Price ticker coverage does not match catalogue")
    if prices.duplicated(["date", "ticker"]).any() or fx.duplicated(["date", "pair"]).any():
        raise ValueError("Duplicate snapshot rows")
    for frame, columns in ((prices, ["open", "high", "low", "close", "adj_close"]), (fx, ["rate"])):
        values = frame[columns].to_numpy(dtype=float)
        if not np.isfinite(values).all() or (values <= 0).any():
            raise ValueError("Snapshot contains invalid or non-positive prices/rates")
        dates = pd.to_datetime(frame["date"])
        if (dates < pd.Timestamp(start)).any() or (dates > pd.Timestamp(end)).any():
            raise ValueError("Snapshot dates outside requested window")
    calendar = pd.bdate_range(start, end)
    coverage = {}
    for instrument in instruments:
        ticker = instrument["ticker"]
        rows = prices.loc[prices["ticker"].eq(ticker)]
        if not rows["currency"].eq(instrument["currency"]).all() or not rows["quote_unit"].eq(
            instrument["quote_unit"]
        ).all():
            raise ValueError(f"Quote unit/currency mismatch for {ticker}")
        dates = pd.DatetimeIndex(pd.to_datetime(rows["date"])).sort_values()
        # Weekday slots deliberately allow up to three exchange holidays/missing bars.
        _check_gaps(calendar, dates, ticker)
        coverage[ticker] = [dates.min().date().isoformat(), dates.max().date().isoformat()]
    fx_dates = pd.DatetimeIndex(pd.to_datetime(fx.loc[fx["pair"].eq("GBPUSD"), "date"]))
    if fx_dates.empty:
        raise ValueError("Missing GBPUSD FX")
    _check_gaps(calendar, fx_dates, "GBPUSD")
    # Every valuation day must have a same-day or earlier rate, never a future backfill.
    aligned = fx.set_index(pd.to_datetime(fx["date"]))["rate"].sort_index()
    aligned = aligned.reindex(aligned.index.union(pd.to_datetime(prices["date"]).unique())).ffill()
    if aligned.reindex(pd.to_datetime(prices["date"]).unique()).isna().any():
        raise ValueError("FX unavailable on first price date")
    return coverage


def _check_gaps(calendar: pd.DatetimeIndex, dates: pd.DatetimeIndex, label: str) -> None:
    missing = ~calendar.isin(dates)
    longest = run = 0
    for absent in missing:
        run = run + 1 if absent else 0
        longest = max(longest, run)
    if longest > 3:
        raise ValueError(f"{label}: gap of {longest} weekdays (maximum 3)")


def write_manifest(out: Path, coverage: dict) -> None:
    path = out / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    downloaded_at = datetime.now(UTC).isoformat()  # Acquisition audit, not simulation time.
    manifest.update(label="eodhd", created_at=downloaded_at)
    manifest.setdefault("sources", {})["eodhd"] = {
        "downloaded_at": downloaded_at, "coverage": coverage, "gaps": [], "delay": "end of day",
        "unit_check": "catalogue units checked; raw provider scale requires issuer/provider cross-check",
    }
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
