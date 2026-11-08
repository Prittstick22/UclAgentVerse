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

from app.config import PERSONA_FILES, params, policy
from app.container import AppState, build_state
from app.core.clock import SimClock
from app.engine import optimiser, risk
from app.engine.portfolio import record_checkpoint
from app.monitors import rules
from app.monitors.cooldowns import Cooldowns, describe, primary_kind
from app.profile.demo import demo_mandate
from app.profile.quiz import mandate_for
from app.sim import approvals as approvals_mod
from app.sim.approvals import ApprovalMode
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
    """2-week walk-forward estimate (#73). `--no-forecast` (state.forecast_off) = the lambda_return 0 ablation."""
    if getattr(state, "forecast_off", False):
        return None
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


class Simulation:
    """The day loop as a stepper, so the API can start, pause and step it (#22). `run()` drives it to the end."""

    def __init__(self, state: AppState, start: str, end: str | None = None, agents: bool = False,
                 targets: dict[str, float] | None = None, approvals: ApprovalMode = "manual"):
        self.state, self.agents, self.approvals = state, agents, approvals
        prm = params()
        led = state.ledger
        self.days = state.gw.trading_days(start, end)
        if not self.days:
            raise ValueError(f"No trading days between {start} and {end}")
        if led.contributions_gbp or led.pending or any(p.units for p in led.positions.values()):
            raise ValueError("run() needs a fresh ledger: this one already has money in it (build a new state)")
        self.targets = targets
        self.n_review = state.mandate.review_every_n_days
        self.review_change: tuple[int, int] | None = None   # (from day index, new cadence); capture fallback only
        self.cool = Cooldowns(prm["cooldown_days"], prm["fold_into_review_days"])
        self.res = SimResult(start=str(self.days[0].date()), end=str(self.days[-1].date()), days=len(self.days))
        self.bench: list[Benchmark] = []
        self.prev_prices: dict[str, float] = {}
        self.review_prices: dict[str, float] = {}
        self.nav_at_last_review: float | None = None
        self.prev_day: pd.Timestamp | None = None
        self.i = 0
        self.capital = float(prm["sim"]["capital_gbp"])
        self.flows: dict[str, float] = {}         # date -> contribution (for time-weighted returns)

    def set_review_every_from(self, date: str, n: int) -> None:
        """From `date`, review every n trading days, counted from the last regular review before it."""
        i0 = next((k for k, d in enumerate(self.days) if str(d.date()) >= date), len(self.days))
        self.review_change = (i0 - i0 % self.n_review, int(n))

    def _review_cadence(self, i: int) -> tuple[bool, int]:
        """(is today a review day, trading days until the next review)."""
        base, n = (0, self.n_review)
        if self.review_change is not None and i > self.review_change[0]:
            base, n = self.review_change
        k = (i - base) % n
        return k == 0, (n if k == 0 else n - k)

    @property
    def done(self) -> bool:
        return self.i >= len(self.days)

    @property
    def progress(self) -> float:
        return round(self.i / len(self.days), 4)

    def _news_hits(self, held: list[str]) -> list:
        """News trigger (#31): strong-event headlines on tickers we hold, since the previous sim close."""
        if self.prev_day is None or not held:
            return []
        prev_close = SimClock(str(self.prev_day.date())).now()
        return rules.news_hits(self.state.gw.news(held, caller="sim.news_trigger"), set(held), prev_close)

    async def step(self) -> None:
        """Simulate one trading day."""
        if self.done:
            return
        state, prm, trg = self.state, params(), params()["triggers"]
        clock, gw, led, ev, res = state.clock, state.gw, state.ledger, state.events, self.res
        i, day = self.i, self.days[self.i]
        date = str(day.date())
        clock.set(date)
        # fees as known today (e.g. VWRP's OCF cut on 28 Jul 2026); benchmarks share this dict
        led.catalogue.update({inst.ticker: inst for inst in gw.catalogue(eligible_only=False)})
        prices = {k: float(v) for k, v in gw.latest_prices().items() if pd.notna(v)}
        order_reason = str(led.pending[0].get("reason", "")) if led.pending else None
        fills = led.fill_pending(date, prices)
        approvals_mod.mark_executed(state, order_reason, fills)
        for f in fills:
            res.fills += 1
            ev.emit("order.filled", title=f"{f.action.capitalize()} {f.ticker} £{f.amount_gbp:,.0f}",
                    payload={"ticker": f.ticker, "action": f.action, "units": f.units, "price_gbp": f.price_gbp,
                             "amount_gbp": f.amount_gbp, "cost_gbp": f.cost_gbp})
        led.mark_to_market(prices)
        if self.prev_day is not None:  # OCF accrues per calendar day, not per trading day
            led.accrue_fund_fees(days=(day - self.prev_day).days)

        contribution = 0.0
        if self.prev_day is not None and day.month != self.prev_day.month:
            contribution = float(prm["sim"]["monthly_contribution_gbp"])
            led.deposit(contribution)
            self.flows[date] = contribution
            if self.nav_at_last_review is not None:  # new money is not a gain: don't let it hide a NAV drop
                self.nav_at_last_review += contribution
            if not led.pending and self.targets:
                values = {t: led.value(t) for t in led.positions if led.positions[t].units > 0}
                led.queue_rebalance(_invest_contribution(values, led.nav(), contribution, self.targets),
                                    "invest contribution")

        status = "monitoring_normally"
        if i == 0:
            status = "investigating"
            await self._construct(date)
        invested = any(p.units > 0 for p in led.positions.values())
        bench_contribution = contribution
        if invested and not self.bench:  # benchmarks start on the day we are first invested, same prices
            # led.nav() already includes today's contribution, so they must not get it again in step()
            # same money in as ours (not our NAV after our trading costs: they pay their own)
            self.bench = make_benchmarks(led.catalogue, self.targets or {}, led.contributions_gbp, date, prices,
                                         prm["benchmark_global_etf"])
            bench_contribution = 0.0
            self.review_prices, self.nav_at_last_review = dict(prices), led.nav()

        if invested and i > 0:
            weights = led.weights()
            held = [t for t in weights if weights[t] > 0]
            day_ret = {t: prices[t] / self.prev_prices[t] - 1 for t in held if self.prev_prices.get(t) and t in prices}
            since = {t: prices[t] / self.review_prices[t] - 1 for t in held
                     if self.review_prices.get(t) and t in prices}
            hits = (rules.drift_hits(weights, self.targets or {}, led.catalogue, trg["drift_pp"])
                    + rules.cap_hits(weights, state.mandate, led.catalogue)
                    + rules.price_move_hits(day_ret, since, trg["price_move_day"], trg["price_move_since_review"])
                    + rules.nav_drop_hit(led.nav(), self.nav_at_last_review, trg["nav_drop"])
                    + self._news_hits(held))
            # on a review day nothing is "folded into the review": the hits ARE part of it, so keep them
            review_day, days_to_review = self._review_cadence(i)
            acted = self.cool.filter(hits, i, days_to_review)
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
                new_targets, action = await _decide(state, kind, notes, self.agents, self.approvals)
                self.targets = new_targets or self.targets
                res.runs.append({"date": date, "kind": kind, "text": notes, "action": action})
                if kind == "review":
                    self.review_prices, self.nav_at_last_review = dict(prices), led.nav()
        if any(p.status == "awaiting_approval" for p in state.proposals.values()):
            status = "awaiting_approval"

        for b in self.bench:
            b_hit = bool(rules.drift_hits(b.ledger.weights(), b.targets, led.catalogue, trg["drift_pp"]))
            b.step(date, prices, bench_contribution, fired=b_hit)
        record_checkpoint(state.db, clock.mode, led, date, self.targets or {})
        ev.emit("clock.tick", title=f"{date} NAV £{led.nav():,.0f}",
                payload={"nav_gbp": round(led.nav(), 2), "weights": {t: round(w, 6) for t, w in led.weights().items()},
                         "benchmarks": {b.name: round(b.ledger.nav(), 2) for b in self.bench}, "status": status})
        res.nav_series.append((date, round(led.nav(), 2)))
        self.prev_prices, self.prev_day = prices, day
        self.i += 1
        if self.done:
            res.final_nav = round(led.nav(), 2)
            res.contributions_gbp = round(led.contributions_gbp, 2)
            res.benchmarks = {b.name: round(b.ledger.nav(), 2) for b in self.bench}
            save_results(self)

    async def _construct(self, date: str) -> None:
        """Day 0: the starting portfolio. Agents build it (construction run + proposal + approval policy);
        the engine builds it in --no-agents mode, or as a labelled fallback if the agent run yields nothing."""
        state, ev, led = self.state, self.state.events, self.state.ledger
        if not self.agents:
            led.deposit(self.capital)
        if self.targets:
            if self.agents:
                led.deposit(self.capital)
            led.queue_rebalance(self.targets, "initial portfolio (given)")
            self.res.runs.append({"date": date, "kind": "construction", "text": "Initial portfolio (given)",
                                  "action": "adjust"})
            return
        if self.agents:
            text = f"Build a starting portfolio for a {state.mandate.profile} investor"
            # capital is paid in after the agents propose, so the proposal is labelled a construction
            targets, action = await _agent_run(state, "construction", text, self.approvals, construction=True)
            led.deposit(self.capital)
            self.res.runs.append({"date": date, "kind": "construction", "text": text, "action": action})
            if targets:
                self.targets = targets
                led.queue_rebalance(targets, _last_approved_key(state))
                return
            if action == "awaiting_approval":
                return   # manual mode: stays in cash until the user approves (#23)
            reason = f"Agent construction ended '{action}', so the engine built the starting portfolio"
        else:
            reason = "construction"
        try:
            self.targets = build_targets(state)
        except RuntimeError as e:
            ev.emit("decision.made", title="No starting portfolio", payload={"action": "maintain", "reason": str(e)})
            return
        led.queue_rebalance(self.targets, "initial portfolio")
        if not self.agents:
            self.res.runs.append({"date": date, "kind": "construction", "text": "Initial portfolio", "action": "adjust"})
        ev.emit("decision.made", title="Initial portfolio built by the engine", payload={"action": "adjust",
                                                                                         "reason": reason})

    async def run_to_end(self) -> SimResult:
        while not self.done:
            await self.step()
        return self.res


RESULTS_NS = "sim_results"


def _strategy(series: list[tuple[str, float]], flows: dict[str, float], ledger) -> dict:
    fills = ledger.fills
    initial = fills[0].date if fills else None          # the initial build from cash is not "turnover"
    return {"series": [{"date": d, "nav_gbp": v} for d, v in series], "flows": flows,
            "costs_gbp": round(ledger.costs_paid_gbp, 2), "fees_gbp": round(ledger.fees_paid_gbp, 2),
            "trades": len(fills), "traded_gbp": round(sum(f.amount_gbp for f in fills if f.date != initial), 2)}


def save_results(sim: Simulation) -> dict:
    """Everything the evaluation (#24) and /api/benchmarks need, stored in the run's own SQLite (kv)."""
    import json

    state, res = sim.state, sim.res
    strategies = {"ours": _strategy(res.nav_series, sim.flows, state.ledger)}
    for b in sim.bench:
        # every strategy starts from the same cash on day 0, so day 1's return includes its own build costs
        series = b.nav_series if b.nav_series and b.nav_series[0][0] == res.start else \
            [(res.start, round(sim.capital, 2)), *b.nav_series]
        strategies[b.name] = _strategy(series, sim.flows, b.ledger)
    out = {"start": res.start, "end": res.end, "days": res.days, "agents": sim.agents, "approvals": sim.approvals,
           "forecast": not getattr(state, "forecast_off", False),
           "profile": state.mandate.profile, "lambda_return": params()["forecast"]["lambda_return"],
           "data_source": state.gw.snapshot.source_label, "runs": res.runs,
           "trigger_counts": dict(res.trigger_counts), "strategies": strategies}
    state.db.put(RESULTS_NS, "latest", json.dumps(out))
    return out


async def run(state: AppState, start: str, end: str | None = None, agents: bool = False,
              targets: dict[str, float] | None = None, approvals: ApprovalMode = "manual") -> SimResult:
    return await Simulation(state, start, end, agents, targets, approvals).run_to_end()


def _last_approved_key(state: AppState) -> str:
    """Order key of the proposal the batch policy just approved, so it is marked 'executed' when it fills."""
    approved = [p for p in state.proposals.values() if p.status == "approved"]
    return f"proposal:{approved[-1].id}" if approved else "approved proposal"


async def _agent_run(state: AppState, kind: str, text: str, approvals: ApprovalMode, construction: bool = False
                     ) -> tuple[dict[str, float] | None, str]:
    """Hand the day to the supervisor; turn an 'adjust' decision with a proposal into orders via the policy."""
    try:
        run = await state.supervisor.start(kind, text)
    except Exception as e:  # noqa: BLE001 - a crashed agent run must not stop the simulation
        state.events.emit("decision.made", title=f"Agent run failed ({kind}); holding",
                          payload={"action": "maintain", "reason": f"agent run failed: {type(e).__name__}"})
        return None, "agent_failed"
    action = run.decision.action if run.decision else "investigate_further"
    prop = state.proposals.get(run.proposal_id) if run.proposal_id else None
    if prop is None:
        return None, action if action != "adjust" else "adjust_without_proposal"
    if action not in ("adjust",) and not construction:
        return None, action
    return approvals_mod.handle(state, prop, approvals, construction=construction)


async def _decide(state: AppState, kind: str, text: str, agents: bool, approvals: ApprovalMode = "manual"
                  ) -> tuple[dict[str, float] | None, str]:
    """Review / trigger response: (new targets or None to keep them, action). Queues orders if it trades."""
    led = state.ledger
    if agents:
        targets, action = await _agent_run(state, kind, text, approvals)
        if targets:
            led.queue_rebalance(targets, _last_approved_key(state))
        return targets, action
    trg = params()["triggers"]
    weights = led.weights()
    try:
        new_targets = build_targets(state, current=weights)
    except RuntimeError as e:  # one bad review day must not stop a 4-month run: hold and say why
        state.events.emit("decision.made", title=f"Engine maintain ({kind})",
                          payload={"action": "maintain", "reason": f"No new target, holding as is: {e}"})
        return None, "maintain"
    outside = (rules.drift_hits(weights, new_targets, led.catalogue, trg["drift_pp"])
               or rules.cap_hits(weights, state.mandate, led.catalogue))
    action = "adjust" if outside else "maintain"
    if outside:
        led.queue_rebalance(new_targets, f"{kind}: {text}")
    reason = (f"Outside the bands: {outside[0].text}" if outside
              else "All holdings within their bands of the recomputed target")
    state.events.emit("decision.made", title=f"Engine {action} ({kind})", payload={"action": action, "reason": reason})
    return new_targets, action


def main(argv: list[str] | None = None) -> None:  # pragma: no cover
    p = argparse.ArgumentParser(description="Day-by-day simulator (docs/03 section 3)")
    p.add_argument("--start", default=params()["sim"]["start"])
    p.add_argument("--end", default=params()["sim"]["end"])
    g = p.add_mutually_exclusive_group()
    g.add_argument("--agents", dest="agents", action="store_true", help="hand reviews/triggers to the supervisor")
    g.add_argument("--no-agents", dest="agents", action="store_false", help="engine-only baseline (default)")
    p.add_argument("--profile", default=None, choices=list(policy()),
                   help="default: the persona's profile (Priya = balanced, Caroline = aggressive)")
    p.add_argument("--persona", default="priya", choices=list(PERSONA_FILES),
                   help="whose fixed demo mandate to record (default priya; the recorded demo)")
    p.add_argument("--approvals", default="manual", choices=["manual", "batch_policy"])
    p.add_argument("--no-agent-views", action="store_true",
                   help="ablation: agents may not nudge the forecast with views (#74); params stay frozen")
    p.add_argument("--no-forecast", action="store_true",
                   help="ablation: no 2-week forecast term (same as forecast.lambda_return 0); params stay frozen")
    p.add_argument("--record", default=None, help="SQLite file for the event log (replaced if it exists)")
    a = p.parse_args(argv)
    if a.record:
        Path(a.record).parent.mkdir(parents=True, exist_ok=True)
        Path(a.record).unlink(missing_ok=True)
    state = build_state(db_path=a.record)
    persona_mandate = demo_mandate(a.persona)
    a.profile = a.profile or persona_mandate.profile
    state.mandate = persona_mandate if a.profile == persona_mandate.profile else mandate_for(a.profile)
    state.db.put("sim_mandate", "initial", state.mandate.model_dump_json())
    state.forecast_off = a.no_forecast
    state.views_off = a.no_agent_views
    r = asyncio.run(run(state, a.start, a.end, agents=a.agents, approvals=a.approvals))
    print(f"Simulated {r.days} trading days {r.start} to {r.end} ({'agents' if a.agents else 'engine only'}, "
          f"{a.profile}). Simulated results, not a forecast.")
    print(f"NAV GBP {r.final_nav:,.2f} from GBP {r.contributions_gbp:,.2f} paid in; {r.fills} fills")
    print("Triggers: " + (", ".join(f"{k} {v}" for k, v in sorted(r.trigger_counts.items())) or "none"))
    print("Decisions: " + ", ".join(f"{k} {v}" for k, v in sorted(Counter(x["action"] for x in r.runs).items())))
    for name, nav in r.benchmarks.items():
        print(f"  {name:20s} GBP {nav:,.2f}")


if __name__ == "__main__":  # pragma: no cover
    main()
