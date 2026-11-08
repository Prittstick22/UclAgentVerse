"""Risk: returns, Ledoit-Wolf covariance, correlation lattice, vol, drawdown, beta. Owner: Cem."""
from __future__ import annotations

import numpy as np
import pandas as pd
from pydantic import BaseModel
from sklearn.covariance import LedoitWolf

from app.config import params

TRADING_DAYS = 252
CALLOUT_HIGH = 0.8   # |corr| at or above this: "rise and fall together"
CALLOUT_LOW = 0.2    # corr at or below this: "help diversify each other"


def lookbacks() -> tuple[int, int]:
    """(lookback, min_lookback) in trading days, from params.yaml (504 / 252)."""
    o = params()["optimiser"]
    return int(o["lookback"]), int(o["min_lookback"])


class History(BaseModel):
    """How much return history a calculation really used."""
    days: int
    lookback: int
    min_lookback: int
    short_history: bool          # fewer than min_lookback return rows: usable, but flagged
    dropped_rows: int = 0        # rows removed because some ticker had no price that day


def log_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Daily log returns. Rows where any ticker lacks a return are dropped (never filled with 0,
    which would fake a calm day and shrink vol and correlations)."""
    px = prices.where(prices > 0)  # zero/negative prices are bad data, not returns
    r = np.log(px / px.shift(1)).replace([np.inf, -np.inf], np.nan)
    return r.dropna(how="any")


def prepare_returns(prices: pd.DataFrame, lookback: int | None = None, min_lookback: int | None = None
                    ) -> tuple[pd.DataFrame, History]:
    """Last `lookback` clean return rows of `prices` plus a History flag. Raises ValueError if < 2 rows."""
    lb, mn = lookbacks()
    try:  # agents pass tool args as JSON, so "504" or 504.0 can arrive here
        lookback = lb if lookback is None else int(lookback)
    except (TypeError, ValueError):
        raise ValueError(f"lookback must be a whole number of trading days, got {lookback!r}") from None
    if lookback < 2:  # tail(-n) would silently mean "everything but the first n rows"
        raise ValueError(f"lookback must be at least 2 trading days, got {lookback}")
    min_lookback = min(mn, lookback) if min_lookback is None else min_lookback
    window = prices.sort_index().tail(lookback + 1)
    raw_rows = max(len(window) - 1, 0)
    rets = log_returns(window)
    if len(rets) < 2:
        raise ValueError(f"Not enough price history for risk: {len(rets)} usable return rows")
    return rets, History(days=len(rets), lookback=lookback, min_lookback=min_lookback,
                         short_history=len(rets) < min_lookback, dropped_rows=raw_rows - len(rets))


def covariance(returns: pd.DataFrame) -> pd.DataFrame:
    """Ledoit-Wolf shrunk covariance, annualised."""
    lw = LedoitWolf().fit(returns.values)
    return pd.DataFrame(lw.covariance_ * TRADING_DAYS, index=returns.columns, columns=returns.columns)


def correlation_from_cov(cov: pd.DataFrame) -> pd.DataFrame:
    """corr = D^-1 Σ D^-1. A zero-variance ticker has no defined correlation: reported as 0 with others."""
    d = np.sqrt(np.diag(cov.values))
    denom = np.outer(d, d)
    with np.errstate(divide="ignore", invalid="ignore"):
        corr = np.where(denom > 0, cov.values / denom, 0.0)
    corr = np.clip(corr, -1.0, 1.0)
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
    history_days: int = 0
    short_history: bool = False


def correlation_report(prices: pd.DataFrame, as_of: str, lookback: int | None = None,
                       names: dict[str, str] | None = None) -> CorrelationReport:
    """Correlation lattice as of `as_of`. `lookback` defaults to params optimiser.lookback (504).

    Rows dated after `as_of` are ignored, so any past date works; the DataGateway still decides
    what may be read at all (callers must fetch prices through it). Histories shorter than
    min_lookback are used as they are and flagged via `short_history`."""
    prices = prices.sort_index().loc[: pd.Timestamp(as_of)]
    rets, hist = prepare_returns(prices, lookback)
    corr = correlation_from_cov(covariance(rets))
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
        if c >= CALLOUT_HIGH:
            callouts.append(Callout(a=a, b=b, corr=round(c, 3),
                                    text=f"{na} and {nb} have a correlation of {c:.2f}: they mostly rise and fall together."))
        elif c <= CALLOUT_LOW:
            callouts.append(Callout(a=a, b=b, corr=round(c, 3),
                                    text=f"{na} and {nb} have a correlation of {c:.2f}: they help diversify each other."))
    callouts.sort(key=lambda x: -abs(x.corr))
    return CorrelationReport(
        as_of=as_of, lookback=hist.lookback, tickers=tickers,
        matrix=[[round(float(v), 4) for v in row] for row in corr.values],
        avg_pairwise=round(avg, 4), callouts=callouts[:8],
        history_days=hist.days, short_history=hist.short_history,
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


class RiskStats(BaseModel):
    vol: float                   # annualised, Ledoit-Wolf covariance
    max_drawdown: float          # backtest of constant weights over the window (<= 0)
    beta: float | None           # vs the benchmark; None if no benchmark or no variance
    herfindahl: float            # sum of squared weights (cash excluded); 1/n when equal-weighted
    history_days: int
    short_history: bool
    label: str = "backtest over the lookback window, not a forecast"


def risk_stats(weights: pd.Series | dict[str, float], prices: pd.DataFrame, benchmark: str | None = None,
               lookback: int | None = None) -> RiskStats:
    """Vol, max drawdown, beta and Herfindahl for `weights` (fractions of NAV; the rest is cash at 0%).

    `prices` must be as_of-limited and contain every weighted ticker, plus `benchmark` for beta
    (default params benchmark_global_etf). Drawdown is a daily-rebalanced constant-weight backtest."""
    w = pd.Series(weights, dtype=float)
    if not np.isfinite(w.values).all():
        raise ValueError("risk_stats weights must be finite numbers")
    if (w < 0).any() or w.sum() > 1.0 + 1e-6:
        raise ValueError(f"risk_stats weights must be long-only and sum to at most 1 (got sum {w.sum():.4f})")
    w = w[w != 0]
    if w.empty:
        raise ValueError("risk_stats needs at least one non-zero weight")
    missing = [t for t in w.index if t not in prices.columns]
    if missing:
        raise KeyError(f"No price data for {missing}")
    benchmark = params()["benchmark_global_etf"] if benchmark is None else benchmark
    cols = list(w.index) + ([benchmark] if benchmark in prices.columns and benchmark not in w.index else [])
    rets, hist = prepare_returns(prices[cols], lookback)
    vol = portfolio_vol(w, covariance(rets[list(w.index)]))
    simple = np.expm1(rets)  # log -> simple returns for compounding NAV
    port = simple[list(w.index)] @ w
    nav = pd.concat([pd.Series([1.0]), (1.0 + port).cumprod().reset_index(drop=True)], ignore_index=True)
    b = beta(port, simple[benchmark]) if benchmark in simple.columns else float("nan")
    return RiskStats(vol=vol, max_drawdown=max_drawdown(nav), beta=None if np.isnan(b) else b,
                     herfindahl=herfindahl(w), history_days=hist.days, short_history=hist.short_history)
