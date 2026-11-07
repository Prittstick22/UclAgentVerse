"""Finnhub adapter (free tier, ~60 calls/min). Company news + earnings calendar. Owner: Jin."""
from __future__ import annotations

import httpx

BASE = "https://finnhub.io/api/v1"


class Finnhub:
    def __init__(self, api_key: str, timeout: float = 30):
        self.client = httpx.Client(timeout=timeout, headers={"X-Finnhub-Token": api_key})

    def company_news(self, symbol: str, start: str, end: str) -> list[dict]:
        """symbol is the plain US ticker (AAPL). Returns [{datetime(unix), headline, summary, url, source, id}]."""
        r = self.client.get(f"{BASE}/company-news", params={"symbol": symbol, "from": start, "to": end})
        r.raise_for_status()
        return r.json()

    def earnings_calendar(self, start: str, end: str, symbol: str | None = None) -> list[dict]:
        params = {"from": start, "to": end}
        if symbol:
            params["symbol"] = symbol
        r = self.client.get(f"{BASE}/calendar/earnings", params=params)
        r.raise_for_status()
        return r.json().get("earningsCalendar", [])
