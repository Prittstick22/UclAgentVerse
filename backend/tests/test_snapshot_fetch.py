"""No-network tests for the real snapshot acquisition pipeline."""
import json

import pandas as pd
import pytest

from app.data.snapshot import Snapshot
from app.data.snapshot_fetch import fx_frame, price_frame, validate, write_manifest

INSTRUMENTS = [
    {"ticker": "TEST.LSE", "currency": "GBP", "quote_unit": "GBX"},
    {"ticker": "TEST.US", "currency": "USD", "quote_unit": "USD"},
]


class Provider:
    def eod(self, ticker, start, end):
        value = 1.25 if ticker == "GBPUSD.FOREX" else 100
        return [{"date": day.date().isoformat(), "open": value, "high": value,
                 "low": value, "close": value, "adjusted_close": value, "volume": 10}
                for day in pd.bdate_range(start, end)]


def test_snapshot_roundtrip_units_fx_and_manifest(tmp_path):
    prices = price_frame(Provider(), INSTRUMENTS, "2026-07-01", "2026-07-10")
    fx = fx_frame(Provider(), "2026-07-01", "2026-07-10")
    coverage = validate(prices, fx, INSTRUMENTS, "2026-07-01", "2026-07-10")
    prices.to_parquet(tmp_path / "prices_daily.parquet", index=False)
    restored = pd.read_parquet(tmp_path / "prices_daily.parquet")
    converted = Snapshot(prices=restored, fx=fx).adj_close_gbp()
    assert converted["TEST.LSE"].iloc[0] == 1
    assert converted["TEST.US"].iloc[0] == 80
    write_manifest(tmp_path, coverage)
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["label"] == "eodhd"
    assert manifest["sources"]["eodhd"]["coverage"]["TEST.LSE"] == ["2026-07-01", "2026-07-10"]


@pytest.mark.parametrize("problem", ["missing", "gap", "unit", "invalid", "duplicate", "fx"])
def test_bad_snapshot_fails_loudly(problem):
    prices = price_frame(Provider(), INSTRUMENTS, "2026-07-01", "2026-07-10")
    fx = fx_frame(Provider(), "2026-07-01", "2026-07-10")
    if problem == "missing":
        prices = prices[prices.ticker.eq("TEST.LSE")]
    elif problem == "gap":
        prices = prices[prices.date.ge("2026-07-07")]
    elif problem == "unit":
        prices.loc[prices.ticker.eq("TEST.LSE"), "quote_unit"] = "GBP"
    elif problem == "invalid":
        prices.loc[prices.index[0], "adj_close"] = -1
    elif problem == "duplicate":
        prices = pd.concat([prices, prices.iloc[:1]])
    else:
        fx = fx.iloc[1:]
    with pytest.raises(ValueError):
        validate(prices, fx, INSTRUMENTS, "2026-07-01", "2026-07-10")
