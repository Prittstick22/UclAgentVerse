"""Tool registry: our code, exposed to agents. Every call emits tool.call / tool.result. Owner: Dev.

SCAFFOLD: the registry, role allow-lists and event wiring are done. A few tools are implemented against the
engine as examples; the rest are stubs returning `not_implemented`. See docs/05-agent-system.md §5 for the
full catalogue, and the GitHub issues for each tool.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from app.agents.guard import scan
from app.agents.roles import ROLES
from app.core.events import EventBus
from app.data.gateway import AsOfViolation, DataGateway
from app.engine import risk

ToolFn = Callable[["ToolContext", dict, Any], Awaitable[dict]]


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
        except Exception as e:  # tools must never crash a run
            out = {"ok": False, "error": type(e).__name__, "summary": str(e)[:200]}
        ev.emit("tool.result", title=f"{name}: {out.get('summary', 'ok')}"[:120], status="ok" if out.get("ok") else "failed",
                evidence_ids=out.get("evidence_ids", []),
                payload={"tool": name, "ok": out.get("ok", False), "summary": out.get("summary", "")}, **agent)
        return out


def _not_implemented(name: str) -> ToolFn:
    async def fn(ctx: ToolContext, args: dict, run: Any) -> dict:
        return {"ok": False, "error": "not_implemented", "summary": f"{name} is not implemented yet (see issues)"}
    return fn


# ---------------------------------------------------------------------- example tools
async def get_catalogue(ctx: ToolContext, args: dict, run: Any) -> dict:
    items = [i.model_dump(include={"ticker", "name", "asset_class", "sleeve", "ocf", "kind"}) for i in ctx.gw.catalogue()]
    return {"ok": True, "summary": f"{len(items)} eligible instruments", "items": items, "evidence_ids": ["catalogue"]}


async def correlation_lattice(ctx: ToolContext, args: dict, run: Any) -> dict:
    tickers = args.get("tickers") or [i.ticker for i in ctx.gw.catalogue()][:10]
    prices = ctx.gw.prices(tickers, caller="tool.correlation_lattice")
    rep = risk.correlation_report(prices, ctx.gw.clock.as_of_str(), args.get("lookback"))
    ev = ctx.events.emit("calc.result", run_id=getattr(run, "run_id", None), title="Correlation lattice computed",
                         payload={"name": "correlation_lattice",
                                  "inputs": {"tickers": tickers, "lookback": rep.lookback},
                                  "outputs": {"avg_pairwise": rep.avg_pairwise, "history_days": rep.history_days,
                                              "short_history": rep.short_history}})
    return {"ok": True, "summary": f"avg pairwise correlation {rep.avg_pairwise:.2f}",
            "callouts": [c.text for c in rep.callouts[:4]], "evidence_ids": [f"calc:{ev.id}"]}


async def search_news(ctx: ToolContext, args: dict, run: Any) -> dict:
    items = ctx.gw.news(args.get("tickers"), since=args.get("since"), caller="tool.search_news")
    safe, quarantined = [], 0
    for n in items[-10:]:
        reason = scan(n.headline + " " + n.summary)
        if reason:
            quarantined += 1
            ctx.events.emit("content.quarantined", run_id=getattr(run, "run_id", None), title=f"Quarantined {n.id}",
                            evidence_ids=[n.id], payload={"evidence_id": n.id, "reason": reason})
            continue
        safe.append({"id": n.id, "headline": n.headline, "available_at": n.available_at})
    return {"ok": True, "summary": f"{len(safe)} items ({quarantined} quarantined)", "items": safe,
            "evidence_ids": [s["id"] for s in safe]}


def default_registry(ctx: ToolContext) -> ToolRegistry:
    reg = ToolRegistry(ctx)
    reg.register("get_catalogue", get_catalogue)
    reg.register("correlation_lattice", correlation_lattice)
    reg.register("search_news", search_news)
    # TODO(issues): get_prices, risk_stats, overlap, exposure, backtest, build_options, cost_turnover,
    # pnl_breakdown, search_filings, earnings_calendar, web_search (live only), check_proposal,
    # get/save_investment_case, propose_adjustment, create_monitor, get_run_history
    return reg
