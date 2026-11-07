"""Backtest a weight set over [start, end] with end <= as_of (enforced by the gateway). Owner: Cem."""
from __future__ import annotations

from typing import Literal

import pandas as pd
from pydantic import BaseModel

from app.data.gateway import DataGateway
from app.engine.metrics import Metrics, compute


class BacktestResult(BaseModel):
    start: str
    end: str
    rebalance: str
    metrics: Metrics
    nav: list[tuple[str, float]]
    label: str = "Historical behaviour on data before the decision date (simulated, not a forecast)"


def run(gw: DataGateway, weights: dict[str, float], start: str, end: str | None = None,
        rebalance: Literal["none", "monthly", "quarterly"] = "quarterly", capital: float = 10_000) -> BacktestResult:
    prices = gw.prices(list(weights), start=start, end=end, caller="backtest").dropna()
    w = pd.Series(weights) / sum(weights.values())
    units = (capital * w) / prices.iloc[0]
    navs = []
    last_period = None
    for dt, row in prices.iterrows():
        period = (dt.year, dt.month if rebalance == "monthly" else (dt.month - 1) // 3)
        nav = float((units * row).sum())
        if rebalance != "none" and last_period is not None and period != last_period:
            units = (nav * w) / row
        last_period = period
        navs.append((str(dt.date()), nav))
    nav_s = pd.Series([v for _, v in navs], index=pd.to_datetime([d for d, _ in navs]))
    return BacktestResult(start=navs[0][0], end=navs[-1][0], rebalance=rebalance, metrics=compute(nav_s), nav=navs)
