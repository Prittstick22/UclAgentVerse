"""Background-only refresh of the live cache. No trades and no LLM calls."""
from __future__ import annotations

import hashlib
import json
import threading
import uuid
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import httpx
import pandas as pd

from app.agents.guard import scan
from app.core.clock import LONDON
from app.data.adapters.eodhd import EODHD
from app.data.adapters.finnhub import Finnhub
from app.data.models import NewsItem

if TYPE_CHECKING:
    from app.container import AppState


class LiveUpdates:
    """One worker per live namespace; retries deduplicate rows and daily calls cap at 99."""

    def __init__(self, state: AppState):
        self.state = state
        self.lock = threading.Lock()
        self.kind = "eod"
        self.failures = {kind: set(json.loads(state.db.get("live_coverage", kind) or "[]"))
                         for kind in ("eod", "news")}
        self._sync_failures()

    def _sync_failures(self) -> None:
        self.state.gw.coverage_failures = set().union(*self.failures.values())
        for kind, tickers in self.failures.items():
            self.state.db.put("live_coverage", kind, json.dumps(sorted(tickers)))

    def _clear(self, ticker: str) -> None:
        self.failures[self.kind].discard(ticker)
        self._sync_failures()

    def _call(self, provider: str, ticker: str, fn, *args):
        state = self.state
        day = state.clock.as_of_str()
        used = int(state.db.get("live_provider_calls", day) or "0")
        if used >= 99:
            raise RuntimeError("Daily provider-call cap reached")
        state.db.put("live_provider_calls", day, str(used + 1))
        state.events.emit("tool.call", title="Live cache provider request", status="running",
                          payload={"tool": "live_refresh", "args": {"provider": provider, "ticker": ticker}})
        try:
            result = fn(*args)
        except (httpx.HTTPError, OSError, ValueError, KeyError, TypeError, RuntimeError, OverflowError):
            state.events.emit("tool.result", title="Live cache request failed", status="failed",
                              payload={"tool": "live_refresh", "ok": False, "summary": "Provider unavailable"})
            raise
        state.events.emit("tool.result", title="Live cache request complete", status="ok",
                          payload={"tool": "live_refresh", "ok": True, "summary": "Cache response received",
                                   "provider_calls_today": used + 1})
        return result

    def refresh(self, kind: str) -> dict:
        state = self.state
        if state.clock.mode != "live":
            raise ValueError("Live refresh requires a live namespace")
        if not self.lock.acquire(blocking=False):
            return {"ok": True, "fetched": 0, "stale": []}
        try:
            self.kind = kind
            return self._eod() if kind == "eod" else self._news()
        except (httpx.HTTPError, OSError, ValueError, KeyError, TypeError, RuntimeError, OverflowError):
            # Never include exception text: provider URLs can contain secrets.
            tickers = list(state.ledger.positions) or [i.ticker for i in state.gw.catalogue()]
            self._failure(tickers)
            return {"ok": False, "fetched": 0, "stale": tickers}
        finally:
            self.lock.release()

    def _failure(self, tickers: list[str]) -> None:
        state = self.state
        self.failures[self.kind].update(tickers)
        self._sync_failures()
        identity = f"coverage_{uuid.uuid4().hex}"
        notification = {"id": identity, "kind": "coverage", "title": "Monitoring degraded",
                        "body": "Refresh failed; retained the last cached values. Price dates remain visible.",
                        "proposal_id": None, "run_id": None,
                        "created_at": state.clock.now().isoformat(), "read": False}
        state.db.put("notifications", identity, json.dumps(notification))
        state.events.emit("notification.created", title="Monitoring degraded", status="failed",
                          payload={"notification_id": identity, "kind": "coverage"})

    def _eod(self) -> dict:
        state = self.state
        if not state.settings.eodhd_api_key:
            raise RuntimeError("Missing provider configuration")
        now = state.clock.now().astimezone(LONDON)
        day = now.date()
        if day.weekday() >= 5:
            return {"ok": True, "fetched": 0, "stale": []}
        old = state.gw.snapshot
        updated = deepcopy(old)
        frames = [old.prices]
        failed, succeeded = [], []
        provider = EODHD(state.settings.eodhd_api_key)
        fetched = 0
        try:
            for inst in state.gw.catalogue(eligible_only=False):
                # Do not ask for an unfinished US or UK close.
                close_hour = 21.5 if inst.ticker.endswith(".US") else 17
                if now.hour + now.minute / 60 < close_hour:
                    continue
                key = f"{day}:{inst.ticker}"
                if state.db.get("live_eod_done", key):
                    continue
                try:
                    raw = self._call("eodhd", inst.ticker, provider.eod, inst.ticker,
                                     (day - timedelta(days=7)).isoformat(), day.isoformat())
                    rows = pd.DataFrame(raw).rename(columns={"adjusted_close": "adj_close"})
                    dates = pd.to_datetime(rows["date"])
                    rows = rows.loc[dates.le(pd.Timestamp(day))].copy()
                    values = rows[["open", "high", "low", "close", "adj_close"]].astype(float)
                    if rows.empty or not values.map(lambda x: 0 < x < float("inf")).all().all():
                        raise ValueError("Invalid bars")
                    rows = rows.assign(ticker=inst.ticker, currency=inst.currency,
                                       quote_unit=inst.quote_unit, source="eodhd")
                    frames.append(rows)
                    fetched += len(rows)
                    succeeded.append((inst.ticker, key, str(rows["date"].max())[:10] == day.isoformat()))
                except (httpx.HTTPError, ValueError, KeyError, TypeError, RuntimeError, OverflowError):
                    failed.append(inst.ticker)
            fx_key = f"{day}:GBPUSD"
            if now.hour >= 17 and not state.db.get("live_eod_done", fx_key):
                try:
                    rows = self._call("eodhd", "GBPUSD.FOREX", provider.eod, "GBPUSD.FOREX",
                                      (day - timedelta(days=7)).isoformat(), day.isoformat())
                    fx = pd.DataFrame(rows).rename(columns={"close": "rate"})
                    fx = fx.loc[pd.to_datetime(fx["date"]).le(pd.Timestamp(day))].copy()
                    if fx.empty or not fx["rate"].map(lambda x: 0 < float(x) < float("inf")).all():
                        raise ValueError("Invalid FX")
                    fx = fx.assign(pair="GBPUSD", source="eodhd")[["date", "pair", "rate", "source"]]
                    updated.fx = pd.concat([old.fx, fx], ignore_index=True).drop_duplicates(["date", "pair"], keep="last")
                    succeeded.append(("GBPUSD", fx_key, str(fx["date"].max())[:10] == day.isoformat()))
                except (httpx.HTTPError, ValueError, KeyError, TypeError, RuntimeError, OverflowError):
                    failed.extend(i.ticker for i in state.gw.catalogue() if i.currency == "USD")
        finally:
            provider.client.close()
        updated.prices = pd.concat(frames, ignore_index=True).drop_duplicates(["date", "ticker"], keep="last")
        label = ("synthetic+eodhd" if "synthetic" in old.source_label else "eodhd") if succeeded else old.source_label
        updated.manifest = {**old.manifest, "label": label}
        updated.manifest["live_updated_at"] = state.clock.now().isoformat()
        self._publish(updated)
        for ticker, key, complete in succeeded:
            if complete:
                state.db.put("live_eod_done", key, "true")
                self._clear(ticker)
            else:
                failed.append(ticker)
        if failed:
            self._failure(sorted(set(failed)))
        state.ledger.mark_to_market(state.gw.latest_prices().to_dict())
        return {"ok": not failed, "fetched": fetched, "stale": sorted(set(failed))}

    def _news(self) -> dict:
        state = self.state
        holdings = [t for t, p in state.ledger.positions.items() if p.units > 0]
        if not holdings:
            return {"ok": True, "fetched": 0, "stale": []}
        now = state.clock.now()
        bucket = now.strftime("%Y-%m-%dT%H")
        items = {n.id: n for n in state.gw.snapshot.news}
        failed, completed = [], []
        added = 0
        for ticker in holdings:
            key = f"{bucket}:{ticker}"
            if state.db.get("live_news_done", key):
                continue
            provider = None
            try:
                first, last = (now.date() - timedelta(days=1)).isoformat(), now.date().isoformat()
                if ticker.endswith(".US"):
                    if not state.settings.finnhub_api_key:
                        raise RuntimeError("Missing provider configuration")
                    provider = Finnhub(state.settings.finnhub_api_key)
                    raw = self._call("finnhub", ticker, provider.company_news, ticker.removesuffix(".US"), first, last)
                    source = "finnhub"
                else:
                    if not state.settings.eodhd_api_key:
                        raise RuntimeError("Missing provider configuration")
                    provider = EODHD(state.settings.eodhd_api_key)
                    raw = self._call("eodhd", ticker, provider.news, ticker, first, last)
                    source = "eodhd"
                for row in raw:
                    stamp = (datetime.fromtimestamp(row["datetime"], UTC) if source == "finnhub"
                             else datetime.fromisoformat(row["date"]))
                    if stamp.tzinfo is None or stamp > now or stamp.date().isoformat() < first:
                        continue
                    title = row.get("headline", "") if source == "finnhub" else row.get("title", "")
                    text = row.get("summary", "") if source == "finnhub" else row.get("content", "")
                    url = row.get("url") if source == "finnhub" else row.get("link")
                    identity = "news_" + source + "_" + hashlib.sha256(
                        (url or f"{ticker}|{stamp.isoformat()}|{title}").encode()
                    ).hexdigest()[:20]
                    if identity in items:
                        previous = items[identity].model_copy(deep=True)
                        previous.tickers = sorted(set(previous.tickers + [ticker]))
                        items[identity] = previous
                        continue
                    if scan(title + " " + text):
                        state.events.emit("content.quarantined", title="Quarantined live news", evidence_ids=[identity],
                                          payload={"evidence_id": identity, "reason": "instruction-like content"})
                        continue
                    items[identity] = NewsItem(id=identity, tickers=[ticker], headline=title, summary=text, url=url,
                                              source=source, published_at=stamp.isoformat(), available_at=stamp.isoformat())
                    added += 1
                completed.append((key, ticker))
            except (httpx.HTTPError, ValueError, KeyError, TypeError, RuntimeError, OverflowError):
                failed.append(ticker)
            finally:
                if provider is not None:
                    provider.client.close()
        updated = deepcopy(state.gw.snapshot)
        updated.news = list(items.values())
        self._publish(updated)
        for key, ticker in completed:
            state.db.put("live_news_done", key, "true")
            self._clear(ticker)
        if failed:
            self._failure(failed)
        return {"ok": not failed, "fetched": added, "stale": failed}

    def _publish(self, snapshot) -> None:
        """Write in the isolated live directory, then publish to the live gateway."""
        directory = self.state.settings.snapshot_dir / "live"
        directory.mkdir(parents=True, exist_ok=True)
        # Per-file atomic replacement prevents readers loading a partial Parquet file.
        for name, frame in (("prices_daily.parquet", snapshot.prices), ("fx_daily.parquet", snapshot.fx)):
            temporary = directory / (name + ".tmp")
            frame.to_parquet(temporary, index=False)
            temporary.replace(directory / name)
        for name, value in (("manifest.json", json.dumps(snapshot.manifest)),
                            ("news.jsonl", "".join(n.model_dump_json() + "\n" for n in snapshot.news))):
            temporary = directory / (name + ".tmp")
            temporary.write_text(value, encoding="utf-8")
            temporary.replace(directory / name)
        for name, rows in (("filings.jsonl", [f.model_dump() for f in snapshot.filings]),
                           ("earnings.jsonl", snapshot.earnings),
                           ("etf_holdings.jsonl", [{"etf": ticker, "holdings": rows}
                                                   for ticker, rows in snapshot.etf_holdings.items()])):
            temporary = directory / (name + ".tmp")
            temporary.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            temporary.replace(directory / name)
        self.state.gw.replace_snapshot(snapshot)


def updates(state: AppState) -> LiveUpdates:
    if state.live_updates is None:
        state.live_updates = LiveUpdates(state)
    return state.live_updates


def live_portfolio(state: AppState):
    """Use deterministic ledger figures and the gateway's real bar dates."""
    from app.schemas import Holding, Portfolio

    ledger = state.ledger
    ledger.mark_to_market(state.gw.latest_prices().to_dict())
    freshness = state.gw.freshness()
    weights = ledger.weights()
    rows = []
    for row in ledger.pnl_rows():
        ticker = row["ticker"]
        if row["units"] <= 0:
            continue
        info = freshness[ticker]
        instrument = ledger.catalogue[ticker]
        rows.append(Holding(**row, name=instrument.name, asset_class=instrument.asset_class,
                            price_gbp=ledger.last_prices.get(ticker, 0), weight=weights.get(ticker, 0),
                            target_weight=weights.get(ticker, 0), price_as_of=info.last_date or "unknown",
                            stale=info.stale))
    nav = ledger.nav()
    degraded = bool(state.gw.coverage_failures) or any(f.stale for f in freshness.values())
    return Portfolio(mode="live", as_of=state.clock.as_of_str(), nav_gbp=nav, cash_gbp=ledger.cash_gbp,
                     invested_gbp=nav - ledger.cash_gbp, contributions_gbp=ledger.contributions_gbp,
                     total_return=0.0,  # TODO(#21): consume the engine's persisted return series, not a cash-flow proxy.
                     status="monitoring_degraded" if degraded else "monitoring_normally", holdings=rows)
