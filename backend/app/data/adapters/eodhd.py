"""EODHD adapter (paid EOD plan). Used by scripts/fetch_snapshot.py and live top-up. Owner: Jin.

Docs: https://eodhd.com/financial-apis/  Tickers look like VWRP.LSE, AAPL.US, GBPUSD.FOREX.
Live (15-min delayed) quotes: /api/real-time/{first}?s=T2,T3 (each symbol = 1 call; 15-20 per request).
"""
from __future__ import annotations

import httpx

BASE = "https://eodhd.com/api"


class EODHD:
    def __init__(self, api_key: str, timeout: float = 30):
        self.key = api_key
        self.client = httpx.Client(timeout=timeout)

    def eod(self, ticker: str, start: str, end: str | None = None) -> list[dict]:
        """Daily bars: [{date, open, high, low, close, adjusted_close, volume}]."""
        params = {"api_token": self.key, "fmt": "json", "from": start, "period": "d"}
        if end:
            params["to"] = end
        r = self.client.get(f"{BASE}/eod/{ticker}", params=params)
        r.raise_for_status()
        return r.json()

    def news(self, symbol: str, start: str, end: str, limit: int = 1000, offset: int = 0) -> list[dict]:
        """Dated company news; paginate with limit/offset."""
        r = self.client.get(f"{BASE}/news", params={
            "s": symbol, "from": start, "to": end, "limit": limit, "offset": offset,
            "api_token": self.key, "fmt": "json",
        })
        r.raise_for_status()
        return r.json()

    def live(self, tickers: list[str]) -> list[dict]:
        """Delayed quotes for up to ~20 tickers. TODO(jin): confirm the $19.99 plan includes this endpoint."""
        first, rest = tickers[0], tickers[1:]
        params = {"api_token": self.key, "fmt": "json"}
        if rest:
            params["s"] = ",".join(rest)
        r = self.client.get(f"{BASE}/real-time/{first}", params=params)
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else [data]
