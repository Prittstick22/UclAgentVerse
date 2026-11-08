"""DataGateway: the ONLY way business logic reads data. Enforces as_of (the clock is the firewall).

Historical mode: everything comes from the snapshot, revealed up to clock.now().
Live mode: same snapshot + daily top-up appended by app.data.live (TODO, issue: live mode).
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd

from app.config import catalogue_raw, params
from app.core.clock import Clock
from app.core.events import EventBus
from app.data.models import Filing, Freshness, NewsItem
from app.data.snapshot import Snapshot
from app.schemas import Instrument


class AsOfViolation(Exception):
    """Raised when anything asks for data after the clock's now()."""


class DataGateway:
    def __init__(self, clock: Clock, snapshot: Snapshot, events: EventBus | None = None):
        self.clock = clock
        self.snapshot = snapshot
        self.events = events
        self._prices_gbp = snapshot.adj_close_gbp()

    # ------------------------------------------------------------------ guards
    def _check_end(self, end: str | pd.Timestamp | None, caller: str) -> pd.Timestamp:
        today = pd.Timestamp(self.clock.today())
        if end is None:
            return today
        end_ts = pd.Timestamp(end)
        if end_ts > today:
            if self.events:
                self.events.emit(
                    "asof.violation",
                    title=f"Refused future data request from {caller}",
                    status="denied",
                    payload={"requested_end": str(end_ts.date()), "as_of": str(today.date()), "caller": caller},
                )
            raise AsOfViolation(f"{caller} requested data to {end_ts.date()} but as_of is {today.date()}")
        return end_ts

    # ------------------------------------------------------------------ prices
    def prices(self, tickers: list[str] | None = None, start: str | None = None, end: str | None = None,
               caller: str = "unknown") -> pd.DataFrame:
        """Adjusted close in GBP, wide (date × ticker), rows dated <= as_of."""
        end_ts = self._check_end(end, caller)
        df = self._prices_gbp.loc[:end_ts]
        if start is not None:
            df = df.loc[pd.Timestamp(start):]
        if tickers is not None:
            missing = [t for t in tickers if t not in df.columns]
            if missing:
                raise KeyError(f"No price data for {missing}")
            df = df[tickers]
        return df

    def latest_prices(self, tickers: list[str] | None = None) -> pd.Series:
        return self.prices(tickers, caller="latest_prices").ffill().iloc[-1]

    def last_quote_dates(self, tickers: list[str], end: str | None = None) -> dict[str, str]:
        """Last observed quote dates, before the adjusted price panel fills missing quotes."""
        cutoff = self._check_end(end, "last_quote_dates")
        rows = self.snapshot.prices
        dates = pd.to_datetime(rows["date"])
        closes = rows["adj_close"]
        visible = rows["ticker"].isin(tickers) & dates.le(cutoff) & closes.gt(0) & closes.lt(float("inf"))
        observed = dates[visible].groupby(rows.loc[visible, "ticker"]).max()
        return {ticker: day.date().isoformat() for ticker, day in observed.items()}

    def fx(self, pair: str = "GBPUSD", start: str | None = None, end: str | None = None) -> pd.Series:
        end_ts = self._check_end(end, "fx")
        fx = self.snapshot.fx[self.snapshot.fx["pair"].eq(pair)].copy()
        fx["date"] = pd.to_datetime(fx["date"])
        s = fx.set_index("date")["rate"].sort_index().loc[:end_ts]
        return s.loc[pd.Timestamp(start):] if start else s

    def trading_days(self, start: str, end: str | None = None) -> list[pd.Timestamp]:
        """Trading calendar from snapshot dates. NOTE: not as_of-limited (calendar is public knowledge)."""
        idx = self._prices_gbp.index
        idx = idx[idx >= pd.Timestamp(start)]
        if end:
            idx = idx[idx <= pd.Timestamp(end)]
        return list(idx)

    # ------------------------------------------------------------------ text
    def _now_iso(self) -> str:
        return self.clock.now().isoformat()

    def news(self, tickers: list[str] | None = None, since: str | None = None, until: str | None = None,
             caller: str = "unknown") -> list[NewsItem]:
        now = self.clock.now()
        if until is not None:
            self._check_end(until[:10], caller)
        out = []
        for n in self.snapshot.news:
            avail = datetime.fromisoformat(n.available_at)
            if avail > now:
                continue
            if since and n.available_at < since:
                continue
            if tickers and not set(tickers) & set(n.tickers):
                continue
            out.append(n)
        return out

    def filings(self, ticker: str | None = None, since: str | None = None, caller: str = "unknown") -> list[Filing]:
        now = self.clock.now()
        return [
            f for f in self.snapshot.filings
            if datetime.fromisoformat(f.available_at) <= now
            and (ticker is None or f.ticker == ticker)
            and (since is None or f.available_at >= since)
        ]

    def earnings(self, tickers: list[str] | None = None, caller: str = "unknown") -> list[dict]:
        """Earnings dates up to as_of only (strict firewall: no upcoming dates in historical mode)."""
        today = self.clock.as_of_str()
        return [
            r for r in self.snapshot.earnings
            if str(r.get("date", ""))[:10] <= today and (not tickers or r.get("ticker") in tickers)
        ]

    # ------------------------------------------------------------------ reference
    def catalogue(self, eligible_only: bool = True) -> list[Instrument]:
        out = []
        for row in catalogue_raw():
            inst = Instrument.model_validate({**row, "data_source": self.snapshot.source_label})
            if history := row.get("ocf_history"):
                visible = [entry for entry in history if entry["effective_from"] <= self.clock.as_of_str()]
                if not visible:
                    raise AsOfViolation(f"No verified OCF for {inst.ticker} at {self.clock.as_of_str()}")
                inst.ocf = max(visible, key=lambda entry: entry["effective_from"])["ocf"]
            if inst.ticker not in self._prices_gbp.columns:
                inst.eligible = False
            if not eligible_only or inst.eligible:
                out.append(inst)
        return out

    def etf_holdings(self, etf: str) -> list[dict]:
        return self.snapshot.etf_holdings.get(etf, [])

    def freshness(self) -> dict[str, Freshness]:
        visible = self.prices(caller="freshness")
        stale_after = params()["risk"]["stale_after_days"]
        out: dict[str, Freshness] = {}
        last_row = len(visible.index) - 1
        for t in visible.columns:
            valid = visible[t].dropna()
            last = valid.index[-1] if len(valid) else None
            lag = last_row - visible.index.get_loc(last) if last is not None else 999
            out[t] = Freshness(
                ticker=t, last_date=str(last.date()) if last is not None else None,
                stale=lag > stale_after, source=self.snapshot.source_label,
            )
        return out
