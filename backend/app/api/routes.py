"""HTTP routes per docs/04-api-contracts.md. Owner: Jin (routing) with Cem/Dev for their handlers.

SCAFFOLD: every endpoint exists with the contract shape. Endpoints marked TODO return valid-but-empty data so the
frontend can integrate now. Replace each TODO in its issue.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import date
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.api.portfolio import PortfolioView
from app.api.run_views import agent_tree, find_evidence, summarize
from app.container import state_for_mode
from app.core.events import Event, sse_frame
from app.data.gateway import AsOfViolation
from app.data.live import updates
from app.engine import risk
from app.engine.portfolio import PortfolioDataUnavailable
from app.profile.quiz import mandate_for, questions_payload, score
from app.schemas import (
    Evidence,
    Goal,
    Mandate,
    Mode,
    Notifications,
    PnlPeriod,
    Portfolio,
    PortfolioHistory,
    PortfolioPnl,
    PortfolioRebalances,
    RunSummary,
    TriggerKind,
)
from app.sim.controller import SimError
from app.sim.controller import controller as sim_controller

router = APIRouter(prefix="/api")
log = logging.getLogger(__name__)


def S(request: Request):
    return request.app.state.app


def err(status: int, code: str, message: str):
    raise HTTPException(status_code=status, detail={"error": {"code": code, "message": message, "details": {}}})


# ------------------------------------------------------------------ system
@router.get("/health")
def health(request: Request):
    s = S(request)
    return {"status": "ok", "mode": s.clock.mode, "as_of": s.clock.as_of_str(), "version": "0.1.0",
            "llm_mode": s.settings.llm_mode, "data_source": s.gw.snapshot.source_label}


@router.get("/mode")
def get_mode(request: Request):
    s = S(request)
    return {"mode": s.clock.mode, "as_of": s.clock.as_of_str(), "sim": sim_controller(s).info()}


class ModeBody(BaseModel):
    mode: Mode


@router.post("/mode")
def set_mode(body: ModeBody, request: Request):
    previous = S(request)
    active = state_for_mode(previous, body.mode)
    request.app.state.app = active
    if previous is not active:
        active.events.emit("mode.changed", title=f"Changed to {body.mode}", payload={"mode": body.mode})
    return get_mode(request)


# ------------------------------------------------------------------ profile + mandate
@router.get("/profile/questions")
def profile_questions():
    return {"questions": questions_payload()}


class QuizBody(BaseModel):
    answers: dict[str, str]
    goal: Goal | None = None
    exclusions: list[str] = []


@router.post("/profile/quiz")
def profile_quiz(body: QuizBody, request: Request):
    result = score(body.answers)
    mandate = mandate_for(result.name, body.goal, body.exclusions)
    S(request).mandate = mandate
    return {"profile": result.model_dump(), "mandate": mandate.model_dump()}


@router.get("/mandate")
def get_mandate(request: Request) -> Mandate:
    return S(request).mandate


@router.put("/mandate")
def put_mandate(body: Mandate, request: Request) -> Mandate:
    s = S(request)
    body.version = s.mandate.version + 1  # TODO(#mandate): validate ranges vs policy limits
    s.mandate = body
    return body


@router.get("/catalogue")
def catalogue(request: Request):
    return {"instruments": [i.model_dump() for i in S(request).gw.catalogue()]}


# ------------------------------------------------------------------ portfolio
@router.post("/portfolio/build", status_code=202)
async def build(request: Request):
    s = S(request)
    run_id = f"run_{uuid.uuid4().hex}"
    task = asyncio.create_task(s.supervisor.start("construction", "User asked to build a portfolio", run_id=run_id))
    s.runs[run_id] = task

    def finished(task: asyncio.Task) -> None:
        s.runs.pop(run_id, None)
        if not task.cancelled() and task.exception() is not None:
            log.error("Portfolio build %s failed", run_id, exc_info=task.exception())

    task.add_done_callback(finished)
    return {"run_id": run_id}


@router.get("/portfolio")
def portfolio(request: Request, mode: Mode | None = None) -> Portfolio:
    s = S(request)
    if s.clock.mode == "live" and mode in (None, "live"):
        # Live (#11): cached prices + coverage-based status from the live cache; counters from the activity log.
        from app.data.live import live_portfolio
        summary = live_portfolio(s)
        activity = s.activity.snapshot("live")
        status = "monitoring_degraded" if summary.status == "monitoring_degraded" else activity.status
        return summary.model_copy(update={"status": status, "counters": activity.counters,
                                          "last_review_date": activity.last_review_date})
    try:
        summary = PortfolioView(s, mode).summary()
    except PortfolioDataUnavailable as exc:
        err(409, "validation_error", str(exc))
    # Home status + counters come from the notifications activity log (#10); holdings and P&L from #21.
    activity = s.activity.snapshot(mode or s.clock.mode)
    return summary.model_copy(update={"status": activity.status, "counters": activity.counters,
                                      "last_review_date": activity.last_review_date or summary.last_review_date})


@router.get("/portfolio/history")
def history(
    request: Request, mode: Mode | None = None, start: date | None = None, end: date | None = None,
) -> PortfolioHistory:
    if start and end and start > end:
        err(422, "validation_error", "Start must be on or before end")
    return PortfolioView(S(request), mode).history(start.isoformat() if start else None, end.isoformat() if end else None)


@router.get("/portfolio/pnl")
def pnl(request: Request, mode: Mode | None = None, period: PnlPeriod = "since_purchase") -> PortfolioPnl:
    try:
        return PortfolioView(S(request), mode).pnl(period)
    except PortfolioDataUnavailable as exc:
        err(409, "validation_error", str(exc))


@router.get("/portfolio/rebalances")
def rebalances(request: Request, mode: Mode | None = None, limit: int = Query(default=20, ge=1)) -> PortfolioRebalances:
    return PortfolioView(S(request), mode).rebalances(limit)


@router.get("/benchmarks")
def benchmarks(request: Request):
    return {"series": {}, "metrics": {}, "periods": {"development": ["2023-01-02", "2026-07-06"],
                                                      "held_out": ["2026-07-07", None]}}  # TODO(#benchmarks)


@router.get("/risk/correlation")
def correlation(request: Request, lookback: int | None = None, tickers: str | None = None,
                as_of: str | None = None):
    """Correlation lattice as of `as_of` (any past date up to the clock; default = now)."""
    s = S(request)
    names = {i.ticker: i.name for i in s.gw.catalogue()}
    tick = tickers.split(",") if tickers else list(s.ledger.weights()) or [i.ticker for i in s.gw.catalogue()][:8]
    try:
        # strict YYYY-MM-DD: pd.Timestamp would also accept "now"/"today" (the wall clock) and "NaT"
        day = date.fromisoformat(as_of).isoformat() if as_of else s.clock.as_of_str()
    except ValueError:
        err(422, "validation_error", f"as_of must be a date like 2026-09-01, got {as_of!r}")
    try:
        prices = s.gw.prices(tick, end=day, caller="api.correlation")
        rep = risk.correlation_report(prices, day, lookback, names)
    except AsOfViolation as e:
        err(400, "asof_violation", str(e))
    except (KeyError, ValueError) as e:
        err(422, "validation_error", str(e))
    return rep.model_dump()


# ------------------------------------------------------------------ runs + events
@router.get("/runs", response_model_exclude={"items": {"__all__": {"agents"}}})
def runs(request: Request, limit: int = 50, mode: Mode | None = None,
         kind: TriggerKind | None = None) -> dict[str, list[RunSummary]]:
    s = S(request)
    rows = s.db.execute(
        """SELECT json FROM events
           WHERE run_id IS NOT NULL AND mode = ? AND type IN ('run.started', 'run.completed')
           ORDER BY ts_wall""",
        (mode or s.clock.mode,),
    )
    events = [Event.model_validate_json(row[0]) for row in rows]
    completed = {event.run_id: event for event in events if event.type == "run.completed"}
    items = [summarize(event, completed.get(event.run_id)) for event in events if event.type == "run.started"]
    if kind:
        items = [item for item in items if item.kind == kind]
    return {"items": items[-limit:] if limit > 0 else []}


@router.get("/runs/{run_id}")
def run_detail(run_id: str, request: Request) -> RunSummary:
    s = S(request)
    events = s.events.history(run_id)
    start = next((event for event in events if event.type == "run.started"), None)
    if start is None:
        err(404, "not_found", f"run {run_id} not found")
    completed = next((event for event in reversed(events) if event.type == "run.completed"), None)
    summary = summarize(start, completed)
    max_depth = start.payload.get("limits", {}).get("max_depth", s.supervisor.cfg["max_depth"])
    summary.agents = agent_tree(events, max_depth)
    return summary


@router.get("/runs/{run_id}/events")
async def run_events(run_id: str, request: Request, after: int = 0, format: str = "sse"):
    bus = S(request).events
    if format == "json":
        return {"items": [e.model_dump() for e in bus.history(run_id, after)]}

    async def stream():
        q = bus.subscribe(run_id)
        try:
            last = after
            for e in bus.history(run_id, after):
                last = e.seq
                yield sse_frame(e)
            while True:
                if await request.is_disconnected():
                    break
                try:
                    e = await asyncio.wait_for(q.get(), timeout=15)
                    if e.seq > last:
                        yield sse_frame(e)
                except TimeoutError:
                    yield ": ping\n\n"
        finally:
            bus.unsubscribe(q)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/events/stream")
async def all_events(request: Request):
    bus = S(request).events

    async def stream():
        q = bus.subscribe(None)
        try:
            while not await request.is_disconnected():
                try:
                    yield sse_frame(await asyncio.wait_for(q.get(), timeout=15))
                except TimeoutError:
                    yield ": ping\n\n"
        finally:
            bus.unsubscribe(q)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


# ------------------------------------------------------------------ proposals, evidence, notifications
@router.get("/proposals/{proposal_id}")
def proposal(proposal_id: str, request: Request):
    p = S(request).proposals.get(proposal_id)  # TODO(#proposals)
    if not p:
        err(404, "not_found", "proposal not found")
    return p


@router.post("/proposals/{proposal_id}/approve")
def approve(proposal_id: str, request: Request):
    err(501, "internal", "TODO(#approve): revalidate → queue orders → approval.decided event")


@router.post("/proposals/{proposal_id}/decline")
def decline(proposal_id: str, request: Request):
    err(501, "internal", "TODO(#approve)")


@router.get("/evidence/{evidence_id}")
def evidence(evidence_id: str, request: Request) -> Evidence:
    s = S(request)
    item = find_evidence(s.gw, s.db, evidence_id)
    if item is None:
        err(404, "not_found", "evidence not found")
    return item


@router.get("/notifications")
async def notifications(request: Request, mode: Mode | None = None, unread: bool = False) -> Notifications:
    s = S(request)
    activity = s.activity.snapshot(mode or s.clock.mode)
    return Notifications(items=sorted((item for item in activity.items.values() if not unread or not item.read),
                                      key=lambda item: item.created_at, reverse=True))


@router.post("/notifications/{notification_id}/read")
async def notification_read(notification_id: str, request: Request):
    s = S(request)
    mode = s.clock.mode
    if notification_id not in s.activity.snapshot(mode).items:
        err(404, "not_found", "notification not found")
    s.activity.read(notification_id, mode)
    return {"ok": True}


# ------------------------------------------------------------------ sim, chat, tasks
class SimStartBody(BaseModel):
    start: date | None = None
    end: date | None = None
    speed: float | None = None            # trading days per second; 0 = as fast as possible
    run_agents: bool = False
    approvals: Literal["manual", "batch_policy"] = "manual"


class SimStepBody(BaseModel):
    days: int = 1


@router.post("/sim/start")
async def sim_start(request: Request, body: SimStartBody | None = None):
    s, b = S(request), body or SimStartBody()
    try:
        sim = await sim_controller(s).start(b.start.isoformat() if b.start else None,
                                            b.end.isoformat() if b.end else None, b.speed, b.run_agents, b.approvals)
    except SimError as e:
        err(e.status, e.code, e.message)
    return {"sim": sim}


@router.post("/sim/pause")
async def sim_pause(request: Request):
    s = S(request)
    return {"sim": await sim_controller(s).pause(), "as_of": s.clock.as_of_str()}


@router.post("/sim/step")
async def sim_step(request: Request, body: SimStepBody | None = None):
    s = S(request)
    try:
        sim = await sim_controller(s).step((body or SimStepBody()).days)
    except SimError as e:
        err(e.status, e.code, e.message)
    return {"sim": sim, "as_of": s.clock.as_of_str()}


@router.get("/sim/status")
def sim_status(request: Request):
    s = S(request)
    ctl = sim_controller(s)
    return {"sim": ctl.info(), "as_of": s.clock.as_of_str(), "progress": ctl.progress()}


class ChatBody(BaseModel):
    message: str
    conversation_id: str | None = None


@router.post("/chat")
def chat(body: ChatBody, request: Request):
    return {"conversation_id": body.conversation_id or "conv_1", "run_id": None,
            "answer": "Chat isn't wired up yet (TODO #chat).", "citations": [], "proposal_id": None}


@router.post("/tasks/live-eod")
def live_eod(request: Request, background: BackgroundTasks):
    s = S(request)
    if not s.settings.task_secret or request.headers.get("X-Task-Secret") != s.settings.task_secret:
        err(401, "unauthorized", "bad task secret")
    live = state_for_mode(s, "live")
    background.add_task(updates(live).refresh, "eod")
    return {"ok": True, "fetched": 0, "stale": [t for t, f in live.gw.freshness().items() if f.stale]}


@router.post("/tasks/live-news")
def live_news(request: Request, background: BackgroundTasks):
    s = S(request)
    if not s.settings.task_secret or request.headers.get("X-Task-Secret") != s.settings.task_secret:
        err(401, "unauthorized", "bad task secret")
    live = state_for_mode(s, "live")
    background.add_task(updates(live).refresh, "news")
    return {"ok": True, "fetched": 0, "stale": [t for t, f in live.gw.freshness().items() if f.stale]}

