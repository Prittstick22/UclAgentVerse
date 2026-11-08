"""Constrained allocation with CVXPY. Owner: Cem. Spec: docs/07-engine-and-config.md §2.

minimise  wᵀΣw − λ_return·μᵀw + λ_track·‖Bw − b*‖² + λ_turn·Σ cᵢ|wᵢ − w_now,ᵢ| + λ_fee·OCFᵀw
subject to the mandate (sum to one, cash floor, caps, asset-class ranges, stocks total, exclusions).

μ is only ever a code-made estimate (engine/forecast.py, #73), never an LLM number. With no μ, or
forecast.lambda_return = 0, this is exactly the no-forecast optimiser (ablation).
"""
from __future__ import annotations

from typing import Literal

import cvxpy as cp
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from app.config import params
from app.schemas import Instrument, Mandate

Variant = Literal["recommended", "lower_cost", "lower_risk"]
VARIANTS: tuple[Variant, ...] = ("recommended", "lower_cost", "lower_risk")

MIN_WEIGHT = 1e-4   # holdings below this are dust: removed, then the problem is re-solved without them
STOCK_CAP_HEADROOM = 0.9   # solve single stocks at 90% of their cap (10% cap -> 9%)
STOCKS_MIN_MARGIN = 0.001  # solve 0.1 pp above a stocks floor
MARGIN = 1e-5       # solve slightly inside every limit so rounding 20 weights to 6 dp can never break one
SOLVERS = ("CLARABEL", "OSQP", "SCS")
INTERNAL = {"sum_to_one", "min_holding"}   # always/self-imposed: not a mandate limit worth reporting

KIND_WORDS = {"equity": ("shares", "a fund that holds shares"), "bond": ("bonds", "a bond fund")}


class OptimiseRequest(BaseModel):
    model_config = {"arbitrary_types_allowed": True}
    mandate: Mandate
    instruments: list[Instrument]          # candidates (already filtered to eligible + chosen by agents)
    cov: pd.DataFrame                      # annualised, index/columns = tickers
    current_weights: dict[str, float] = Field(default_factory=dict)
    variant: Variant = "recommended"
    mu: pd.Series | None = None            # annualised expected returns from engine/forecast.py (#73); None = no forecast
    lambda_return: float | None = None     # override params forecast.lambda_return (calibration / ablation only)
    tilt_caps: bool = True                 # bound the forecast's effect (params forecast.max_tilt_*); off only to calibrate


class OptimiseResult(BaseModel):
    status: Literal["optimal", "infeasible", "error"]
    variant: Variant
    weights: dict[str, float] = Field(default_factory=dict)
    cash_weight: float = 0.0
    binding_constraints: list[str] = Field(default_factory=list)
    vol_annual: float | None = None
    ocf_weighted: float | None = None
    turnover: float | None = None


def optimise(req: OptimiseRequest) -> OptimiseResult:
    m = req.mandate
    insts = [i for i in req.instruments
             if i.eligible and i.ticker not in m.exclusions and i.sleeve not in m.exclusions]
    if not insts:
        return OptimiseResult(status="infeasible", variant=req.variant,
                              binding_constraints=["No eligible instruments are left after the exclusions."])
    missing = _missing_risk_data(req.cov, [i.ticker for i in insts])
    if missing:  # never treat "no data" as "no risk": that would pile money into the unknown fund
        return OptimiseResult(status="error", variant=req.variant,
                              binding_constraints=[(f"No risk data for {', '.join(missing)}: "
                                                    "drop them from the candidates or fetch their prices.")])

    if req.mu is not None and not np.isfinite(req.mu.reindex([i.ticker for i in insts]).fillna(0.0).values).all():
        return OptimiseResult(status="error", variant=req.variant,
                              binding_constraints=["The return forecast contains an infinite value."])

    # The forecast may only LEAN the portfolio: solve without it first, then let it move each holding at most
    # max_tilt_per_holding and the whole portfolio at most max_tilt_total away from that answer.
    anchor: dict[str, float] | None = None
    if _forecast_on(req) and req.tilt_caps:
        base = optimise(req.model_copy(update={"mu": None}))
        if base.status != "optimal":
            return base
        anchor = base.weights

    # Solve slightly inside every limit; if the limits only just fit (e.g. one fund capped at exactly
    # the equity minimum), the margin would make it infeasible, so retry on the exact limits.
    result = _solve(req, insts, margin=MARGIN, anchor=anchor)
    if result == "infeasible":
        result = _solve(req, insts, margin=0.0, anchor=anchor)
    if result == "error":
        return OptimiseResult(status="error", variant=req.variant,
                              binding_constraints=["The solver failed on this problem. Try again or check the inputs."])
    if result == "infeasible":
        return OptimiseResult(status="infeasible", variant=req.variant, binding_constraints=_diagnose(m, insts))
    keep = [i for i, x in zip(insts, result[0]) if x >= MIN_WEIGHT]
    # Dust: re-solve without it (kept holdings floored at MIN_WEIGHT) instead of deleting it afterwards,
    # which used to push e.g. equity to 59.998% under a 60% minimum. If that fails, keep the dust.
    if keep and len(keep) < len(insts):
        again = _solve(req, keep, margin=result[2], floor=MIN_WEIGHT, anchor=anchor)
        if not isinstance(again, str):
            insts, result = keep, again
    return _result(req, insts, result[0], result[1])


Solved = tuple[np.ndarray, dict[str, cp.Constraint], float]


def _lambda_return(req: OptimiseRequest) -> float:
    if req.lambda_return is not None:
        return float(req.lambda_return)
    return float(params().get("forecast", {}).get("lambda_return", 0.0))


def _forecast_on(req: OptimiseRequest) -> bool:
    return req.mu is not None and _lambda_return(req) != 0.0


def _solve(req: OptimiseRequest, insts: list[Instrument], margin: float, floor: float = 0.0,
           anchor: dict[str, float] | None = None) -> Solved | Literal["infeasible", "error"]:
    p, costs, m = params()["optimiser"], params()["costs"], req.mandate
    tickers = [i.ticker for i in insts]
    n = len(tickers)
    cov = req.cov.loc[tickers, tickers].values
    cov = (cov + cov.T) / 2 + np.eye(n) * 1e-8
    ocf = np.array([i.ocf for i in insts])
    trade_cost = np.array([costs["trade"] + (costs["fx"] if i.currency == "USD" else 0.0) for i in insts])
    w_now = np.array([req.current_weights.get(t, 0.0) for t in tickers])
    is_eq = np.array([i.asset_class == "equity" for i in insts], dtype=float)
    is_bd = np.array([i.asset_class == "bond" for i in insts], dtype=float)
    is_stock = np.array([i.kind == "stock" for i in insts], dtype=float)
    from app.sim import compat
    # Solve single stocks inside their cap (headroom) so an ordinary price rise doesn't breach it the next day and
    # trigger an investigation; the checker and monitors keep the real cap. Funds are unchanged.
    stock_cap = m.caps.per_stock * (1.0 if compat.legacy else STOCK_CAP_HEADROOM)
    caps = np.array([stock_cap if i.kind == "stock" else m.caps.per_fund for i in insts])

    eq_lo, eq_hi = m.ranges.equity
    bd_lo, bd_hi = m.ranges.bond
    eq_target, bd_target = (eq_lo + eq_hi) / 2, (bd_lo + bd_hi) / 2
    lam_track, lam_turn, lam_fee, lam_risk = p["lambda_track"], p["lambda_turn"], p["lambda_fee"], 1.0
    if req.variant == "lower_cost":
        lam_fee *= 5
    elif req.variant == "lower_risk":
        eq_target, bd_target = eq_lo, min(bd_hi, 1 - eq_lo - m.ranges.cash_min)
        lam_risk *= 2

    w = cp.Variable(n, nonneg=True)
    cash = cp.Variable(nonneg=True)
    track = cp.square(is_eq @ w - eq_target) + cp.square(is_bd @ w - bd_target)
    objective = (lam_risk * cp.quad_form(w, cp.psd_wrap(cov)) + lam_track * track
                 + lam_turn * cp.sum(cp.multiply(trade_cost, cp.abs(w - w_now))) + lam_fee * ocf @ w)
    fc = params().get("forecast", {})
    if _forecast_on(req):
        # mu is annualised; the forecast is a 2-week estimate, so use the return expected over that horizon
        horizon = float(fc.get("horizon_days", 10)) / 252.0
        mu = req.mu.reindex(tickers).fillna(0.0).values * horizon  # no estimate = no tilt
        objective = objective - _lambda_return(req) * mu @ w
    e = margin
    named = {
        "sum_to_one": cp.sum(w) + cash == 1,
        "cash_min": cash >= m.ranges.cash_min + e,
        "caps": w <= np.maximum(caps - e, 0.0),
        "equity_min": is_eq @ w >= eq_lo + e,
        "equity_max": is_eq @ w <= eq_hi - e,
        "bond_min": is_bd @ w >= bd_lo + e,
        "bond_max": is_bd @ w <= max(bd_hi - e, 0.0),
        "stocks_total": is_stock @ w <= max(m.caps.stocks_total - e, 0.0),
    }
    if m.caps.stocks_min > 0:
        # rounding 8+ stock weights to 6 dp can land just under an exactly-met floor: solve a little above it
        named["stocks_min"] = is_stock @ w >= m.caps.stocks_min + (e if compat.legacy else max(e, STOCKS_MIN_MARGIN))
    if floor:
        named["min_holding"] = w >= floor
    if anchor is not None:
        a = np.array([anchor.get(t, 0.0) for t in tickers])
        dropped = [x for t, x in anchor.items() if t not in tickers]   # e.g. dust removed: sold in full
        if any(x > float(fc["max_tilt_per_holding"]) for x in dropped):
            return "infeasible"
        named["forecast_tilt_per_holding"] = cp.abs(w - a) <= float(fc["max_tilt_per_holding"])
        named["forecast_tilt_total"] = ((cp.sum(cp.abs(w - a)) + sum(dropped)) / 2
                                        <= float(fc["max_tilt_total"]))
    prob = cp.Problem(cp.Minimize(objective), list(named.values()))
    for solver in SOLVERS:
        if solver not in cp.installed_solvers():
            continue
        try:
            prob.solve(solver=solver)
        except (cp.SolverError, ValueError):
            continue
        if prob.status in ("infeasible", "infeasible_inaccurate"):
            return "infeasible"
        if prob.status in ("optimal", "optimal_inaccurate") and w.value is not None:
            return np.clip(w.value, 0.0, None), named, margin
    return "error"


def _result(req: OptimiseRequest, insts: list[Instrument], wv: np.ndarray, named: dict[str, cp.Constraint]
            ) -> OptimiseResult:
    tickers = [i.ticker for i in insts]
    wv = wv.round(6)
    cov = req.cov.loc[tickers, tickers].values
    ocf = np.array([i.ocf for i in insts])
    w_now = req.current_weights
    weights = {t: float(x) for t, x in zip(tickers, wv) if x > 0}
    turnover = sum(abs(weights.get(k, 0.0) - w_now.get(k, 0.0)) for k in set(weights) | set(w_now)) / 2
    return OptimiseResult(
        status="optimal", variant=req.variant, weights=weights, cash_weight=round(1.0 - float(wv.sum()), 6),
        binding_constraints=[k for k, c in named.items() if k not in INTERNAL and _is_tight(c)],
        vol_annual=float(np.sqrt(max(wv @ cov @ wv, 0.0))), ocf_weighted=float(ocf @ wv), turnover=float(turnover),
    )


def _missing_risk_data(cov: pd.DataFrame, tickers: list[str]) -> list[str]:
    """Tickers with no usable covariance: absent, NaN anywhere in their row, or zero variance."""
    sub = cov.reindex(index=tickers, columns=tickers)
    bad = ~np.isfinite(sub.values).all(axis=1) | ~(np.diag(sub.values) > 0)
    return [t for t, b in zip(tickers, bad) if b]


def _is_tight(c: cp.Constraint, tol: float = 1e-5) -> bool:
    try:
        dual = c.dual_value
        return dual is not None and bool(np.any(np.abs(np.atleast_1d(dual)) > tol))
    except Exception:  # pragma: no cover
        return False


def _diagnose(m: Mandate, insts: list[Instrument]) -> list[str]:
    """Plain-English reasons a mandate can't be met with these candidates. Never loosens the mandate."""
    reasons = []
    prof = m.profile
    for cls, (lo, _hi) in (("equity", m.ranges.equity), ("bond", m.ranges.bond)):
        funds = [i for i in insts if i.asset_class == cls and i.kind != "stock"]
        stocks = [i for i in insts if i.asset_class == cls and i.kind == "stock"]
        most = len(funds) * m.caps.per_fund + min(len(stocks) * m.caps.per_stock, m.caps.stocks_total)
        if most < lo - 1e-9:
            word, fund = KIND_WORDS[cls]
            if not funds and not stocks:
                reasons.append(f"The {prof} profile needs at least {lo:.0%} in {word}, "
                               f"but none of the candidates hold {word}. Add {fund}.")
            else:
                parts = []
                if funds:
                    parts.append(f"{len(funds)} fund{'s' if len(funds) > 1 else ''} at up to {m.caps.per_fund:.0%} each")
                if stocks:
                    parts.append(f"single stocks at up to {m.caps.stocks_total:.0%} in total")
                reasons.append(f"The {prof} profile needs at least {lo:.0%} in {word}, but the candidates can hold "
                               f"at most {most:.0%} ({' and '.join(parts)}). Add {fund} "
                               "or remove an exclusion.")
    stocks = [i for i in insts if i.kind == "stock"]
    if m.caps.stocks_min > min(len(stocks) * m.caps.per_stock, m.caps.stocks_total) + 1e-9:
        reasons.append(f"The {prof} profile needs at least {m.caps.stocks_min:.0%} in single stocks, but the "
                       f"candidates can hold at most {min(len(stocks) * m.caps.per_stock, m.caps.stocks_total):.0%} "
                       f"({len(stocks)} stocks at up to {m.caps.per_stock:.0%} each). Add stocks or remove an exclusion.")
    if m.ranges.equity[0] + m.ranges.bond[0] + m.ranges.cash_min > 1 + 1e-9:
        reasons.append(f"The minimums for shares ({m.ranges.equity[0]:.0%}), bonds ({m.ranges.bond[0]:.0%}) "
                       f"and cash ({m.ranges.cash_min:.0%}) add up to more than 100%.")
    return reasons or [("The candidates can't meet this profile's limits together. "
                        "Try adding more funds or removing an exclusion.")]
