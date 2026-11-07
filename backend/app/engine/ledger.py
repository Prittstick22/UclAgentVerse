"""Paper ledger: positions, cash, fills (t+1 close) with costs, fund fees, P&L. Owner: Cem."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from app.config import params
from app.schemas import Instrument


@dataclass
class Position:
    units: float = 0.0
    cost_basis_gbp: float = 0.0     # total cost of units held
    realised_pnl_gbp: float = 0.0


@dataclass
class Fill:
    date: str
    ticker: str
    action: str
    units: float
    price_gbp: float
    amount_gbp: float
    cost_gbp: float


@dataclass
class Ledger:
    catalogue: dict[str, Instrument]
    cash_gbp: float = 0.0
    contributions_gbp: float = 0.0
    fees_paid_gbp: float = 0.0
    costs_paid_gbp: float = 0.0
    positions: dict[str, Position] = field(default_factory=dict)
    pending: list[dict] = field(default_factory=list)          # {ticker, target_weight} orders queued for next close
    fills: list[Fill] = field(default_factory=list)
    last_prices: dict[str, float] = field(default_factory=dict)

    # ------------------------------------------------------------- cash
    def deposit(self, amount_gbp: float) -> None:
        self.cash_gbp += amount_gbp
        self.contributions_gbp += amount_gbp

    # ------------------------------------------------------------- valuation
    def mark_to_market(self, prices: dict[str, float]) -> None:
        self.last_prices.update({k: float(v) for k, v in prices.items() if v == v})

    def value(self, ticker: str) -> float:
        return self.positions.get(ticker, Position()).units * self.last_prices.get(ticker, 0.0)

    def nav(self) -> float:
        return self.cash_gbp + sum(self.value(t) for t in self.positions)

    def weights(self) -> dict[str, float]:
        nav = self.nav()
        return {t: self.value(t) / nav for t in self.positions if nav > 0 and self.positions[t].units > 0}

    def holdings_hash(self) -> str:
        data = {t: round(p.units, 6) for t, p in sorted(self.positions.items()) if p.units}
        return hashlib.sha1(json.dumps(data).encode()).hexdigest()[:12]

    def accrue_fund_fees(self, days: int = 1) -> None:
        for t, pos in self.positions.items():
            inst = self.catalogue.get(t)
            if inst and inst.ocf and pos.units > 0:
                fee = self.value(t) * inst.ocf * days / 365
                price = self.last_prices.get(t)
                if price:
                    pos.units -= fee / price            # fees reduce units (like an OCF drag)
                    self.fees_paid_gbp += fee

    # ------------------------------------------------------------- orders
    def queue_rebalance(self, target_weights: dict[str, float], reason: str = "") -> None:
        self.pending = [{"target_weights": target_weights, "reason": reason}]

    def fill_pending(self, date: str, prices: dict[str, float]) -> list[Fill]:
        if not self.pending:
            return []
        self.mark_to_market(prices)
        order = self.pending.pop(0)
        self.pending = []
        return self.rebalance_to(order["target_weights"], date)

    def rebalance_to(self, target_weights: dict[str, float], date: str) -> list[Fill]:
        c = params()["costs"]
        min_trade = params()["min_trade_gbp"]
        nav = self.nav()
        out: list[Fill] = []
        tickers = set(target_weights) | {t for t, p in self.positions.items() if p.units > 0}
        # sells first, then buys, so cash is available
        deltas = {t: target_weights.get(t, 0.0) * nav - self.value(t) for t in tickers}
        for t in sorted(tickers, key=lambda k: deltas[k]):
            amount = deltas[t]
            price = self.last_prices.get(t)
            if not price or abs(amount) < min_trade:
                continue
            inst = self.catalogue.get(t)
            rate = c["trade"] + (c["fx"] if inst and inst.currency == "USD" else 0.0)
            cost = abs(amount) * rate
            pos = self.positions.setdefault(t, Position())
            units = amount / price
            if amount < 0:  # sell
                units = max(units, -pos.units)
                avg = pos.cost_basis_gbp / pos.units if pos.units else 0
                pos.realised_pnl_gbp += -units * (price - avg)
                pos.cost_basis_gbp += units * avg
                pos.units += units
                self.cash_gbp += -units * price - cost
            else:  # buy
                spend = min(amount, max(self.cash_gbp - cost, 0))
                units = spend / price
                pos.units += units
                pos.cost_basis_gbp += spend
                self.cash_gbp -= spend + cost
            self.costs_paid_gbp += cost
            fill = Fill(date=date, ticker=t, action="buy" if amount > 0 else "sell", units=round(units, 6),
                        price_gbp=round(price, 4), amount_gbp=round(abs(units * price), 2), cost_gbp=round(cost, 2))
            self.fills.append(fill)
            out.append(fill)
        return out

    # ------------------------------------------------------------- P&L
    def pnl_rows(self) -> list[dict]:
        rows = []
        nav = self.nav() or 1
        for t, pos in self.positions.items():
            value = self.value(t)
            unreal = value - pos.cost_basis_gbp
            rows.append({
                "ticker": t, "units": pos.units, "value_gbp": value, "cost_basis_gbp": pos.cost_basis_gbp,
                "unrealised_pnl_gbp": unreal,
                "unrealised_pnl_pct": unreal / pos.cost_basis_gbp if pos.cost_basis_gbp else 0.0,
                "realised_pnl_gbp": pos.realised_pnl_gbp,
                "contribution_to_return": (unreal + pos.realised_pnl_gbp) / nav,
            })
        return rows
