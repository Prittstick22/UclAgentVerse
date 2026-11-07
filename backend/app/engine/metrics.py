"""Performance metrics. Owner: Cem."""
from __future__ import annotations

import numpy as np
import pandas as pd
from pydantic import BaseModel

from app.engine.risk import TRADING_DAYS, max_drawdown


class Metrics(BaseModel):
    total_return: float
    vol_annual: float
    max_drawdown: float
    sharpe: float          # rf = 0, labelled in UI
    turnover: float = 0.0
    costs_gbp: float = 0.0
    trades: int = 0


def time_weighted_returns(nav: pd.Series, flows: pd.Series | None = None) -> pd.Series:
    """Daily TWR: strips contributions (flows on day t are added before the day's close)."""
    flows = flows.reindex(nav.index).fillna(0.0) if flows is not None else pd.Series(0.0, index=nav.index)
    prev = nav.shift(1)
    r = (nav - flows - prev) / prev
    return r.dropna()


def compute(nav: pd.Series, flows: pd.Series | None = None, turnover: float = 0.0, costs_gbp: float = 0.0,
            trades: int = 0) -> Metrics:
    r = time_weighted_returns(nav, flows)
    growth = (1 + r).cumprod()
    total = float(growth.iloc[-1] - 1) if len(growth) else 0.0
    vol = float(r.std() * np.sqrt(TRADING_DAYS)) if len(r) > 1 else 0.0
    sharpe = float(r.mean() * TRADING_DAYS / vol) if vol else 0.0
    mdd = max_drawdown(growth) if len(growth) else 0.0
    return Metrics(total_return=total, vol_annual=vol, max_drawdown=mdd, sharpe=sharpe,
                   turnover=turnover, costs_gbp=costs_gbp, trades=trades)
