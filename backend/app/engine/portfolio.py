"""Read-side portfolio snapshots and performance based on the paper ledger."""
from __future__ import annotations

from collections import defaultdict
from datetime import date

import pandas as pd
from pydantic import BaseModel

from app.config import params
from app.core.db import DB
from app.engine import metrics
from app.engine.ledger import Ledger
from app.schemas import PnlPeriod, PnlRow


class PortfolioDataUnavailable(ValueError):
    """The recording does not have the ledger basis for the requested view."""


class PositionMark(BaseModel):
    ticker: str
    units: float
    value_gbp: float
    cost_basis_gbp: float
    unrealised_pnl_gbp: float
    unrealised_pnl_pct: float
    realised_pnl_gbp: float
    contribution_to_return: float


class LedgerCheckpoint(BaseModel):
    date: str
    nav_gbp: float
    cash_gbp: float
    contributions_gbp: float
    positions: dict[str, PositionMark]
    prices: dict[str, float]
    weights: dict[str, float]
    targets: dict[str, float]
    purchases_gbp: dict[str, float]
    first_fill: str | None


def capture(ledger: Ledger, day: str, targets: dict[str, float] | None = None) -> LedgerCheckpoint:
    positions = {row["ticker"]: PositionMark.model_validate(row) for row in ledger.pnl_rows()}
    purchases: dict[str, float] = defaultdict(float)
    fills = [fill for fill in ledger.fills if fill.date <= day]
    for fill in fills:
        if fill.action == "buy":
            purchases[fill.ticker] += fill.amount_gbp
    return LedgerCheckpoint(
        date=day, nav_gbp=ledger.nav(), cash_gbp=ledger.cash_gbp, contributions_gbp=ledger.contributions_gbp,
        positions=positions, prices={ticker: ledger.last_prices[ticker] for ticker in positions
                                    if ticker in ledger.last_prices},
        weights=ledger.weights(), targets=targets or {}, purchases_gbp=dict(purchases),
        first_fill=min((fill.date for fill in fills), default=None),
    )


def record_checkpoint(db: DB, mode: str, ledger: Ledger, day: str, targets: dict[str, float]) -> None:
    db.put(f"ledger_checkpoints:{mode}", day, capture(ledger, day, targets).model_dump_json())


def checkpoints(db: DB, mode: str) -> list[LedgerCheckpoint]:
    return [LedgerCheckpoint.model_validate_json(raw) for _, raw in db.list(f"ledger_checkpoints:{mode}")]


def total_return(history: list[LedgerCheckpoint]) -> float:
    # Only funded marks can be return denominators. Include first-close gain/loss against the deposit.
    funded = [mark for mark in history if mark.nav_gbp > 0 and mark.contributions_gbp > 0]
    if not funded:
        return 0.0
    initial = funded[0].contributions_gbp
    nav = pd.Series([initial, *(mark.nav_gbp for mark in funded)])
    flows = pd.Series([mark.contributions_gbp for mark in funded]).diff().fillna(0.0)
    return metrics.compute(nav, pd.concat([pd.Series([0.0]), flows], ignore_index=True)).total_return


def _period_start(period: PnlPeriod, day: str) -> str | None:
    as_of = date.fromisoformat(day)
    if period == "since_purchase":
        return None
    if period == "sim_year":
        return params()["sim"]["start"]
    if period == "ytd":
        return as_of.replace(month=1, day=1).isoformat()
    months = 1 if period == "1m" else 3
    return (pd.Timestamp(as_of) - pd.DateOffset(months=months)).date().isoformat()


def pnl_rows(
    current: LedgerCheckpoint, history: list[LedgerCheckpoint], period: PnlPeriod, names: dict[str, str],
    *, as_of: str,
) -> list[PnlRow]:
    start = _period_start(period, as_of)
    opening = next((mark for mark in reversed(history) if start is not None and mark.date < start), None)
    if (start is not None and opening is None and current.positions
            and (current.first_fill is None or current.first_fill < start)):
        raise PortfolioDataUnavailable("Ledger history does not cover the requested P&L period")
    if start is not None and current.positions and current.date < start:
        raise PortfolioDataUnavailable("The last ledger mark is earlier than the requested P&L period")

    rows = []
    for ticker, mark in sorted(current.positions.items()):
        previous = opening.positions.get(ticker) if opening else None
        realised = mark.realised_pnl_gbp - (previous.realised_pnl_gbp if previous else 0.0)
        unrealised = mark.unrealised_pnl_gbp - (previous.unrealised_pnl_gbp if previous else 0.0)
        purchases = current.purchases_gbp.get(ticker, 0.0) - (
            opening.purchases_gbp.get(ticker, 0.0) if opening else 0.0
        )
        capital = (previous.value_gbp if previous else 0.0) + purchases
        pnl = realised + unrealised
        nav = opening.nav_gbp if opening and opening.nav_gbp > 0 else current.contributions_gbp
        rows.append(PnlRow(
            ticker=ticker, name=names.get(ticker, ticker), pnl_gbp=round(pnl, 2),
            pnl_pct=pnl / capital if capital > 0 else 0.0,
            realised_gbp=round(realised, 2), unrealised_gbp=round(unrealised, 2),
            contribution_to_return=pnl / nav if nav > 0 else 0.0,
        ))
    return rows
