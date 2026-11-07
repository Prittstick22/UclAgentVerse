"""Alpaca market data (free plan: US stocks/ETFs, IEX feed, history since 2016). Owner: Jin."""
from __future__ import annotations

import httpx

BASE = "https://data.alpaca.markets/v2"


class Alpaca:
    def __init__(self, key_id: str, secret: str, timeout: float = 30):
        self.client = httpx.Client(
            timeout=timeout, headers={"APCA-API-KEY-ID": key_id, "APCA-API-SECRET-KEY": secret}
        )

    def daily_bars(self, symbols: list[str], start: str, end: str | None = None) -> dict:
        params = {"symbols": ",".join(symbols), "timeframe": "1Day", "start": start, "adjustment": "all",
                  "feed": "iex", "limit": 10000}
        if end:
            params["end"] = end
        r = self.client.get(f"{BASE}/stocks/bars", params=params)
        r.raise_for_status()
        return r.json().get("bars", {})

    def latest_quotes(self, symbols: list[str]) -> dict:
        r = self.client.get(f"{BASE}/stocks/quotes/latest", params={"symbols": ",".join(symbols), "feed": "iex"})
        r.raise_for_status()
        return r.json().get("quotes", {})
