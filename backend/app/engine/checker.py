"""Independent numbers verifier + mandate checker + pre-execution revalidation. Owner: Cem.

Never imports the optimiser. This is the hard stop that agents cannot override.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.config import params
from app.schemas import Instrument, Mandate


class Violation(BaseModel):
    code: str
    message: str
    ticker: str | None = None
    value: float | None = None
    limit: float | None = None


class CheckReport(BaseModel):
    passed: bool
    violations: list[Violation] = Field(default_factory=list)
    recomputed: dict = Field(default_factory=dict)


def check_proposal(weights: dict[str, float], cash_weight: float, mandate: Mandate,
                   catalogue: list[Instrument], current_weights: dict[str, float] | None = None,
                   nav_gbp: float | None = None) -> CheckReport:
    by_ticker = {i.ticker: i for i in catalogue}
    v: list[Violation] = []
    total = sum(weights.values()) + cash_weight
    if abs(total - 1.0) > 1e-4:
        v.append(Violation(code="sum", message=f"Weights + cash sum to {total:.4f}, not 1", value=total, limit=1.0))
    if cash_weight < mandate.ranges.cash_min - 1e-6:
        v.append(Violation(code="cash_min", message=f"Cash {cash_weight:.1%} below minimum {mandate.ranges.cash_min:.0%}",
                           value=cash_weight, limit=mandate.ranges.cash_min))
    eq = bd = stocks = 0.0
    for t, w in weights.items():
        inst = by_ticker.get(t)
        if inst is None or not inst.eligible:
            v.append(Violation(code="ineligible", message=f"{t} is not an eligible catalogue instrument", ticker=t))
            continue
        if w < -1e-9:
            v.append(Violation(code="short", message=f"Negative weight for {t}", ticker=t, value=w, limit=0))
        if t in mandate.exclusions or inst.sleeve in mandate.exclusions:
            v.append(Violation(code="excluded", message=f"{t} is excluded by the mandate", ticker=t))
        cap = mandate.caps.per_stock if inst.kind == "stock" else mandate.caps.per_fund
        if w > cap + 1e-6:
            kind = "Per-stock" if inst.kind == "stock" else "Per-fund"
            v.append(Violation(code="concentration", message=f"{kind} cap {cap:.0%} exceeded for {t} ({w:.0%})",
                               ticker=t, value=w, limit=cap))
        eq += w if inst.asset_class == "equity" else 0
        bd += w if inst.asset_class == "bond" else 0
        stocks += w if inst.kind == "stock" else 0
    lo, hi = mandate.ranges.equity
    if not lo - 1e-6 <= eq <= hi + 1e-6:
        v.append(Violation(code="equity_range", message=f"Equity {eq:.1%} outside {lo:.0%}–{hi:.0%}", value=eq))
    lo, hi = mandate.ranges.bond
    if not lo - 1e-6 <= bd <= hi + 1e-6:
        v.append(Violation(code="bond_range", message=f"Bonds {bd:.1%} outside {lo:.0%}–{hi:.0%}", value=bd))
    if stocks > mandate.caps.stocks_total + 1e-6:
        v.append(Violation(code="stocks_total", message=f"Single stocks {stocks:.1%} above {mandate.caps.stocks_total:.0%}",
                           value=stocks, limit=mandate.caps.stocks_total))

    recomputed: dict = {"equity": eq, "bond": bd, "stocks": stocks, "cash": cash_weight, "sum": total}
    if current_weights is not None:
        keys = set(weights) | set(current_weights)
        turnover = sum(abs(weights.get(k, 0) - current_weights.get(k, 0)) for k in keys) / 2
        recomputed["turnover"] = turnover
        if nav_gbp is not None:
            c = params()["costs"]
            cost = 0.0
            for k in keys:
                amt = abs(weights.get(k, 0) - current_weights.get(k, 0)) * nav_gbp
                inst = by_ticker.get(k)
                cost += amt * (c["trade"] + (c["fx"] if inst and inst.currency == "USD" else 0))
            recomputed["cost_gbp"] = round(cost, 2)
    return CheckReport(passed=not v, violations=v, recomputed=recomputed)


def revalidate(*, proposal_as_of: str, price_dates: dict[str, str], today: str, mandate_version_at_proposal: int,
               mandate_version_now: int, holdings_hash_at_proposal: str, holdings_hash_now: str,
               pending_order_keys: set[str], order_key: str) -> CheckReport:
    """Pre-execution checks: fresh prices, same mandate, same holdings, no duplicate order."""
    import pandas as pd

    v: list[Violation] = []
    stale_after = params()["risk"]["stale_after_days"]
    if len(pd.bdate_range(proposal_as_of, today)) - 1 > stale_after:
        v.append(Violation(code="stale_data", message=f"The proposal is from {proposal_as_of}; ask for a fresh one"))
    for t, d in price_dates.items():
        if len(pd.bdate_range(d, today)) - 1 > stale_after:
            v.append(Violation(code="stale_data", message=f"Price for {t} is from {d}", ticker=t))
    if mandate_version_now != mandate_version_at_proposal:
        v.append(Violation(code="mandate_changed", message="Mandate changed since the proposal"))
    if holdings_hash_now != holdings_hash_at_proposal:
        v.append(Violation(code="holdings_changed", message="Holdings changed since the proposal"))
    if order_key in pending_order_keys:
        v.append(Violation(code="duplicate_order", message="An identical order is already pending"))
    return CheckReport(passed=not v, violations=v)
