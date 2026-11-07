"""Load the preloaded data snapshot (backend/data/snapshot/) into memory. Schema: docs/06-data-plan.md §2."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from app.data.models import Filing, NewsItem


@dataclass
class Snapshot:
    prices: pd.DataFrame                    # long: date, ticker, close, adj_close, currency, quote_unit, source
    fx: pd.DataFrame                        # long: date, pair, rate
    news: list[NewsItem] = field(default_factory=list)
    filings: list[Filing] = field(default_factory=list)
    earnings: list[dict] = field(default_factory=list)
    etf_holdings: dict[str, list[dict]] = field(default_factory=dict)
    manifest: dict = field(default_factory=dict)

    @property
    def source_label(self) -> str:
        return self.manifest.get("label", "unknown")

    def adj_close_gbp(self) -> pd.DataFrame:
        """Wide DataFrame (date index × ticker) of adjusted close in GBP. GBX normalised, USD converted."""
        p = self.prices.copy()
        p["date"] = pd.to_datetime(p["date"])
        gbx = p["quote_unit"].eq("GBX")
        p.loc[gbx, "adj_close"] = p.loc[gbx, "adj_close"] / 100.0
        wide = p.pivot_table(index="date", columns="ticker", values="adj_close").sort_index()
        usd_cols = sorted(p.loc[p["currency"].eq("USD"), "ticker"].unique())
        if usd_cols:
            fx = self.fx[self.fx["pair"].eq("GBPUSD")].copy()
            fx["date"] = pd.to_datetime(fx["date"])
            rate = fx.set_index("date")["rate"].reindex(wide.index).ffill().bfill()
            wide[usd_cols] = wide[usd_cols].div(rate, axis=0)
        return wide.ffill()


def load_snapshot(path: Path) -> Snapshot:
    path = Path(path)
    if not (path / "prices_daily.parquet").exists():
        raise FileNotFoundError(
            f"No snapshot at {path}. Run `python scripts/make_synthetic_snapshot.py` (dev) "
            "or `python scripts/fetch_snapshot.py` (real data)."
        )
    prices = pd.read_parquet(path / "prices_daily.parquet")
    fx = pd.read_parquet(path / "fx_daily.parquet") if (path / "fx_daily.parquet").exists() else pd.DataFrame(
        columns=["date", "pair", "rate"]
    )

    def jsonl(name: str) -> list[dict]:
        f = path / name
        return [json.loads(line) for line in f.read_text().splitlines() if line.strip()] if f.exists() else []

    holdings = {row["etf"]: row["holdings"] for row in jsonl("etf_holdings.jsonl")}
    manifest = json.loads((path / "manifest.json").read_text()) if (path / "manifest.json").exists() else {}
    return Snapshot(
        prices=prices,
        fx=fx,
        news=[NewsItem.model_validate(r) for r in jsonl("news.jsonl")],
        filings=[Filing.model_validate(r) for r in jsonl("filings.jsonl")],
        earnings=jsonl("earnings.jsonl"),
        etf_holdings=holdings,
        manifest=manifest,
    )
