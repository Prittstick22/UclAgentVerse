#!/usr/bin/env python3
"""Verify every external API works with our keys AND fits this project. Owner: Dev (#55). Not run in CI.

    cd backend
    python scripts/check_providers.py                 # everything whose key is set in .env
    python scripts/check_providers.py --only gemini,eodhd
    python scripts/check_providers.py --report ../provider-report.md   # markdown for the board (no secrets)

Call budget per full run: EODHD ~22 calls (free plan allows 20/day → use --eodhd-max 15 on the free plan),
Alpha Vantage 1 (of 25/day), Finnhub ~4, Alpaca 2, EDGAR 1, Gemini ~5 small requests.
"""
from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from app.config import catalogue_raw  # noqa: E402
from app.settings import get_settings  # noqa: E402

SIM_START = "2025-11-07"
HISTORY_START = "2023-01-02"


@dataclass
class Row:
    provider: str
    check: str
    status: str      # PASS | WARN | FAIL | SKIP
    detail: str


ROWS: list[Row] = []


def rec(provider: str, check: str, status: str, detail: str) -> None:
    ROWS.append(Row(provider, check, status, detail))
    icon = {"PASS": "✅", "WARN": "⚠️ ", "FAIL": "❌", "SKIP": "⏭️ "}[status]
    print(f"{icon} {provider:13} {check:38} {detail}")


def timed(fn):
    t = time.perf_counter()
    out = fn()
    return out, (time.perf_counter() - t) * 1000


# ----------------------------------------------------------------------------------------------- Gemini
def check_gemini(s) -> None:
    if not s.gemini_api_key:
        return rec("gemini", "key", "SKIP", "GEMINI_API_KEY not set")
    from google import genai
    from google.genai import types

    from app.agents.schemas import AgentStep

    client = genai.Client(api_key=s.gemini_api_key)

    class Pong(BaseModel):
        ok: bool
        model: str

    for label, model in [("deep", s.gemini_model_deep), ("fast", s.gemini_model_fast)]:
        if not model:
            rec("gemini", f"{label} model", "FAIL", "model ID not set in .env")
            continue
        try:
            resp, ms = timed(lambda m=model: client.models.generate_content(
                model=m, contents=f'Return ok=true and model="{m}".',
                config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=Pong)))
            tok = getattr(resp.usage_metadata, "total_token_count", "?")
            Pong.model_validate_json(resp.text)
            rec("gemini", f"{label} structured output ({model})", "PASS", f"{ms:.0f} ms, {tok} tokens")
        except Exception as e:
            rec("gemini", f"{label} structured output ({model})", "FAIL", str(e)[:160])

    try:  # our real agent schema must be accepted by Gemini's response_schema
        resp, ms = timed(lambda: client.models.generate_content(
            model=s.gemini_model_fast or s.gemini_model_deep,
            contents="You are a risk analyst. Ask to call tool correlation_lattice with args_json '{\"lookback\": 252}'.",
            config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=AgentStep)))
        step = AgentStep.model_validate_json(resp.text)
        rec("gemini", "AgentStep schema round-trip", "PASS" if step.tool_calls else "WARN",
            f"{ms:.0f} ms, tool_calls={[c.tool for c in step.tool_calls]}")
    except Exception as e:
        rec("gemini", "AgentStep schema round-trip", "FAIL", str(e)[:160])

    try:  # live mode only: Google Search grounding
        resp, ms = timed(lambda: client.models.generate_content(
            model=s.gemini_model_fast or s.gemini_model_deep, contents="What is the current Bank of England base rate?",
            config=types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())])))
        grounded = bool(resp.candidates and resp.candidates[0].grounding_metadata)
        rec("gemini", "Google Search grounding (live mode)", "PASS" if grounded else "WARN",
            f"{ms:.0f} ms, grounded={grounded}. Note: we call grounding WITHOUT response_schema")
    except Exception as e:
        rec("gemini", "Google Search grounding (live mode)", "WARN", f"not available: {str(e)[:120]}")


# ----------------------------------------------------------------------------------------------- EODHD
def check_eodhd(s, max_calls: int) -> None:
    if not s.eodhd_api_key:
        return rec("eodhd", "key", "SKIP", "EODHD_API_KEY not set")
    base, key = "https://eodhd.com/api", s.eodhd_api_key
    c = httpx.Client(timeout=30)
    calls = 0

    def get(path, **params):
        nonlocal calls
        calls += 1
        return c.get(f"{base}{path}", params={"api_token": key, "fmt": "json", **params})

    r, ms = timed(lambda: get("/eod/VWRP.LSE", **{"from": (date.today() - timedelta(days=14)).isoformat()}))
    if r.status_code != 200:
        return rec("eodhd", "auth (VWRP.LSE recent)", "FAIL", f"HTTP {r.status_code}: {r.text[:120]}")
    rec("eodhd", "auth (VWRP.LSE recent)", "PASS", f"{ms:.0f} ms, {len(r.json())} bars")

    # LSE symbol list: currency (GBX vs GBP) + ISINs for the catalogue (#5)
    r = get("/exchange-symbol-list/LSE")
    units: dict[str, str] = {}
    if r.status_code == 200:
        listing = {x["Code"]: x for x in r.json()}
        for inst in catalogue_raw():
            if inst["ticker"].endswith(".LSE"):
                row = listing.get(inst["ticker"].split(".")[0])
                if row:
                    units[inst["ticker"]] = row.get("Currency", "?")
                    ok = row.get("Currency") == inst["quote_unit"]
                    rec("eodhd", f"LSE unit/ISIN {inst['ticker']}", "PASS" if ok else "WARN",
                        f"currency={row.get('Currency')} (catalogue says {inst['quote_unit']}), isin={row.get('Isin')}")
                else:
                    rec("eodhd", f"LSE listing {inst['ticker']}", "FAIL", "not in EODHD's LSE symbol list")
    else:
        rec("eodhd", "LSE symbol list", "WARN", f"HTTP {r.status_code} (may need the paid plan)")

    # coverage + history depth per catalogue ticker (bounded by --eodhd-max)
    tickers = [i["ticker"] for i in catalogue_raw()] + ["GBPUSD.FOREX"]
    for t in tickers:
        if calls >= max_calls:
            rec("eodhd", f"coverage {t}", "SKIP", f"call budget {max_calls} reached (rerun tomorrow / after paying)")
            continue
        r = get(f"/eod/{t}", **{"from": HISTORY_START})
        if r.status_code != 200 or not isinstance(r.json(), list) or not r.json():
            rec("eodhd", f"coverage {t}", "FAIL", f"HTTP {r.status_code}: {r.text[:80]}")
            continue
        bars = r.json()
        first, last = bars[0]["date"], bars[-1]["date"]
        if first <= "2023-01-31":
            rec("eodhd", f"coverage {t}", "PASS", f"{len(bars)} bars {first} → {last}")
        elif first <= SIM_START:
            rec("eodhd", f"coverage {t}", "WARN",
                f"history only from {first} (free plan gives ~1 year; recheck after paying; need 2023-01 for lookback)")
        else:
            rec("eodhd", f"coverage {t}", "FAIL", f"starts {first}, after the sim start")

    r = get("/real-time/VWRP.LSE", s="AAPL.US")
    rec("eodhd", "live (15-min delayed) quotes", "PASS" if r.status_code == 200 and "close" in r.text else "WARN",
        f"HTTP {r.status_code}. If not included, live mode shows last close with its date")
    rec("eodhd", "calls used this run", "PASS" if calls <= 20 else "WARN", f"{calls} (free plan: 20/day)")


# ----------------------------------------------------------------------------------------------- Finnhub
def check_finnhub(s) -> None:
    if not s.finnhub_api_key:
        return rec("finnhub", "key", "SKIP", "FINNHUB_API_KEY not set")
    c = httpx.Client(timeout=30, headers={"X-Finnhub-Token": s.finnhub_api_key})
    r, ms = timed(lambda: c.get("https://finnhub.io/api/v1/company-news",
                                params={"symbol": "AAPL", "from": "2025-11-07", "to": "2025-11-30"}))
    if r.status_code != 200:
        return rec("finnhub", "company news AAPL Nov 2025", "FAIL", f"HTTP {r.status_code}: {r.text[:100]}")
    items = r.json()
    rec("finnhub", "company news AAPL Nov 2025 (history)", "PASS" if items else "FAIL",
        f"{ms:.0f} ms, {len(items)} items; remaining/min={r.headers.get('X-Ratelimit-Remaining', '?')}")
    recent = c.get("https://finnhub.io/api/v1/company-news",
                   params={"symbol": "NVDA", "from": (date.today() - timedelta(days=7)).isoformat(),
                           "to": date.today().isoformat()})
    rec("finnhub", "company news NVDA last 7 days (live)", "PASS" if recent.ok and recent.json() else "WARN",
        f"{len(recent.json()) if recent.ok else recent.status_code} items")
    uk = c.get("https://finnhub.io/api/v1/company-news", params={"symbol": "AZN.L", "from": "2026-01-01",
                                                                  "to": "2026-01-31"})
    rec("finnhub", "UK company news (AZN.L)", "PASS" if uk.ok and uk.json() else "WARN",
        "free tier is mostly North American → curate UK hero items by hand (docs/06 §6)")
    e = c.get("https://finnhub.io/api/v1/calendar/earnings", params={"from": "2026-04-01", "to": "2026-05-31",
                                                                    "symbol": "AAPL"})
    rec("finnhub", "earnings calendar", "PASS" if e.ok and e.json().get("earningsCalendar") else "WARN",
        f"HTTP {e.status_code}")


# ----------------------------------------------------------------------------------------------- Alpha Vantage
def check_alphavantage(s) -> None:
    if not s.alphavantage_api_key:
        return rec("alphavantage", "key", "SKIP", "ALPHAVANTAGE_API_KEY not set")
    r, ms = timed(lambda: httpx.get("https://www.alphavantage.co/query", timeout=30, params={
        "function": "NEWS_SENTIMENT", "tickers": "NVDA", "time_from": "20260401T0000", "time_to": "20260531T2359",
        "limit": 50, "apikey": s.alphavantage_api_key}))
    body = r.json() if r.ok else {}
    feed = body.get("feed", [])
    if "Information" in body or "Note" in body:
        return rec("alphavantage", "NEWS_SENTIMENT NVDA Apr–May 2026", "FAIL", (body.get("Information") or body.get("Note"))[:140])
    rec("alphavantage", "NEWS_SENTIMENT NVDA Apr–May 2026", "PASS" if feed else "WARN",
        f"{ms:.0f} ms, {len(feed)} items (1 of 25 daily requests used)")


# ----------------------------------------------------------------------------------------------- Alpaca
def check_alpaca(s) -> None:
    if not (s.alpaca_key_id and s.alpaca_secret_key):
        return rec("alpaca", "key", "SKIP", "ALPACA_KEY_ID / ALPACA_SECRET_KEY not set (optional: live US quotes)")
    h = {"APCA-API-KEY-ID": s.alpaca_key_id, "APCA-API-SECRET-KEY": s.alpaca_secret_key}
    q = httpx.get("https://data.alpaca.markets/v2/stocks/quotes/latest", params={"symbols": "AAPL,MSFT", "feed": "iex"},
                  headers=h, timeout=30)
    rec("alpaca", "latest quotes AAPL,MSFT (IEX)", "PASS" if q.ok and q.json().get("quotes") else "FAIL",
        f"HTTP {q.status_code}")
    b = httpx.get("https://data.alpaca.markets/v2/stocks/bars", headers=h, timeout=30, params={
        "symbols": "AAPL", "timeframe": "1Day", "start": HISTORY_START, "adjustment": "all", "feed": "iex", "limit": 1})
    rec("alpaca", "daily bars from 2023 (backup history)", "PASS" if b.ok else "WARN", f"HTTP {b.status_code}")


# ----------------------------------------------------------------------------------------------- EDGAR
def check_edgar(s) -> None:
    ua = s.edgar_user_agent
    if "set EDGAR_USER_AGENT" in ua or "@" not in ua:
        rec("edgar", "user agent", "WARN", "set EDGAR_USER_AGENT='UclAgentVerse team <email>' (SEC asks for a contact)")
    r, ms = timed(lambda: httpx.get("https://data.sec.gov/submissions/CIK0000320193.json",
                                    headers={"User-Agent": ua}, timeout=30))
    if not r.ok:
        return rec("edgar", "submissions (Apple)", "FAIL", f"HTTP {r.status_code}")
    recent = r.json()["filings"]["recent"]
    forms = [(f, a) for f, a in zip(recent["form"], recent["acceptanceDateTime"]) if f in ("10-K", "10-Q", "8-K")]
    in_sim = [f for f in forms if f[1] >= SIM_START]
    rec("edgar", "submissions (Apple)", "PASS" if in_sim else "WARN",
        f"{ms:.0f} ms, {len(in_sim)} 10-K/10-Q/8-K since {SIM_START}; acceptanceDateTime present → available_at")


# ----------------------------------------------------------------------------------------------- main
FIT = """
## Does it fit the project? (read with the table above)
| Need | Provider | Pass condition |
|---|---|---|
| Daily prices for every catalogue ticker from 2023-01 | EODHD (paid) | all `coverage` rows PASS after paying (WARN on free plan is expected) |
| Correct GBX/GBP units + ISINs | EODHD symbol list | `LSE unit/ISIN` rows match the catalogue (fix catalogue in #5 otherwise) |
| GBPUSD FX | EODHD | `coverage GBPUSD.FOREX` PASS |
| Dated US company news Nov 2025 → now | Finnhub (+ Alpha Vantage for hero events) | news history + live rows PASS |
| UK news | — | expected WARN → hand-curate hero UK items (labelled `curated`) |
| Filings with timestamps | EDGAR | PASS |
| Agents: structured JSON on both models | Gemini | both structured-output rows + AgentStep PASS |
| Live news context (live mode only) | Gemini grounding | PASS or WARN (WARN → live mode uses Finnhub only) |
| Live prices (optional) | EODHD live / Alpaca | PASS or WARN (WARN → show last close + date) |
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="gemini,eodhd,finnhub,alphavantage,alpaca,edgar")
    ap.add_argument("--eodhd-max", type=int, default=22, help="max EODHD calls (free plan: 20/day → use 15)")
    ap.add_argument("--report", help="write a markdown report (no secrets) to this path")
    a = ap.parse_args()
    s = get_settings()
    only = set(a.only.split(","))
    print("Checking providers (keys are read from .env and never printed)\n")
    checks = {"gemini": lambda: check_gemini(s), "eodhd": lambda: check_eodhd(s, a.eodhd_max),
              "finnhub": lambda: check_finnhub(s), "alphavantage": lambda: check_alphavantage(s),
              "alpaca": lambda: check_alpaca(s), "edgar": lambda: check_edgar(s)}
    for name, fn in checks.items():
        if name in only:
            try:
                fn()
            except Exception as e:  # network errors etc.
                rec(name, "run", "FAIL", f"{type(e).__name__}: {str(e)[:140]}")
    counts = {k: sum(r.status == k for r in ROWS) for k in ("PASS", "WARN", "FAIL", "SKIP")}
    print(f"\n{counts}")
    print(FIT)
    if a.report:
        lines = [f"# Provider check · {date.today()}", "", f"Summary: {counts}", "", "| Provider | Check | Status | Detail |",
                 "|---|---|---|---|"] + [f"| {r.provider} | {r.check} | {r.status} | {r.detail.replace('|', '/')} |" for r in ROWS]
        Path(a.report).write_text("\n".join(lines) + "\n" + FIT)
        print(f"Report written to {a.report}. Post it: python ../scripts/board.py new --from dev --to all --type fyi "
              f"--title 'Provider check results' --body - < {a.report}")
    sys.exit(1 if counts["FAIL"] else 0)


if __name__ == "__main__":
    main()
