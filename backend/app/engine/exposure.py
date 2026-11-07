"""Look-through ownership exposure. Owner: Cem.

exposure(entity) = Σ_fund w_fund × w_entity_in_fund + w_direct
This is OWNERSHIP exposure, not a predicted loss (say so in the UI).
"""
from __future__ import annotations

from pydantic import BaseModel


class ExposureResult(BaseModel):
    entity: str
    total: float
    direct: float
    via_funds: dict[str, float]
    note: str = "Ownership exposure, not a predicted loss."


def look_through(portfolio_weights: dict[str, float], etf_holdings: dict[str, list[dict]], entity: str) -> ExposureResult:
    direct = portfolio_weights.get(entity, 0.0)
    via: dict[str, float] = {}
    for fund, w_fund in portfolio_weights.items():
        for h in etf_holdings.get(fund, []):
            if entity in (h.get("ticker"), h.get("name")):
                via[fund] = w_fund * float(h.get("weight", 0.0))
    return ExposureResult(entity=entity, total=direct + sum(via.values()), direct=direct, via_funds=via)
