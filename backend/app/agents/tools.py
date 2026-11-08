"""Tool registry: our code, exposed to agents. Every call emits tool.call / tool.result. Owner: Dev.

Every tool goes through DataGateway (as_of-enforced) and the engine; no numbers are made up here. Calc tools emit
`calc.result` and return its id (`calc:<event id>`) as evidence. Spec: docs/05-agent-system.md §5.

Weights arguments: tools that take a portfolio accept `weights` ({ticker: weight}), or `option` (a label from
`build_options`: recommended | lower_cost | lower_risk), and otherwise use the current holdings.
"""
from __future__ import annotations

import copy
import hashlib
import json
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pandas as pd

from app.agents.guard import scan
from app.agents.roles import ROLES
from app.agents.schemas import InvestmentCase
from app.config import params
from app.core.events import EventBus
from app.data.gateway import AsOfViolation, DataGateway
from app.engine import backtest as bt
from app.engine import checker, exposure, optimiser, risk
from app.engine.ledger import Ledger
from app.schemas import DecisionCard, OptionStats, OrderChange, PortfolioOption, Proposal, ProposedHolding

ToolFn = Callable[["ToolContext", dict, Any], Awaitable[dict]]
VARIANTS = ("recommended", "lower_cost", "lower_risk")
MARKET = "VWRP.LSE"          # global equity ETF used as the market for beta


@dataclass
class ToolContext:
    gw: DataGateway
    events: EventBus
    state: Any            # app.container.AppState (mandate, ledger, db…); typed loosely to avoid import cycles


class ToolRegistry:
    def __init__(self, ctx: ToolContext):
        self.ctx = ctx
        self._tools: dict[str, ToolFn] = {}

    def register(self, name: str, fn: ToolFn) -> None:
        self._tools[name] = fn

    async def call(self, name: str, args: dict, *, role: str, run: Any, agent: dict) -> dict:
        ev = self.ctx.events
        if name not in ROLES[role].tools:
            ev.emit("tool.result", title=f"{name} not allowed for {role}", status="denied",
                    payload={"tool": name, "ok": False, "summary": "tool not allowed for role"}, **agent)
            return {"ok": False, "error": "tool_not_allowed"}
        ev.emit("tool.call", title=f"{name}", status="running", payload={"tool": name, "args": args}, **agent)
        fn = self._tools.get(name, _not_implemented(name))
        try:
            out = await fn(self.ctx, args, run)
        except AsOfViolation as e:
            out = {"ok": False, "error": "asof_violation", "summary": str(e)}
        except Exception as e:  # noqa: BLE001 - tools must never crash a run
            out = {"ok": False, "error": type(e).__name__, "summary": str(e)[:200]}
        ev.emit("tool.result", title=f"{name}: {out.get('summary', 'ok')}"[:120], status="ok" if out.get("ok") else "failed",
                evidence_ids=out.get("evidence_ids", []),
                payload={"tool": name, "ok": out.get("ok", False), "summary": out.get("summary", "")}, **agent)
        return out


def _not_implemented(name: str) -> ToolFn:
    async def fn(ctx: ToolContext, args: dict, run: Any) -> dict:
        return {"ok": False, "error": "not_implemented", "summary": f"{name} is not implemented yet (see issues)"}
    return fn


# ---------------------------------------------------------------------- helpers
def _run_id(run: Any) -> str | None:
    return getattr(run, "run_id", None)


def _calc(ctx: ToolContext, run: Any, name: str, inputs: dict, outputs: dict, title: str) -> str:
    ev = ctx.events.emit("calc.result", run_id=_run_id(run), title=title,
                         payload={"name": name, "inputs": inputs, "outputs": outputs})
    return f"calc:{ev.id}"


def _r(x: float | None, nd: int = 4) -> float | None:
    return None if x is None or pd.isna(x) else round(float(x), nd)


def _scratch(run: Any) -> dict:
    return getattr(run, "scratch", None) if getattr(run, "scratch", None) is not None else {}


def _weights_from(ctx: ToolContext, args: dict, run: Any) -> tuple[dict[str, float], float, str]:
    """(weights, cash_weight, label) from `weights`, an `option` label, or the current holdings."""
    if isinstance(args.get("weights"), dict) and args["weights"]:
        w = {str(k): float(v) for k, v in args["weights"].items()}
        cash = float(args.get("cash_weight", max(0.0, 1.0 - sum(w.values()))))
        return w, cash, "given weights"
    label = args.get("option")
    if label:
        opt = _scratch(run).get("options", {}).get(label)
        if opt is None:
            raise ValueError(f"no option '{label}': call build_options first")
        return {h.ticker: h.weight for h in opt.holdings}, opt.cash_weight, label
    w = ctx.state.ledger.weights()
    if not w:
        raise ValueError("no current holdings: pass `weights` or an `option` label")
    return w, max(0.0, 1.0 - sum(w.values())), "current holdings"


def _capital(ctx: ToolContext) -> float:
    nav = ctx.state.ledger.nav()
    return nav if nav > 0 else float(params()["sim"]["capital_gbp"])


def _cov(ctx: ToolContext, tickers: list[str], caller: str) -> pd.DataFrame:
    p = params()["optimiser"]
    prices = ctx.gw.prices(tickers, caller=caller).tail(p["lookback"] + 1)
    return risk.covariance(risk.log_returns(prices))


def _lookback_start(ctx: ToolContext, days: int) -> str:
    idx = ctx.gw.prices(caller="lookback").index
    return str(idx[max(0, len(idx) - days - 1)].date())


def _forecast_mu(ctx: ToolContext, run: Any, tickers: list[str]) -> tuple[pd.Series | None, str | None]:
    """Engine 2-week forecast (#73) for the optimiser's bounded tilt; None if the module is missing."""
    try:
        from app.engine import forecast as fc
    except ImportError:
        return None, None
    res = fc.forecast(ctx.gw, tickers, ctx.gw.clock.as_of_str())
    eid = _calc(ctx, run, "forecast_2w", {"tickers": tickers, "horizon": res.horizon_days},
                {"mu": res.mu, "skipped": res.skipped, "label": res.label}, "2-week estimate (not a promise)")
    return (pd.Series(res.mu, dtype=float) if res.mu else None), eid


def _trades(ctx: ToolContext, target: dict[str, float]) -> tuple[list[OrderChange], float, float]:
    """Trade list, cost £ and turnover, by replaying the rebalance on a throwaway copy of the ledger (engine code)."""
    led: Ledger = ctx.state.ledger
    trial = copy.deepcopy(led) if led.nav() > 0 else Ledger(catalogue=led.catalogue)
    if trial.nav() <= 0:
        trial.deposit(_capital(ctx))
    trial.mark_to_market(ctx.gw.latest_prices().to_dict())
    before = trial.weights()
    fills = trial.rebalance_to(target, ctx.gw.clock.as_of_str())
    changes = [OrderChange(ticker=f.ticker, action=f.action, amount_gbp=f.amount_gbp,
                           from_weight=round(before.get(f.ticker, 0.0), 4), to_weight=round(target.get(f.ticker, 0.0), 4))
               for f in fills]
    keys = set(target) | set(before)
    turnover = sum(abs(target.get(k, 0.0) - before.get(k, 0.0)) for k in keys) / 2
    return changes, round(sum(f.cost_gbp for f in fills), 2), round(turnover, 4)


def _round_w(w: dict[str, float]) -> dict[str, float]:
    return {k: round(v, 4) for k, v in sorted(w.items(), key=lambda kv: -kv[1])}


# ---------------------------------------------------------------------- data tools
async def get_catalogue(ctx: ToolContext, args: dict, run: Any) -> dict:
    items = [i.model_dump(include={"ticker", "name", "asset_class", "sleeve", "ocf", "kind"}) for i in ctx.gw.catalogue()]
    return {"ok": True, "summary": f"{len(items)} eligible instruments", "items": items, "evidence_ids": ["catalogue"]}


async def get_prices(ctx: ToolContext, args: dict, run: Any) -> dict:
    tickers = args.get("tickers") or [i.ticker for i in ctx.gw.catalogue()]
    df = ctx.gw.prices(tickers, start=args.get("start"), end=args.get("end"), caller="tool.get_prices").ffill()
    rets = risk.log_returns(df)
    rows = []
    for t in tickers:
        s = df[t].dropna()
        if s.empty:
            continue

        def ret(n: int, s=s) -> float | None:
            return _r(s.iloc[-1] / s.iloc[-1 - n] - 1) if len(s) > n else None
        rows.append({"ticker": t, "last_gbp": _r(s.iloc[-1], 2), "last_date": str(s.index[-1].date()),
                     "ret_1m": ret(21), "ret_3m": ret(63), "ret_1y": ret(252),
                     "vol_annual": _r(rets[t].tail(252).std() * (risk.TRADING_DAYS ** 0.5))})
    eid = _calc(ctx, run, "price_summary", {"tickers": tickers, "start": args.get("start"), "end": args.get("end")},
                {"rows": rows}, f"Price summary for {len(rows)} instruments")
    return {"ok": True, "summary": f"price summary for {len(rows)} instruments (GBP, adjusted)", "rows": rows,
            "evidence_ids": [eid]}


async def correlation_lattice(ctx: ToolContext, args: dict, run: Any) -> dict:
    tickers = args.get("tickers") or [i.ticker for i in ctx.gw.catalogue()][:10]
    prices = ctx.gw.prices(tickers, caller="tool.correlation_lattice")
    rep = risk.correlation_report(prices, ctx.gw.clock.as_of_str(), args.get("lookback"))
    eid = _calc(ctx, run, "correlation_lattice", {"tickers": tickers, "lookback": rep.lookback},
                {"avg_pairwise": rep.avg_pairwise, "history_days": rep.history_days,
                 "short_history": rep.short_history}, "Correlation lattice computed")
    return {"ok": True, "summary": f"avg pairwise correlation {rep.avg_pairwise:.2f}",
            "callouts": [c.text for c in rep.callouts[:4]], "evidence_ids": [eid]}


async def search_news(ctx: ToolContext, args: dict, run: Any) -> dict:
    items = ctx.gw.news(args.get("tickers"), since=args.get("since"), caller="tool.search_news")
    safe, quarantined = [], 0
    for n in items[-10:]:
        reason = scan(n.headline + " " + n.summary)
        if reason:
            quarantined += 1
            ctx.events.emit("content.quarantined", run_id=_run_id(run), title=f"Quarantined {n.id}",
                            evidence_ids=[n.id], payload={"evidence_id": n.id, "reason": reason})
            continue
        safe.append({"id": n.id, "headline": n.headline, "available_at": n.available_at})
    return {"ok": True, "summary": f"{len(safe)} items ({quarantined} quarantined)", "items": safe,
            "evidence_ids": [s["id"] for s in safe]}


async def search_filings(ctx: ToolContext, args: dict, run: Any) -> dict:
    ticker = args.get("ticker") or (args.get("tickers") or [None])[0]
    words = [w.lower() for w in str(args.get("query") or "").split() if len(w) > 2]
    out, quarantined = [], 0
    for f in ctx.gw.filings(ticker, since=args.get("since"), caller="tool.search_filings")[::-1]:
        for p in f.passages:
            if words and not any(w in p.text.lower() for w in words):
                continue
            reason = scan(p.text)
            if reason:
                quarantined += 1
                ctx.events.emit("content.quarantined", run_id=_run_id(run), title=f"Quarantined {p.id}",
                                evidence_ids=[p.id], payload={"evidence_id": p.id, "reason": reason})
                continue
            ctx.events.emit("source.inspect", run_id=_run_id(run), title=f"{f.company} {f.form}", evidence_ids=[p.id],
                            payload={"evidence_id": p.id, "kind": "filing", "title": f"{f.company} {f.form}",
                                     "source": "synthetic" if f.synthetic else "sec_edgar",
                                     "published_at": f.accepted_at})
            out.append({"id": p.id, "company": f.company, "form": f.form, "accepted_at": f.accepted_at,
                        "text": p.text[:500]})
            if len(out) >= 8:
                break
        if len(out) >= 8:
            break
    return {"ok": True, "summary": f"{len(out)} filing passages ({quarantined} quarantined)", "passages": out,
            "evidence_ids": [p["id"] for p in out]}


async def earnings_calendar(ctx: ToolContext, args: dict, run: Any) -> dict:
    rows = ctx.gw.earnings(args.get("tickers"), caller="tool.earnings_calendar")
    by: dict[str, list[str]] = {}
    for r in rows:
        by.setdefault(r["ticker"], []).append(r["date"])
    last = {t: sorted(d)[-4:] for t, d in by.items()}
    return {"ok": True, "summary": f"past earnings dates for {len(last)} tickers (dates up to as_of only)",
            "past_dates": last, "evidence_ids": [f"earnings:{t}" for t in last]}


# ---------------------------------------------------------------------- engine tools
async def risk_stats(ctx: ToolContext, args: dict, run: Any) -> dict:
    """Engine risk stats (engine.risk.risk_stats): vol, max drawdown, beta, concentration, history flag."""
    w, cash, label = _weights_from(ctx, args, run)
    bench = params()["benchmark_global_etf"]
    prices = ctx.gw.prices(list(dict.fromkeys([*w, bench])), caller="tool.risk_stats")
    rs = risk.risk_stats(w, prices, benchmark=bench)
    out = {"vol_annual": _r(rs.vol), "max_drawdown": _r(rs.max_drawdown), "beta_vs_global_equity": _r(rs.beta),
           "herfindahl": _r(rs.herfindahl), "largest": max(w, key=w.get), "cash_weight": _r(cash),
           "history_days": rs.history_days, "short_history": rs.short_history, "label": rs.label}
    eid = _calc(ctx, run, "risk_stats", {"weights": _round_w(w), "label": label}, out, f"Risk stats for {label}")
    return {"ok": True, "summary": f"{label}: vol {rs.vol:.1%}/yr, max drawdown {rs.max_drawdown:.1%} (historical)",
            **out, "evidence_ids": [eid]}


async def backtest(ctx: ToolContext, args: dict, run: Any) -> dict:
    w, _, label = _weights_from(ctx, args, run)
    start = args.get("start") or _lookback_start(ctx, params()["optimiser"]["lookback"])
    res = bt.run(ctx.gw, w, start=start, end=args.get("end"), rebalance=args.get("rebalance", "quarterly"))
    m = res.metrics
    out = {"start": res.start, "end": res.end, "rebalance": res.rebalance, "total_return": _r(m.total_return),
           "vol_annual": _r(m.vol_annual), "max_drawdown": _r(m.max_drawdown), "sharpe": _r(m.sharpe, 2),
           "label": res.label}
    eid = _calc(ctx, run, "backtest", {"weights": _round_w(w), "start": start, "end": args.get("end")}, out,
                f"Backtest of {label} {res.start}→{res.end}")
    return {"ok": True, "summary": f"{label} {res.start}→{res.end}: return {m.total_return:.1%}, "
                                   f"max drawdown {m.max_drawdown:.1%} (simulated, not a forecast)",
            **out, "evidence_ids": [eid]}


async def build_options(ctx: ToolContext, args: dict, run: Any) -> dict:
    eligible = ctx.gw.catalogue()
    wanted = set(args.get("tickers") or [])
    insts = [i for i in eligible if not wanted or i.ticker in wanted]
    if not insts:
        return {"ok": False, "error": "no_candidates", "summary": "none of the tickers are eligible"}
    cov = _cov(ctx, [i.ticker for i in insts], "tool.build_options")
    mu, fc_eid = _forecast_mu(ctx, run, [i.ticker for i in insts])   # same bounded tilt as the sim (#73)
    current = ctx.state.ledger.weights()
    lookback_start = _lookback_start(ctx, params()["optimiser"]["lookback"])
    options: dict[str, PortfolioOption] = {}
    summary_rows, eids, failed = [], [], []
    for variant in VARIANTS:
        res = optimiser.optimise(optimiser.OptimiseRequest(mandate=ctx.state.mandate, instruments=insts, cov=cov,
                                                           current_weights=current, variant=variant, mu=mu))
        if res.status != "optimal":
            failed.append({"variant": variant, "status": res.status, "why": res.binding_constraints})
            continue
        _, cost, turnover = _trades(ctx, res.weights)
        mdd = bt.run(ctx.gw, res.weights, start=lookback_start, rebalance="quarterly").metrics.max_drawdown
        stats = OptionStats(vol_annual=round(res.vol_annual or 0, 4), ocf_weighted=round(res.ocf_weighted or 0, 5),
                            turnover=turnover, cost_gbp=cost, max_drawdown_backtest=_r(mdd))
        rounded = _round_w(res.weights)   # 4 dp for display; cash absorbs the rounding so weights + cash == 1
        options[variant] = PortfolioOption(
            label=variant, cash_weight=round(1.0 - sum(rounded.values()), 6), stats=stats,
            holdings=[ProposedHolding(ticker=t, weight=x) for t, x in rounded.items()])
        eid = _calc(ctx, run, "optimise", {"variant": variant, "candidates": [i.ticker for i in insts]},
                    {"weights": _round_w(res.weights), "cash_weight": res.cash_weight, **stats.model_dump(),
                     "binding_constraints": res.binding_constraints}, f"Optimised {variant} option")
        eids.append(eid)
        summary_rows.append({"option": variant, "weights": _round_w(res.weights), "cash": _r(res.cash_weight),
                             "vol_annual": stats.vol_annual, "fees_per_year_gbp": round(stats.ocf_weighted * _capital(ctx), 2),
                             "trade_cost_gbp": cost, "max_drawdown_backtest": stats.max_drawdown_backtest,
                             "binding": res.binding_constraints, "evidence_id": eid})
    scratch = _scratch(run)
    scratch["options"] = options
    if not options:
        return {"ok": False, "error": "infeasible", "summary": "no option satisfies the mandate", "failed": failed}
    return {"ok": True, "summary": f"built {len(options)} options: {', '.join(options)}"
                                   + (" (with the bounded 2-week forecast tilt)" if mu is not None else ""),
            "options": summary_rows, "failed": failed, "evidence_ids": eids + ([fc_eid] if fc_eid else [])}


async def cost_turnover(ctx: ToolContext, args: dict, run: Any) -> dict:
    w, _, label = _weights_from(ctx, args, run)
    changes, cost, turnover = _trades(ctx, w)
    out = {"trades": [c.model_dump() for c in changes], "cost_gbp": cost, "turnover": turnover,
           "capital_gbp": round(_capital(ctx), 2)}
    eid = _calc(ctx, run, "cost_turnover", {"weights": _round_w(w), "label": label}, out, f"Trades and costs for {label}")
    return {"ok": True, "summary": f"{label}: {len(changes)} trades, cost £{cost:,.2f}, turnover {turnover:.0%}",
            **out, "evidence_ids": [eid]}


async def check_proposal(ctx: ToolContext, args: dict, run: Any) -> dict:
    w, cash, label = _weights_from(ctx, args, run)
    led = ctx.state.ledger
    rep = checker.check_proposal(w, cash, ctx.state.mandate, ctx.gw.catalogue(eligible_only=False),
                                 current_weights=led.weights(), nav_gbp=_capital(ctx))
    out = {"passed": rep.passed, "violations": [v.model_dump(exclude_none=True) for v in rep.violations],
           "recomputed": {k: _r(v) for k, v in rep.recomputed.items()}}
    eid = _calc(ctx, run, "check_proposal", {"weights": _round_w(w), "cash_weight": _r(cash), "label": label}, out,
                f"Mandate check for {label}: {'pass' if rep.passed else 'fail'}")
    msg = "passes the mandate" if rep.passed else "; ".join(v.message for v in rep.violations[:3])
    return {"ok": True, "summary": f"{label}: {msg}", **out, "evidence_ids": [eid]}


async def exposure_tool(ctx: ToolContext, args: dict, run: Any) -> dict:
    entity = args.get("entity") or args.get("ticker")
    if not entity:
        raise ValueError("pass `entity` (a ticker or company name)")
    w, _, label = _weights_from(ctx, args, run)
    holdings = {t: ctx.gw.etf_holdings(t) for t in w}
    res = exposure.look_through(w, holdings, entity)
    out = res.model_dump()
    eid = _calc(ctx, run, "exposure", {"entity": entity, "label": label}, out, f"Exposure to {entity}")
    return {"ok": True, "summary": f"{label}: {res.total:.1%} exposure to {entity} (ownership, not a predicted loss)",
            **out, "evidence_ids": [eid]}


async def overlap_tool(ctx: ToolContext, args: dict, run: Any) -> dict:
    """How much two or more holdings are the same companies (#25). Ownership, not a predicted loss."""
    cat = ctx.gw.catalogue(eligible_only=False)
    raw = args.get("tickers") or list(ctx.state.ledger.weights()) or [i.ticker for i in cat if i.kind == "etf"][:6]
    if isinstance(raw, str):   # models sometimes send "VWRP.LSE, VUAG.LSE" instead of a list
        raw = raw.replace(";", ",").split(",")
    tickers = list(dict.fromkeys(str(t).strip() for t in raw if str(t).strip()))[:12]
    if len(tickers) < 2:
        raise ValueError("pass at least two `tickers` to compare")
    stocks = {i.ticker for i in cat if i.kind == "stock"}
    pairs = exposure.overlap_pairs(tickers, {t: ctx.gw.etf_holdings(t) for t in tickers}, stocks)
    # top 10 pairs only: the full matrix (up to 66 pairs) would flood the model's context
    out = {"pairs": [p.model_dump() for p in pairs[:10]], "pairs_total": len(pairs), "note": exposure.OVERLAP_NOTE}
    eid = _calc(ctx, run, "overlap", {"tickers": tickers}, out, f"Overlap between {len(tickers)} holdings")
    known = [p for p in pairs if p.overlap is not None]
    if known:
        top = known[0]
        summary = (f"{top.a} and {top.b} share {top.overlap:.1%} of their holdings by weight "
                   "(ownership, not a predicted loss)")
    else:
        summary = "no look-through holdings data for these funds, so overlap is unknown (not zero)"
    return {"ok": True, "summary": summary, **out, "evidence_ids": [eid]}


async def forecast(ctx: ToolContext, args: dict, run: Any) -> dict:
    try:
        from app.engine import forecast as fc  # Cem's #73
    except ImportError:
        return {"ok": False, "error": "not_available", "summary": "the 2-week forecast lands with #73"}
    tickers = args.get("tickers") or list(ctx.state.ledger.weights()) or [i.ticker for i in ctx.gw.catalogue()]
    res = fc.forecast(ctx.gw, tickers, ctx.gw.clock.as_of_str(), horizon=int(args.get("horizon", 10)))
    out = res.model_dump() if hasattr(res, "model_dump") else dict(res)
    eid = _calc(ctx, run, "forecast_2w", {"tickers": tickers}, out, "2-week estimate (not a promise)")
    return {"ok": True, "summary": "2-week estimate from past data only (estimate, not a promise)",
            "forecast": out, "evidence_ids": [eid]}


# ---------------------------------------------------------------------- proposals and memory
async def propose_adjustment(ctx: ToolContext, args: dict, run: Any) -> dict:
    label = args.get("option") or "recommended"
    options: dict[str, PortfolioOption] = _scratch(run).get("options", {})
    if label not in options:
        raise ValueError(f"no option '{label}': call build_options first")
    opt = options[label]
    w = {h.ticker: h.weight for h in opt.holdings}
    led = ctx.state.ledger
    rep = checker.check_proposal(w, opt.cash_weight, ctx.state.mandate, ctx.gw.catalogue(eligible_only=False),
                                 current_weights=led.weights(), nav_gbp=_capital(ctx))
    if not rep.passed:
        return {"ok": False, "error": "mandate_violation", "summary": "; ".join(v.message for v in rep.violations[:3]),
                "violations": [v.model_dump(exclude_none=True) for v in rep.violations]}
    purposes = args.get("purposes") if isinstance(args.get("purposes"), dict) else {}
    why_not = args.get("why_not") if isinstance(args.get("why_not"), dict) else {}
    for h in opt.holdings:   # purpose + evidence default to the holding's saved investment case
        raw = ctx.state.db.get("cases", h.ticker)
        case = InvestmentCase.model_validate_json(raw) if raw else None
        h.purpose = str(purposes.get(h.ticker) or (case.purpose if case else "") or h.purpose)[:200]
        h.why_not_alternatives = str(why_not.get(h.ticker, h.why_not_alternatives))[:300]
        if case and not h.evidence_ids:
            h.evidence_ids = list(case.evidence_ids)
    missing = [h.ticker for h in opt.holdings if not h.purpose]
    changes, cost, turnover = _trades(ctx, w)
    capital = _capital(ctx)
    kind = "construction" if led.nav() <= 0 else "adjustment"
    s = opt.stats
    card = DecisionCard(
        headline=(f"Proposed starting portfolio: {len(opt.holdings)} holdings" if kind == "construction"
                  else f"Proposed adjustment: {len(changes)} trades"),
        body=(f"Invests £{capital:,.0f} across {len(opt.holdings)} holdings with £{opt.cash_weight * capital:,.0f} kept "
              f"in cash. Trading cost about £{cost:,.2f}; fund fees about £{s.ocf_weighted * capital:,.2f} a year. "
              f"In the past {params()['optimiser']['lookback']} trading days a mix like this had a worst fall of "
              f"{abs(s.max_drawdown_backtest or 0):.0%} (simulated on past data, not a forecast)."),
        changes=changes)
    uncertainties = sorted({u for f in getattr(run, "findings", []) for u in getattr(f, "uncertainties", [])})[:10]
    prop = Proposal(id=f"prop_{uuid.uuid4().hex[:10]}", run_id=_run_id(run) or "none", kind=kind,
                    as_of=ctx.gw.clock.as_of_str(), created_at=datetime.now(UTC).isoformat(),
                    options=list(options.values()), selected=label, decision_card=card, uncertainties=uncertainties)
    ctx.state.proposals[prop.id] = prop
    ctx.state.db.put("proposals", prop.id, prop.model_dump_json())
    if run is not None:
        run.proposal_id = prop.id
    ctx.events.emit("proposal.created", run_id=_run_id(run), title=card.headline,
                    payload={"proposal_id": prop.id, "kind": kind})
    return {"ok": True, "summary": f"proposal {prop.id} created ({label}, {len(changes)} trades, cost £{cost:,.2f}); "
                                   "it needs the user's approval", "proposal_id": prop.id,
            "turnover": turnover, "holdings_without_purpose": missing, "evidence_ids": [f"proposal:{prop.id}"]}


async def get_investment_case(ctx: ToolContext, args: dict, run: Any) -> dict:
    ticker = args.get("ticker")
    raw = ctx.state.db.get("cases", ticker) if ticker else None
    if not raw:
        return {"ok": True, "summary": f"no investment case for {ticker}", "case": None, "evidence_ids": []}
    case = InvestmentCase.model_validate_json(raw)
    return {"ok": True, "summary": f"case {case.case_id} v{case.version}", "case": case.model_dump(),
            "evidence_ids": [f"case:{case.ticker}:v{case.version}"]}


async def save_investment_case(ctx: ToolContext, args: dict, run: Any) -> dict:
    """Save one case (`case` or flat args) or several (`cases`: list) in one call. Versioned per ticker."""
    raw = args.get("cases")
    if isinstance(raw, str):
        raw = json.loads(raw)
    if not raw:
        one = args.get("case")
        if isinstance(one, str):
            one = json.loads(one)
        raw = [dict(one or {k: v for k, v in args.items() if k != "case"})]
    emap = getattr(run, "evidence_map", {}) or {}
    saved, ids = [], []
    for data in raw[:20]:
        data = dict(data)
        ticker = data.get("ticker")
        if not ticker:
            raise ValueError("every investment case needs a ticker")
        data["evidence_ids"] = [emap.get(e, e) for e in data.get("evidence_ids", [])]  # aliases -> real ids
        prev = ctx.state.db.get("cases", ticker)
        version = InvestmentCase.model_validate_json(prev).version + 1 if prev else 1
        case = InvestmentCase.model_validate({**data, "case_id": f"case_{ticker}", "version": version})
        ctx.state.db.put("cases", ticker, case.model_dump_json())
        saved.append({"ticker": ticker, "case_id": case.case_id, "version": version})
        ids.append(f"case:{ticker}:v{version}")
    first = saved[0]
    return {"ok": True, "summary": f"saved {len(saved)} investment case(s): {', '.join(s['ticker'] for s in saved)}",
            "saved": saved, "case_id": first["case_id"], "version": first["version"], "evidence_ids": ids}


# ---------------------------------------------------------------------- web (live only)
async def web_search(ctx: ToolContext, args: dict, run: Any) -> dict:
    if ctx.gw.clock.mode != "live":
        return {"ok": False, "error": "historical_mode",
                "summary": "web search is live mode only (it can't be limited to the sim date)"}
    query = str(args.get("query") or "").strip()
    if not query:
        raise ValueError("pass a `query`")
    res = await ctx.state.llm.search(query, ctx.gw.clock.as_of_str())
    reason = scan(res["text"])
    eid = f"web:{hashlib.sha256(query.encode()).hexdigest()[:12]}"
    if reason:
        ctx.events.emit("content.quarantined", run_id=_run_id(run), title=f"Quarantined {eid}", evidence_ids=[eid],
                        payload={"evidence_id": eid, "reason": reason})
        return {"ok": False, "error": "quarantined", "summary": "search result looked like an instruction; quarantined"}
    ctx.events.emit("source.inspect", run_id=_run_id(run), title=f"Web search: {query[:80]}", evidence_ids=[eid],
                    payload={"evidence_id": eid, "kind": "web", "title": query[:120], "source": "google_search",
                             "published_at": None, "sources": res["sources"][:5]})
    return {"ok": True, "summary": f"web search: {len(res['sources'])} sources",
            "text": f"<untrusted_source>{res['text'][:1200]}</untrusted_source>", "sources": res["sources"][:5],
            "evidence_ids": [eid]}


def default_registry(ctx: ToolContext) -> ToolRegistry:
    reg = ToolRegistry(ctx)
    for name, fn in {
        "get_catalogue": get_catalogue, "get_prices": get_prices, "correlation_lattice": correlation_lattice,
        "search_news": search_news, "search_filings": search_filings, "earnings_calendar": earnings_calendar,
        "risk_stats": risk_stats, "backtest": backtest, "build_options": build_options,
        "cost_turnover": cost_turnover, "check_proposal": check_proposal, "exposure": exposure_tool, "overlap": overlap_tool,
        "forecast": forecast, "propose_adjustment": propose_adjustment,
        "get_investment_case": get_investment_case, "save_investment_case": save_investment_case,
        "web_search": web_search,
    }.items():
        reg.register(name, fn)
    # Not yet (other issues): overlap, pnl_breakdown, create_monitor (#36), get_run_history, get_fx, macro_series (#64)
    return reg
