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
        self.ledger.mark_to_market(prices)
        if contribution:
            self.ledger.deposit(contribution)
            if self.rule == "none":       # buy-and-hold: invest the contribution pro rata
                self.ledger.rebalance_to(self._pro_rata_targets(), date)
        y, m = int(date[:4]), int(date[5:7])
        q = (y, (m - 1) // 3)
        if self.rule == "quarterly" and self._last_quarter is not None and q != self._last_quarter:
            self.ledger.rebalance_to(self.targets, date)
        if self.rule == "trigger_5pct" and fired:
            self.ledger.rebalance_to(self.targets, date)
        if self.rule == "quarterly" and contribution:
            self.ledger.rebalance_to(self.targets, date)
        self._last_quarter = q
        self.nav_series.append((date, round(self.ledger.nav(), 2)))

    def _pro_rata_targets(self) -> dict[str, float]:
        return self.ledger.weights() or self.targets


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
