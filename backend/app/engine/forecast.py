"""Walk-forward 2-week forecast. Owner: Cem. Spec: docs/07-engine-and-config.md §2a (#73).

At a given day it looks `horizon` trading days ahead using ONLY prices dated <= as_of (read through the
DataGateway, which refuses anything later):
- mu:    EWMA mean of daily log returns (the last ~2 weeks weigh most), shrunk towards 0 by `forecast.shrink`
- sigma: EWMA volatility
- p10 / p50 / p90 of the horizon return per asset and for the portfolio (Ledoit-Wolf covariance)

Every number is an estimate, not a promise. The optimiser uses `mu` (annualised) via `- lambda_return * mu'w`.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from app.config import params
from app.engine import risk

Z90 = 1.2815515655446004      # standard normal 90th percentile
MIN_OBS = 20                  # fewer daily returns than this: no estimate for that ticker
LABEL = "estimate, not a promise"


class Band(BaseModel):
    """Horizon return quantiles as simple returns (0.02 = +2%)."""
    p10: float
    p50: float
    p90: float


class AssetForecast(BaseModel):
    ticker: str
    mu_annual: float            # shrunk EWMA mean log return, annualised: what the optimiser sees
    sigma_annual: float         # EWMA volatility, annualised
    band: Band                  # over the horizon
    obs: int                    # daily returns used


class Forecast(BaseModel):
    as_of: str
    horizon_days: int
    halflife_days: float
    shrink: float
    lookback_days: int
    mu: dict[str, float] = Field(default_factory=dict)        # ticker -> mu_annual (for OptimiseRequest.mu)
    assets: list[AssetForecast] = Field(default_factory=list)
    skipped: list[str] = Field(default_factory=list)          # not enough history for an estimate
    portfolio: Band | None = None
    portfolio_weights: dict[str, float] = Field(default_factory=dict)
    portfolio_basis: str = "none"                             # "given" | "equal" | "none"
    label: str = LABEL


def ewma_weights(n: int, halflife: float) -> np.ndarray:
    """Weights for n observations, oldest first, newest weighs most; sums to 1."""
    if halflife <= 0:
        raise ValueError(f"halflife must be positive, got {halflife}")
    age = np.arange(n - 1, -1, -1, dtype=float)
    w = 0.5 ** (age / halflife)
    return w / w.sum()


def _band(mean_log: float, sd_log: float) -> Band:
    q = [mean_log - Z90 * sd_log, mean_log, mean_log + Z90 * sd_log]
    p10, p50, p90 = (float(np.expm1(x)) for x in q)
    return Band(p10=round(p10, 6), p50=round(p50, 6), p90=round(p90, 6))


def forecast(gw: Any, tickers: list[str], as_of: str, horizon: int | None = None,
             weights: dict[str, float] | None = None) -> Forecast:
    """2-week (default) walk-forward estimate for `tickers` from data dated <= as_of only.

    `weights` (fractions of NAV, cash = the rest at 0%) give the portfolio band; without them an equal-weight
    band over the estimated tickers is reported and labelled as such.
    """
    cfg, opt = params()["forecast"], params()["optimiser"]
    horizon = int(cfg["horizon_days"] if horizon is None else horizon)
    if horizon < 1:
        raise ValueError(f"horizon must be at least 1 trading day, got {horizon}")
    halflife, shrink, lookback = float(cfg["ewma_halflife_days"]), float(cfg["shrink"]), int(opt["lookback"])
    tickers = list(dict.fromkeys(tickers))
    px = gw.prices(tickers, end=as_of, caller="engine.forecast").sort_index()
    px = px.loc[: pd.Timestamp(as_of)].tail(lookback + 1)
    out = Forecast(as_of=as_of, horizon_days=horizon, halflife_days=halflife, shrink=shrink, lookback_days=lookback)

    mu_d: dict[str, float] = {}
    for t in tickers:
        s = px[t] if t in px.columns else pd.Series(dtype=float)
        s = s.where(s > 0).dropna()
        r = np.log(s / s.shift(1)).replace([np.inf, -np.inf], np.nan).dropna().values
        if len(r) < MIN_OBS:
            out.skipped.append(t)
            continue
        w = ewma_weights(len(r), halflife)
        m_raw = float(w @ r)
        sd = float(np.sqrt(max(w @ (r - m_raw) ** 2, 0.0)))
        m = (1.0 - shrink) * m_raw
        mu_d[t] = m
        out.mu[t] = round(m * risk.TRADING_DAYS, 6)
        out.assets.append(AssetForecast(ticker=t, mu_annual=out.mu[t], sigma_annual=round(sd * np.sqrt(risk.TRADING_DAYS), 6),
                                        band=_band(horizon * m, np.sqrt(horizon) * sd), obs=len(r)))

    est = [t for t in tickers if t in mu_d]
    if weights:
        pw = {t: float(x) for t, x in weights.items() if x and t in mu_d}
        basis = "given"
    else:
        pw = {t: 1.0 / len(est) for t in est} if est else {}
        basis = "equal"
    if pw:
        names = list(pw)
        rets = risk.log_returns(px[names])
        if len(names) == 1 or len(rets) >= MIN_OBS:
            cov_d = (risk.covariance(rets).values / risk.TRADING_DAYS if len(names) > 1
                     else np.array([[next(a.sigma_annual for a in out.assets if a.ticker == names[0]) ** 2
                                     / risk.TRADING_DAYS]]))
            wv = np.array([pw[t] for t in names])
            mean = horizon * float(wv @ np.array([mu_d[t] for t in names]))
            sd = float(np.sqrt(max(horizon * wv @ cov_d @ wv, 0.0)))
            out.portfolio, out.portfolio_weights, out.portfolio_basis = _band(mean, sd), pw, basis
    return out


# ---------------------------------------------------------------------- calibration (development data only)
LAMBDA_GRID = (0.0, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0)
PROFILES = ("cautious", "balanced", "growth", "adventurous")


def calibrate_lambda(state: Any, target_turnover: float = 0.10, every: int = 10,
                     grid: tuple[float, ...] = LAMBDA_GRID) -> dict:
    """Pick forecast.lambda_return from the DEVELOPMENT period only (params periods.development, before the sim).

    Rule (written down before looking at any result): at each fortnightly review date in the development period,
    for each profile, measure how much of the portfolio the forecast moves on its own (turnover vs the
    no-forecast optimiser, tilt caps OFF). Choose the largest lambda whose median added turnover is at most
    `target_turnover` for every profile. The tilt caps are a separate hard backstop on top.
    """
    from app.engine import optimiser
    from app.profile.quiz import mandate_for

    dev_start, dev_end = params()["periods"]["development"]
    lookback, min_lb = int(params()["optimiser"]["lookback"]), int(params()["optimiser"]["min_lookback"])
    gw, clock = state.gw, state.clock
    original = clock.as_of_str()
    days = [d for d in gw.trading_days(dev_start, dev_end)][min_lb::every]   # need a year of history first
    added: dict[tuple[str, float], list[float]] = {}
    try:
        for d in days:
            day = str(d.date())
            clock.set(day)
            insts = gw.catalogue()   # fees as known on that day, not today's
            tickers = [i.ticker for i in insts]
            px = gw.prices(tickers, end=day, caller="engine.forecast.calibrate").tail(lookback + 1)
            cov = risk.covariance(risk.log_returns(px))
            mu = pd.Series(forecast(gw, tickers, day).mu)
            for prof in PROFILES:
                m = mandate_for(prof)
                base = optimiser.optimise(optimiser.OptimiseRequest(mandate=m, instruments=insts, cov=cov))
                if base.status != "optimal":
                    continue
                for lam in grid:
                    r = optimiser.optimise(optimiser.OptimiseRequest(mandate=m, instruments=insts, cov=cov, mu=mu,
                                                                     lambda_return=lam, tilt_caps=False))
                    if r.status == "optimal":
                        keys = set(r.weights) | set(base.weights)
                        to = sum(abs(r.weights.get(k, 0) - base.weights.get(k, 0)) for k in keys) / 2
                        added.setdefault((prof, lam), []).append(to)
    finally:
        clock.set(original)
    table = {prof: {lam: float(np.median(added.get((prof, lam), [np.nan]))) for lam in grid} for prof in PROFILES}
    ok = [lam for lam in grid if all(table[p][lam] <= target_turnover + 1e-12 for p in PROFILES)]
    return {"chosen": max(ok) if ok else 0.0, "target_turnover": target_turnover, "review_dates": len(days),
            "period": [str(days[0].date()), str(days[-1].date())] if days else [], "median_added_turnover": table}


def main(argv: list[str] | None = None) -> None:  # pragma: no cover
    import argparse
    import json

    from app.container import build_state

    p = argparse.ArgumentParser(description="2-week forecast tools (#73)")
    p.add_argument("--calibrate", action="store_true", help="choose lambda_return on development data only")
    p.add_argument("--target-turnover", type=float, default=0.10)
    a = p.parse_args(argv)
    if a.calibrate:
        state = build_state()
        res = calibrate_lambda(state, a.target_turnover)
        print(f"Data source: {state.gw.snapshot.source_label}. Development reviews: {res['review_dates']} "
              f"({res['period'][0]} to {res['period'][1]}); sim-window data not used.")
        print("Median share of the portfolio moved by the forecast alone (tilt caps off):")
        print("lambda   " + "  ".join(f"{p:>11s}" for p in PROFILES))
        for lam in LAMBDA_GRID:
            print(f"{lam:<8} " + "  ".join(f"{res['median_added_turnover'][p][lam]:>11.1%}" for p in PROFILES))
        print(f"Rule: largest lambda with median <= {a.target_turnover:.0%} for every profile -> "
              f"lambda_return = {res['chosen']}")
        print(json.dumps({"lambda_return": res["chosen"]}))


if __name__ == "__main__":  # pragma: no cover
    main()
