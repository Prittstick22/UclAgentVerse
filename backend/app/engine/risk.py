"""Risk: returns, Ledoit-Wolf covariance, correlation lattice, vol, drawdown, beta. Owner: Cem."""
from __future__ import annotations

import numpy as np
import pandas as pd
from pydantic import BaseModel
from sklearn.covariance import LedoitWolf

TRADING_DAYS = 252


def log_returns(prices: pd.DataFrame) -> pd.DataFrame:
    return np.log(prices / prices.shift(1)).dropna(how="all").fillna(0.0)


def covariance(returns: pd.DataFrame) -> pd.DataFrame:
    """Ledoit-Wolf shrunk covariance, annualised."""
    lw = LedoitWolf().fit(returns.values)
    return pd.DataFrame(lw.covariance_ * TRADING_DAYS, index=returns.columns, columns=returns.columns)


def correlation_from_cov(cov: pd.DataFrame) -> pd.DataFrame:
    d = np.sqrt(np.diag(cov.values))
    corr = cov.values / np.outer(d, d)
    np.fill_diagonal(corr, 1.0)
    return pd.DataFrame(corr, index=cov.index, columns=cov.columns)


class Callout(BaseModel):
    a: str
    b: str
    corr: float
    text: str


class CorrelationReport(BaseModel):
    as_of: str
    lookback: int
    tickers: list[str]
    matrix: list[list[float]]
    avg_pairwise: float
    callouts: list[Callout]


def correlation_report(prices: pd.DataFrame, as_of: str, lookback: int = 252, names: dict[str, str] | None = None
                       ) -> CorrelationReport:
    """prices must already be as_of-limited (from DataGateway)."""
    window = prices.tail(lookback + 1)
    corr = correlation_from_cov(covariance(log_returns(window)))
    tickers = list(corr.columns)
    n = len(tickers)
    iu = np.triu_indices(n, k=1)
    avg = float(corr.values[iu].mean()) if n > 1 else 1.0
    names = names or {}
    callouts: list[Callout] = []
    for i, j in zip(*iu):
        c = float(corr.iat[i, j])
        a, b = tickers[i], tickers[j]
        na, nb = names.get(a, a), names.get(b, b)
        if c >= 0.8:
            callouts.append(Callout(a=a, b=b, corr=round(c, 3),
                                    text=f"{na} and {nb} have a correlation of {c:.2f}: they mostly rise and fall together."))
        elif c <= 0.2:
            callouts.append(Callout(a=a, b=b, corr=round(c, 3),
                                    text=f"{na} and {nb} have a correlation of {c:.2f}: they help diversify each other."))
    callouts.sort(key=lambda x: -abs(x.corr))
    return CorrelationReport(
        as_of=as_of, lookback=lookback, tickers=tickers,
        matrix=[[round(float(v), 4) for v in row] for row in corr.values],
        avg_pairwise=round(avg, 4), callouts=callouts[:8],
    )


def portfolio_vol(weights: pd.Series, cov: pd.DataFrame) -> float:
    w = weights.reindex(cov.index).fillna(0.0).values
    return float(np.sqrt(max(w @ cov.values @ w, 0.0)))


def max_drawdown(nav: pd.Series) -> float:
    peak = nav.cummax()
    return float((nav / peak - 1.0).min())


def beta(asset_returns: pd.Series, market_returns: pd.Series) -> float:
    df = pd.concat([asset_returns, market_returns], axis=1).dropna()
    if len(df) < 2:
        return float("nan")
    var = df.iloc[:, 1].var()
    return float(df.iloc[:, 0].cov(df.iloc[:, 1]) / var) if var else float("nan")


def herfindahl(weights: pd.Series) -> float:
    return float((weights**2).sum())
