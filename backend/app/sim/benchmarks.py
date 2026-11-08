"""Benchmark strategies run in lockstep with ours (same contributions + costs). Owner: Cem."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.engine.ledger import Ledger
from app.schemas import Instrument


@dataclass
class Benchmark:
    name: str
    ledger: Ledger
    targets: dict[str, float]
    rule: str                                   # "none" | "quarterly" | "trigger_5pct"
    nav_series: list[tuple[str, float]] = field(default_factory=list)
    _last_quarter: tuple[int, int] | None = None

    def step(self, date: str, prices: dict[str, float], contribution: float, fired: bool) -> None:
        """Same contributions and cost model as ours. Contributions are always invested (buys only):
        buy-and-hold in proportion to what it already holds, the others by their targets. Only the
        strategy's own rule ever rebalances: quarterly at a new quarter, mechanical_5pct when a trigger fires."""
        self.ledger.mark_to_market(prices)
        if contribution:
            self.ledger.deposit(contribution)
            base = self._holdings_mix() if self.rule == "none" else self.targets
            self.ledger.rebalance_to(self._invest(contribution, base), date)
        y, m = int(date[:4]), int(date[5:7])
        q = (y, (m - 1) // 3)
        if self.rule == "quarterly" and self._last_quarter is not None and q != self._last_quarter:
            self.ledger.rebalance_to(self.targets, date)
        if self.rule == "trigger_5pct" and fired:
            self.ledger.rebalance_to(self.targets, date)
        self._last_quarter = q
        self.nav_series.append((date, round(self.ledger.nav(), 2)))

    def _holdings_mix(self) -> dict[str, float]:
        vals = {t: self.ledger.value(t) for t, p in self.ledger.positions.items() if p.units > 0}
        total = sum(vals.values())
        return {t: v / total for t, v in vals.items()} if total else self.targets

    def _invest(self, amount: float, mix: dict[str, float]) -> dict[str, float]:
        """Target weights that keep current holdings and add `amount` split by `mix` (so only buys happen).
        (The old pro-rata version targeted the current weights, which already include the new cash: no trades.)"""
        nav = self.ledger.nav()
        out = {t: self.ledger.value(t) / nav for t, p in self.ledger.positions.items() if p.units > 0}
        total = sum(mix.values()) or 1.0
        for t, w in mix.items():
            out[t] = out.get(t, 0.0) + amount * (w / total) * self._invested_share() / nav
        return out

    def _invested_share(self) -> float:
        """Invest the same share of new money as the target keeps invested (the rest stays as its cash buffer)."""
        return min(sum(self.targets.values()), 1.0) if self.targets else 1.0


def make_benchmarks(catalogue: dict[str, Instrument], targets: dict[str, float], capital: float, date: str,
                    prices: dict[str, float], global_etf: str) -> list[Benchmark]:
    out = []
    for name, tg, rule in [
        ("buy_and_hold", targets, "none"),
        ("quarterly_rebalance", targets, "quarterly"),
        ("global_etf", {global_etf: 1.0}, "none"),
        ("mechanical_5pct", targets, "trigger_5pct"),
    ]:
        led = Ledger(catalogue=catalogue)
        led.deposit(capital)
        led.mark_to_market(prices)
        led.rebalance_to(tg, date)
        out.append(Benchmark(name=name, ledger=led, targets=tg, rule=rule))
    return out
