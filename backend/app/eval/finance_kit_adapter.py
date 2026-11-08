"""Adapter for the organisers' AgentVerse finance kit (#61). Owner: Dev. Spec: docs/finance-kit.md.

    cd backend && python -m app.eval.finance_kit_adapter

Protocol: one JSON request per line on stdin, one JSON response per line on stdout (flushed). Logs go to stderr only.
Only `market_step` is our product; other tasks get {"error": "unsupported_task"} (we ask organisers to run the
`markets` / `real-markets` packs).

The strategy is our product's risk discipline applied to a single asset, decided ONLY from the price history the
runner has shown so far (no look-ahead, no LLM: answers must take milliseconds). All constants were fixed before
any challenge run and are never tuned on challenge results:
- stay invested by default (a long-term investor; we buy at the first step);
- step aside to cash if the price is DRAWDOWN_EXIT below its recent peak (last PEAK_WINDOW bars), or if recent
  volatility (last VOL_WINDOW returns) is more than VOL_EXIT times its normal level (the returns before that);
- re-enter when volatility has calmed (< VOL_REENTER x long-run), the price is above its VOL_WINDOW-bar average,
  and it is no longer in a DRAWDOWN_EXIT drawdown.
"""
from __future__ import annotations

import json
import logging
import sys

import numpy as np

DRAWDOWN_EXIT = 0.15      # same order as the quiz's "£10,000 falls to £8,000" loss question
PEAK_WINDOW = 60          # recent peak, so a long decline can't lock us out forever
VOL_WINDOW = 20
VOL_EXIT = 2.0
VOL_REENTER = 1.5
MIN_VOL_OBS = 2 * VOL_WINDOW   # need this many returns before the volatility test means anything

log = logging.getLogger("finance_kit_adapter")


def signals(prices: list[float]) -> dict:
    """Risk measures from the observed prices only."""
    p = np.asarray(prices, dtype=float)
    peak = float(p[-PEAK_WINDOW:].max())
    drawdown = float(p[-1] / peak - 1.0) if peak > 0 else 0.0
    out = {"drawdown": drawdown, "vol_ratio": None, "above_avg": bool(p[-1] >= p[-VOL_WINDOW:].mean())}
    if len(p) > MIN_VOL_OBS and (p > 0).all():
        r = np.diff(np.log(p))
        long_vol = float(r[:-VOL_WINDOW].std())     # the normal level = before the recent window
        if long_vol > 0:
            out["vol_ratio"] = float(r[-VOL_WINDOW:].std()) / long_vol
    return out


def decide(inp: dict) -> str:
    history = inp["history"]
    prices = [float(h["price_pence"]) for h in history]
    if not prices or any(x <= 0 for x in prices):
        raise ValueError("prices must be positive")
    shares, cash, fee = int(inp.get("shares", 0)), int(inp.get("cash_pence", 0)), int(inp.get("fee_pence", 0))
    s = signals(prices)
    stressed = s["drawdown"] <= -DRAWDOWN_EXIT or (s["vol_ratio"] is not None and s["vol_ratio"] > VOL_EXIT)
    if shares > 0:
        return "sell" if stressed else "hold"
    can_buy = cash - fee >= prices[-1]
    if not can_buy:
        return "hold"
    if len(prices) == 1:
        return "buy"                         # invest from the start, like the product
    calm = s["vol_ratio"] is None or s["vol_ratio"] < VOL_REENTER
    return "buy" if (not stressed and calm and s["above_avg"]) else "hold"


def solve(request: dict) -> dict:
    if request.get("task") != "market_step":
        return {"error": "unsupported_task"}
    try:
        return {"action": decide(request["input"])}
    except (KeyError, TypeError, ValueError):
        return {"error": "invalid_input"}


def main() -> None:
    logging.basicConfig(stream=sys.stderr, level=logging.INFO)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            output = solve(request)
            rid = request.get("request_id")
        except json.JSONDecodeError:
            output, rid = {"error": "invalid_input"}, None
        sys.stdout.write(json.dumps({"request_id": rid, "output": output}) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
