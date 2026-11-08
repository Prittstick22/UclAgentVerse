"""Look-through ownership exposure. Owner: Cem.

exposure(entity) = Σ_fund w_fund × w_entity_in_fund + w_direct
This is OWNERSHIP exposure, not a predicted loss (say so in the UI).
"""
from __future__ import annotations

import math

from pydantic import BaseModel, Field


class ExposureResult(BaseModel):
    entity: str
    total: float | None
    known_total: float = 0.0
    missing: list[str] = Field(default_factory=list)
    coverage: dict[str, float] = Field(default_factory=dict)
    direct: float
    via_funds: dict[str, float]
    note: str = "Ownership exposure, not a predicted loss."


def look_through(portfolio_weights: dict[str, float], etf_holdings: dict[str, list[dict]], entity: str,
                 funds: set[str] | None = None) -> ExposureResult:
    direct = portfolio_weights.get(entity, 0.0)
    via: dict[str, float] = {}
    for fund, w_fund in portfolio_weights.items():
        weights = _clean_weights(etf_holdings.get(fund, []))
        for h, w in weights:
            if entity in (h.get("ticker"), h.get("name")):
                via[fund] = via.get(fund, 0.0) + w_fund * w   # a company listed twice (2 share classes) adds up
    funds = funds if funds is not None else set(etf_holdings)
    coverage = {fund: min(1.0, sum(weight for _, weight in _clean_weights(etf_holdings.get(fund, []))))
                for fund in funds if portfolio_weights.get(fund, 0) > 0}
    missing = sorted(fund for fund, covered in coverage.items() if covered == 0)
    known = direct + sum(via.values())
    note = "Ownership exposure, not a predicted loss."
    if missing:
        note += " Total is unknown because fund constituents are unavailable; known_total is only the known portion."
    elif any(covered < 1 - 1e-6 for covered in coverage.values()):
        note += " A lower bound: supplied fund constituents cover only part of the funds."
    return ExposureResult(entity=entity, total=None if missing else known, known_total=known,
                          direct=direct, via_funds=via, missing=missing, coverage=coverage, note=note)


# ---------------------------------------------------------------------- overlap (#25)
OVERLAP_NOTE = ("Share of the two holdings' weight that sits in the same companies, from the published "
                "holdings we have. A lower bound if a holdings list is only the top positions.")


class CommonHolding(BaseModel):
    key: str              # ticker if known, else the company name
    name: str
    weight_a: float
    weight_b: float


class OverlapResult(BaseModel):
    a: str
    b: str
    overlap: float | None               # Σ min(w_a, w_b) over shared companies, 0..1; None = no data for one side
    common: list[CommonHolding]
    coverage_a: float                   # share of `a` we have look-through data for (1.0 for a single stock)
    coverage_b: float
    missing: list[str]                  # holdings with no look-through data at all
    note: str = OVERLAP_NOTE


def _norm(name: object) -> str:
    return " ".join(str(name or "").lower().replace(".", " ").replace(",", " ").split())


def _clean_weights(holdings: list[dict]) -> list[tuple[dict, float]]:
    """(holding, weight as a fraction). Skips missing, non-numeric, NaN or non-positive weights. A list that adds
    up to more than 100% must be in percent (4.5 = 4.5%), so it is divided by 100."""
    out = []
    for h in holdings:
        try:
            w = float(h.get("weight", 0.0) or 0.0)
        except (TypeError, ValueError):
            continue
        if math.isfinite(w) and w > 0:
            out.append((h, w))
    if sum(w for _, w in out) > 1.0 + 1e-6:
        out = [(h, w / 100.0) for h, w in out]
    return out


def _constituents(ticker: str, etf_holdings: dict[str, list[dict]], stocks: set[str],
                  name_to_ticker: dict[str, str]) -> dict[str, tuple[str, float]]:
    """key -> (name, weight). A single stock 'holds' itself at 100%. Key: the ticker, or (for a line without one)
    the ticker another line gave the same company name, else the normalised name."""
    if ticker in stocks:
        return {ticker: (ticker, 1.0)}
    out: dict[str, tuple[str, float]] = {}
    for h, w in _clean_weights(etf_holdings.get(ticker, [])):
        name = _norm(h.get("name"))
        key = h.get("ticker") or name_to_ticker.get(name) or name
        if not key:
            continue
        label = h.get("name") or key
        out[key] = (out.get(key, (label, 0.0))[0], out.get(key, (label, 0.0))[1] + w)   # duplicates add up
    return out


def _name_map(funds: list[str], etf_holdings: dict[str, list[dict]]) -> dict[str, str]:
    """Company name -> ticker, learned from any line that has both (so name-only lists still match)."""
    return {_norm(h.get("name")): h["ticker"] for f in funds for h in etf_holdings.get(f, [])
            if h.get("ticker") and _norm(h.get("name"))}


def overlap(a: str, b: str, etf_holdings: dict[str, list[dict]], stocks: set[str] | None = None) -> OverlapResult:
    """How much of `a` and `b` is the same companies, by weight. Ownership, not a prediction."""
    stocks = stocks or set()
    names = _name_map([a, b], etf_holdings)
    ca, cb = _constituents(a, etf_holdings, stocks, names), _constituents(b, etf_holdings, stocks, names)
    missing = [t for t, c in ((a, ca), (b, cb)) if not c]
    common = sorted(
        (CommonHolding(key=k, name=ca[k][0], weight_a=round(ca[k][1], 6), weight_b=round(cb[k][1], 6))
         for k in set(ca) & set(cb)),
        key=lambda h: -min(h.weight_a, h.weight_b))
    value = None if missing else round(sum(min(h.weight_a, h.weight_b) for h in common), 6)
    return OverlapResult(a=a, b=b, overlap=value, common=common[:10],
                         coverage_a=round(min(sum(w for _, w in ca.values()), 1.0), 6),
                         coverage_b=round(min(sum(w for _, w in cb.values()), 1.0), 6), missing=missing)


def overlap_pairs(tickers: list[str], etf_holdings: dict[str, list[dict]], stocks: set[str] | None = None
                  ) -> list[OverlapResult]:
    """Every pair, biggest known overlap first; pairs without data last."""
    tickers = list(dict.fromkeys(tickers))
    pairs = [overlap(x, y, etf_holdings, stocks) for i, x in enumerate(tickers) for y in tickers[i + 1:]]
    return sorted(pairs, key=lambda r: (r.overlap is None, -(r.overlap or 0.0)))
