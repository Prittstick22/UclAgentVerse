"""Constrained allocation with CVXPY. No return forecasts. Owner: Cem. Spec: docs/07-engine-and-config.md §2."""
from __future__ import annotations

from typing import Literal

import cvxpy as cp
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from app.config import params
from app.schemas import Instrument, Mandate

Variant = Literal["recommended", "lower_cost", "lower_risk"]


class OptimiseRequest(BaseModel):
    model_config = {"arbitrary_types_allowed": True}
    mandate: Mandate
    instruments: list[Instrument]          # candidates (already filtered to eligible + chosen by agents)
    cov: pd.DataFrame                      # annualised, index/columns = tickers
    current_weights: dict[str, float] = Field(default_factory=dict)
    variant: Variant = "recommended"


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
    p = params()["optimiser"]
    costs = params()["costs"]
    m = req.mandate
    insts = [i for i in req.instruments if i.ticker not in m.exclusions and i.sleeve not in m.exclusions]
    tickers = [i.ticker for i in insts]
    if not tickers:
        return OptimiseResult(status="infeasible", variant=req.variant, binding_constraints=["no eligible instruments"])
    n = len(tickers)
    cov = req.cov.reindex(index=tickers, columns=tickers).fillna(0.0).values
    cov = (cov + cov.T) / 2 + np.eye(n) * 1e-8
    ocf = np.array([i.ocf for i in insts])
    trade_cost = np.array([costs["trade"] + (costs["fx"] if i.currency == "USD" else 0.0) for i in insts])
    w_now = np.array([req.current_weights.get(t, 0.0) for t in tickers])
    is_eq = np.array([i.asset_class == "equity" for i in insts], dtype=float)
    is_bd = np.array([i.asset_class == "bond" for i in insts], dtype=float)
    is_stock = np.array([i.kind == "stock" for i in insts], dtype=float)
    caps = np.array([m.caps.per_stock if i.kind == "stock" else m.caps.per_fund for i in insts])

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
    named = {
        "sum_to_one": cp.sum(w) + cash == 1,
        "cash_min": cash >= m.ranges.cash_min,
        "caps": w <= caps,
        "equity_min": is_eq @ w >= eq_lo,
        "equity_max": is_eq @ w <= eq_hi,
        "bond_min": is_bd @ w >= bd_lo,
        "bond_max": is_bd @ w <= bd_hi,
        "stocks_total": is_stock @ w <= m.caps.stocks_total,
    }
    prob = cp.Problem(cp.Minimize(objective), list(named.values()))
    try:
        prob.solve()
    except cp.SolverError as e:  # pragma: no cover
        return OptimiseResult(status="error", variant=req.variant, binding_constraints=[str(e)])
    if prob.status not in ("optimal", "optimal_inaccurate") or w.value is None:
        return OptimiseResult(status="infeasible", variant=req.variant,
                              binding_constraints=_diagnose(m, insts))
    wv = np.clip(w.value, 0, None)
    wv[wv < 1e-4] = 0.0
    cash_v = float(1 - wv.sum())
    weights = {t: round(float(x), 6) for t, x in zip(tickers, wv) if x > 0}
    return OptimiseResult(
        status="optimal", variant=req.variant, weights=weights, cash_weight=round(cash_v, 6),
        binding_constraints=[k for k, c in named.items() if _is_tight(c)],
        vol_annual=float(np.sqrt(max(wv @ cov @ wv, 0))), ocf_weighted=float(ocf @ wv),
        turnover=float(np.abs(wv - w_now).sum() / 2),
    )


def _is_tight(c: cp.Constraint, tol: float = 1e-5) -> bool:
    try:
        v = c.violation()
        dual = c.dual_value
        return dual is not None and np.any(np.abs(np.atleast_1d(dual)) > tol) and np.all(np.atleast_1d(v) < 1e-4)
    except Exception:  # pragma: no cover
        return False


def _diagnose(m: Mandate, insts: list[Instrument]) -> list[str]:
    reasons = []
    eq_cap = sum(m.caps.per_stock if i.kind == "stock" else m.caps.per_fund for i in insts if i.asset_class == "equity")
    bd_cap = sum(m.caps.per_fund for i in insts if i.asset_class == "bond")
    if eq_cap < m.ranges.equity[0]:
        reasons.append(f"equity_min {m.ranges.equity[0]:.0%} unreachable: equity caps sum to {eq_cap:.0%}")
    if bd_cap < m.ranges.bond[0]:
        reasons.append(f"bond_min {m.ranges.bond[0]:.0%} unreachable: bond caps sum to {bd_cap:.0%}")
    if m.ranges.equity[0] + m.ranges.bond[0] + m.ranges.cash_min > 1:
        reasons.append("equity_min + bond_min + cash_min exceed 100%")
    return reasons or ["unknown: check mandate ranges vs candidate list"]
