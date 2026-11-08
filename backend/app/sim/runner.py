"""Day-by-day simulator. Owner: Cem. Spec: docs/03-how-it-works.md §3–4, docs/07 §6–7.

Decide at day t's close, fill at day t+1's close. Every day: fills → mark-to-market → fees → contribution →
monitors (+ cooldowns) → review / trigger run → benchmarks → clock.tick.

Engine-only (`--no-agents`, the default): on review and trigger days the optimiser recomputes the target and
the portfolio trades only if a holding or asset class is outside the drift band (or over a cap). This is the
`ours_no_agents` baseline. With `--agents` the run is handed to the supervisor (decisions → orders in #22).

    python -m app.sim.runner --start 2026-07-07 --end 2026-11-06 [--agents | --no-agents] [--profile balanced]
                             [--approvals batch_policy] [--record runs/no_agents.sqlite]
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from app.config import params
from app.container import AppState, build_state
from app.engine import optimiser, risk
from app.engine.portfolio import record_checkpoint
from app.monitors import rules
from app.monitors.cooldowns import Cooldowns, describe, primary_kind
from app.profile.quiz import mandate_for
from app.sim.benchmarks import Benchmark, make_benchmarks

CORR_WINDOW = 252        # trading days of returns for the correlation-regime check
CORR_LAG = 126           # "6 months earlier"


@dataclass
class SimResult:
    start: str
    end: str
    days: int = 0
    nav_series: list[tuple[str, float]] = field(default_factory=list)
    runs: list[dict] = field(default_factory=list)              # {date, kind, text, action}
    trigger_counts: Counter = field(default_factory=Counter)    # acted-on hits per kind (+ "folded", "review")
    fills: int = 0
    benchmarks: dict[str, float] = field(default_factory=dict)
    final_nav: float = 0.0
    contributions_gbp: float = 0.0


def build_targets(state: AppState, current: dict[str, float] | None = None) -> dict[str, float]:
    """Engine target: the optimiser's recommended portfolio from data up to the clock (no LLM)."""
    insts = state.gw.catalogue()
    lb = params()["optimiser"]["lookback"]
    px = state.gw.prices([i.ticker for i in insts], caller="sim.targets").tail(lb + 1)
    cov = risk.covariance(risk.log_returns(px))
    res = optimiser.optimise(optimiser.OptimiseRequest(mandate=state.mandate, instruments=insts, cov=cov,
                                                       current_weights=current or {}, mu=_forecast_mu(state)))
    if res.status != "optimal":
        raise RuntimeError(f"Optimiser could not build a target: {res.binding_constraints}")
    return res.weights


def _forecast_mu(state: AppState) -> pd.Series | None:
    """2-week walk-forward estimate (#73). Until engine/forecast.py exists, no forecast term is used."""
    try:
        from app.engine import forecast  # type: ignore[attr-defined]
    except ImportError:
        return None
    tickers = [i.ticker for i in state.gw.catalogue()]
    out = forecast.forecast(state.gw, tickers, state.clock.as_of_str())
    state.events.emit("calc.result", title="2-week estimate (not a promise)",   # traceable, like the agent tool
                      payload={"name": "forecast_2w", "inputs": {"tickers": tickers, "horizon": out.horizon_days},
                               "outputs": {"mu": out.mu, "portfolio": out.portfolio.model_dump() if out.portfolio else None,
                                           "skipped": out.skipped, "label": out.label}})
    return pd.Series(out.mu, dtype=float)


def _avg_corr(px: pd.DataFrame) -> float | None:
    rets = risk.log_returns(px)
    if px.shape[1] < 2 or len(rets) < 20:
        return None
    corr = risk.correlation_from_cov(risk.covariance(rets)).values
    iu = np.triu_indices(len(corr), k=1)
    return float(corr[iu].mean())


def corr_regime(state: AppState, held: list[str]) -> list[rules.Hit]:
    """Average pairwise correlation of holdings now vs 6 months earlier (informs the review only)."""
    if len(held) < 2:
        return []
    px = state.gw.prices(held, caller="sim.corr_regime")
    now = _avg_corr(px.tail(CORR_WINDOW + 1))
    then = _avg_corr(px.iloc[: -CORR_LAG].tail(CORR_WINDOW + 1)) if len(px) > CORR_LAG + 20 else None
    if now is None:
        return []
    return rules.corr_regime_hit(now, then, params()["triggers"]["corr_jump"])


def _invest_contribution(weights_value: dict[str, float], nav_after: float, amount: float,
                         targets: dict[str, float]) -> dict[str, float]:
    """Target weights that leave holdings as they are and spread the new cash by the targets (buys only)."""
    out = {t: v / nav_after for t, v in weights_value.items()}
    for t, w in targets.items():
        out[t] = out.get(t, 0.0) + amount * w / nav_after
    return out


async def run(state: AppState, start: str, end: str | None = None, agents: bool = False,
              targets: dict[str, float] | None = None, approvals: str = "manual") -> SimResult:
    prm, trg = params(), params()["triggers"]
    clock, gw, led, ev = state.clock, state.gw, state.ledger, state.events
    days = gw.trading_days(start, end)
    if not days:
        raise ValueError(f"No trading days between {start} and {end}")
    if led.contributions_gbp or led.pending or any(p.units for p in led.positions.values()):
        raise ValueError("run() needs a fresh ledger: this one already has money in it (build a new state)")
    n_review = state.mandate.review_every_n_days
    cool = Cooldowns(prm["cooldown_days"], prm["fold_into_review_days"])
    res = SimResult(start=str(days[0].date()), end=str(days[-1].date()), days=len(days))
    bench: list[Benchmark] = []
    prev_prices: dict[str, float] = {}
    review_prices: dict[str, float] = {}
    nav_at_last_review: float | None = None
    prev_day: pd.Timestamp | None = None
    led.deposit(prm["sim"]["capital_gbp"])

    for i, day in enumerate(days):
        date = str(day.date())
        clock.set(date)
        # fees as known today (e.g. VWRP's OCF cut on 28 Jul 2026); benchmarks share this dict
        led.catalogue.update({i.ticker: i for i in gw.catalogue(eligible_only=False)})
        prices = {k: float(v) for k, v in gw.latest_prices().items() if pd.notna(v)}
        for f in led.fill_pending(date, prices):
            res.fills += 1
            ev.emit("order.filled", title=f"{f.action.capitalize()} {f.ticker} £{f.amount_gbp:,.0f}",
                    payload={"ticker": f.ticker, "action": f.action, "units": f.units, "price_gbp": f.price_gbp,
                             "amount_gbp": f.amount_gbp, "cost_gbp": f.cost_gbp})
        led.mark_to_market(prices)
        if prev_day is not None:  # OCF accrues per calendar day, not per trading day
            led.accrue_fund_fees(days=(day - prev_day).days)

        contribution = 0.0
        if prev_day is not None and day.month != prev_day.month:
            contribution = float(prm["sim"]["monthly_contribution_gbp"])
            led.deposit(contribution)
            if nav_at_last_review is not None:  # new money is not a gain: don't let it hide a NAV drop
                nav_at_last_review += contribution
            if not led.pending and targets:
                values = {t: led.value(t) for t in led.positions if led.positions[t].units > 0}
                led.queue_rebalance(_invest_contribution(values, led.nav(), contribution, targets),
                                    "invest contribution")

        status = "monitoring_normally"
        if i == 0:
            targets = targets or build_targets(state)
            led.queue_rebalance(targets, "initial portfolio")
            res.runs.append({"date": date, "kind": "construction", "text": "Initial portfolio", "action": "adjust"})
            ev.emit("decision.made", title="Initial portfolio built by the engine",
                    payload={"action": "adjust", "reason": "construction"})
        invested = any(p.units > 0 for p in led.positions.values())
        bench_contribution = contribution
        if invested and not bench:  # benchmarks start on the day we are first invested, same prices
            # led.nav() already includes today's contribution, so they must not get it again in step()
            bench = make_benchmarks(led.catalogue, targets or {}, led.nav(), date, prices, prm["benchmark_global_etf"])
            bench_contribution = 0.0
            review_prices, nav_at_last_review = dict(prices), led.nav()

        if invested and i > 0:
            weights = led.weights()
            held = [t for t in weights if weights[t] > 0]
            day_ret = {t: prices[t] / prev_prices[t] - 1 for t in held if prev_prices.get(t) and t in prices}
            since = {t: prices[t] / review_prices[t] - 1 for t in held if review_prices.get(t) and t in prices}
            hits = (rules.drift_hits(weights, targets or {}, led.catalogue, trg["drift_pp"])
                    + rules.cap_hits(weights, state.mandate, led.catalogue)
                    + rules.price_move_hits(day_ret, since, trg["price_move_day"], trg["price_move_since_review"])
                    + rules.nav_drop_hit(led.nav(), nav_at_last_review, trg["nav_drop"]))
            review_day = i % n_review == 0
            # on a review day nothing is "folded into the review": the hits ARE part of it, so keep them
            days_to_review = n_review if review_day else n_review - (i % n_review)
            acted = cool.filter(hits, i, days_to_review)
            if hits and not acted and not review_day:
                res.trigger_counts["suppressed"] += 1   # in cooldown, or folded into a review due soon
            kind = None
            if review_day:
                kind, notes = "review", describe(acted) if acted else "Scheduled fortnightly review"
                notes += "".join(f"; {h.text}" for h in corr_regime(state, held))
                res.trigger_counts["review"] += 1
            elif acted:
                kind, notes = primary_kind(acted), describe(acted)
            for h in acted:
                res.trigger_counts[h.kind] += 1
                ev.emit("monitor.fired", title=h.text,
                        payload={"monitor_id": f"rule:{h.kind}", "rule": h.kind, "ticker": h.ticker,
                                 "value": round(h.value, 6), "threshold": h.threshold})
            if kind:
                status = "investigating"
                new_targets, action = await _decide(state, kind, notes, agents)
                targets = new_targets or targets
                res.runs.append({"date": date, "kind": kind, "text": notes, "action": action})
                if kind == "review":
                    review_prices, nav_at_last_review = dict(prices), led.nav()

        for b in bench:
            b_hit = bool(rules.drift_hits(b.ledger.weights(), b.targets, led.catalogue, trg["drift_pp"]))
            b.step(date, prices, bench_contribution, fired=b_hit)
        record_checkpoint(state.db, clock.mode, led, date, targets or {})
        ev.emit("clock.tick", title=f"{date} NAV £{led.nav():,.0f}",
                payload={"nav_gbp": round(led.nav(), 2), "weights": {t: round(w, 6) for t, w in led.weights().items()},
                         "benchmarks": {b.name: round(b.ledger.nav(), 2) for b in bench}, "status": status})
        res.nav_series.append((date, round(led.nav(), 2)))
        prev_prices, prev_day = prices, day

    res.final_nav = round(led.nav(), 2)
    res.contributions_gbp = round(led.contributions_gbp, 2)
    res.benchmarks = {b.name: round(b.ledger.nav(), 2) for b in bench}
    return res


async def _decide(state: AppState, kind: str, text: str, agents: bool) -> tuple[dict[str, float] | None, str]:
    """Review / trigger response: (new targets or None to keep them, action). Queues orders if it trades."""
    if agents:
        # TODO(#22): use the run's decision + proposal, gate result and approvals policy to queue orders.
        await state.supervisor.start(kind, text)
        return None, "agent_run"
    led, trg = state.ledger, params()["triggers"]
    weights = led.weights()
    try:
        new_targets = build_targets(state, current=weights)
    except RuntimeError as e:  # one bad review day must not stop a 4-month run: hold and say why
        state.events.emit("decision.made", title=f"Engine maintain ({kind})",
                          payload={"action": "maintain", "reason": f"No new target, holding as is: {e}"})
        return None, "maintain"
    outside =(rules.drift_hits(weights, new_targets, led.catalogue, trg["drift_pp"])
               or rules.cap_hits(weights, state.mandate, led.catalogue))
    action = "adjust" if outside else "maintain"
    if outside:
        led.queue_rebalance(new_targets, f"{kind}: {text}")
    reason = (f"Outside the bands: {outside[0].text}" if outside
              else "All holdings within their bands of the recomputed target")
    state.events.emit("decision.made", title=f"Engine {action} ({kind})", payload={"action": action, "reason": reason})
    return new_targets, action


def main(argv: list[str] | None = None) -> None:  # pragma: no cover
    p = argparse.ArgumentParser(description="Day-by-day simulator (docs/03 §3)")
    p.add_argument("--start", default=params()["sim"]["start"])
    p.add_argument("--end", default=params()["sim"]["end"])
    g = p.add_mutually_exclusive_group()
    g.add_argument("--agents", dest="agents", action="store_true", help="hand reviews/triggers to the supervisor")
    g.add_argument("--no-agents", dest="agents", action="store_false", help="engine-only baseline (default)")
    p.add_argument("--profile", default="balanced", choices=["cautious", "balanced", "growth", "adventurous"])
    p.add_argument("--approvals", default="manual", choices=["manual", "batch_policy"])
    p.add_argument("--record", default=None, help="SQLite file for the event log (replaced if it exists)")
    a = p.parse_args(argv)
    if a.record:
        Path(a.record).parent.mkdir(parents=True, exist_ok=True)
        Path(a.record).unlink(missing_ok=True)
    state = build_state(db_path=a.record)
    state.mandate = mandate_for(a.profile)
    r = asyncio.run(run(state, a.start, a.end, agents=a.agents, approvals=a.approvals))
    print(f"Simulated {r.days} trading days {r.start} → {r.end} ({'agents' if a.agents else 'engine only'}, "
          f"{a.profile}). Simulated results, not a forecast.")
    print(f"NAV £{r.final_nav:,.2f} from £{r.contributions_gbp:,.2f} paid in; {r.fills} fills")
    print("Triggers: " + (", ".join(f"{k} {v}" for k, v in sorted(r.trigger_counts.items())) or "none"))
    print("Decisions: " + ", ".join(f"{k} {v}" for k, v in sorted(Counter(x["action"] for x in r.runs).items())))
    for name, nav in r.benchmarks.items():
        print(f"  {name:20s} £{nav:,.2f}")


if __name__ == "__main__":  # pragma: no cover
    main()
