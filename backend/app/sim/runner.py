"""Day-by-day simulator. Owner: Cem. Spec: docs/03-how-it-works.md §3.

SCAFFOLD: deterministic loop skeleton (clock, fills, mark-to-market, contributions, tick events) runs end to end.
TODO(issues): monitors + cooldowns, review schedule, agent runs via supervisor, approvals, benchmarks, CLI flags.

    python -m app.sim.runner --start 2026-07-07 --end 2026-07-31 [--agents] [--approvals batch_policy]
"""
from __future__ import annotations

import argparse
import asyncio

from app.config import params
from app.container import AppState, build_state
from app.engine.portfolio import record_checkpoint


async def run(state: AppState, start: str, end: str | None, targets: dict[str, float], agents: bool = False) -> None:
    prm = params()
    clock, gw, led, ev = state.clock, state.gw, state.ledger, state.events
    days = gw.trading_days(start, end)
    led.deposit(prm["sim"]["capital_gbp"])
    last_month = None
    for i, day in enumerate(days):
        clock.set(day.date())  # type: ignore[attr-defined]
        prices = gw.latest_prices().to_dict()
        led.fill_pending(str(day.date()), prices)
        led.mark_to_market(prices)
        led.accrue_fund_fees()
        if i == 0:
            led.queue_rebalance(targets, "initial portfolio")
        if last_month is not None and day.month != last_month:
            led.deposit(prm["sim"]["monthly_contribution_gbp"])
            led.queue_rebalance(targets, "invest contribution")  # TODO(#sim): invest pro rata, not full rebalance
        last_month = day.month
        # TODO(#monitors): hits = monitors.evaluate(...); cooldowns; review schedule
        # TODO(#sim-agents): if review/trigger and agents: await state.supervisor.start(kind, trigger_text)
        # TODO(#benchmarks): step benchmarks
        record_checkpoint(state.db, clock.mode, led, clock.as_of_str(), targets)
        ev.emit("clock.tick", title=f"{day.date()} NAV £{led.nav():,.0f}",
                payload={"nav_gbp": round(led.nav(), 2), "weights": led.weights(), "benchmarks": {},
                         "status": "monitoring_normally"})


def main() -> None:  # pragma: no cover
    p = argparse.ArgumentParser()
    p.add_argument("--start", default=params()["sim"]["start"])
    p.add_argument("--end", default=None)
    p.add_argument("--agents", action="store_true")
    a = p.parse_args()
    state = build_state()
    # placeholder targets until construction runs: equal-weight two ETFs
    targets = {"VWRP.LSE": 0.6, "VAGS.LSE": 0.37}
    asyncio.run(run(state, a.start, a.end, targets, agents=a.agents))
    print(f"Done. NAV £{state.ledger.nav():,.2f}")


if __name__ == "__main__":  # pragma: no cover
    main()
