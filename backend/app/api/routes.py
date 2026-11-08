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

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from app.api.demo_guard import check_budget, guard_agent_run, require_passcode
from app.api.portfolio import PortfolioView
from app.api.recorded_replay import controller as sim_controller
from app.api.run_views import agent_tree, find_evidence, summarize
from app.container import state_for_mode
from app.core.events import Event, sse_frame
from app.data.gateway import AsOfViolation
from app.data.live import updates
from app.engine import risk
from app.engine.portfolio import PortfolioDataUnavailable
from app.profile.demo import demo_profile
from app.profile.mandates import save as save_mandate
from app.profile.mandates import validate as validate_mandate
from app.profile.quiz import mandate_for, questions_payload, score
from app.schemas import (
    DemoProfile,
    Evidence,
    Mandate,
    Mode,
    Notifications,
    PnlPeriod,
    Portfolio,
    PortfolioHistory,
    PortfolioPnl,
    PortfolioRebalances,
    QuizRequest,
    RunSummary,
    TriggerKind,
)
from app.sim import approvals
from app.sim.approvals import ApprovalError
from app.sim.controller import SimError
from app.sim.evaluate import benchmarks_payload

router = APIRouter(prefix="/api")
log = logging.getLogger(__name__)


def S(request: Request, mode: Mode | None = None):
    state = request.app.state.app
    # Legacy/offline states may keep both modes in one log; recorded demos have isolated DBs.
    isolated = any(st.recording is not None for st in state.modes.values())
    return state_for_mode(state, mode) if mode is not None and isolated else state


def err(status: int, code: str, message: str):
    raise HTTPException(status_code=status, detail={"error": {"code": code, "message": message, "details": {}}})


# ------------------------------------------------------------------ system
@router.get("/health")
def health(request: Request):
    s = S(request)
    return {"status": "ok", "mode": s.clock.mode, "as_of": s.clock.as_of_str(), "version": "0.1.0",
            "llm_mode": s.llm.mode, "data_source": s.gw.snapshot.source_label}


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
@router.get("/profile/demo")
def get_demo_profile() -> DemoProfile:
    return demo_profile()


def require_live_profile(request: Request) -> None:
    if S(request).clock.mode == "historical":
        err(409, "validation_error", "This demo follows Priya. Switch to live mode to create your own profile.")


@router.get("/profile/questions")
def profile_questions():
    return {"questions": questions_payload()}


@router.post("/profile/quiz", dependencies=[Depends(require_live_profile)])
def profile_quiz(body: QuizRequest, request: Request):
    result = score(body.answers, body.follow_up_answer)
    mandate = mandate_for(result.name, body.goal, body.exclusions)
    if fields := validate_mandate(mandate):
        raise HTTPException(422, detail={"error": {"code": "validation_error", "message": "Invalid mandate.",
                                                  "details": {"fields": fields}}})
    s = S(request)
    with s.mandate_lock:
        mandate = save_mandate(s, mandate)
    return {"profile": result.model_dump(), "mandate": mandate.model_dump()}


@router.get("/mandate")
def get_mandate(request: Request) -> Mandate:
    return S(request).mandate


@router.put("/mandate", dependencies=[Depends(require_live_profile)])
def put_mandate(body: Mandate, request: Request) -> Mandate:
    s = S(request)
    with s.mandate_lock:
        if fields := validate_mandate(body, s.mandate):
            raise HTTPException(422, detail={"error": {"code": "validation_error", "message": "Invalid mandate.",
                                                      "details": {"fields": fields}}})
        return save_mandate(s, body)


@router.get("/catalogue")
def catalogue(request: Request):
    return {"instruments": [i.model_dump() for i in S(request).gw.catalogue()]}


# ------------------------------------------------------------------ portfolio
@router.post("/portfolio/build", status_code=202, dependencies=[Depends(guard_agent_run)])
async def build(request: Request):
    s = S(request)
    if s.recording is not None:
        recorded = s.recording.construction
        if recorded is None or recorded.as_of > s.clock.as_of_str():
            err(404, "not_found", "No construction run is visible in this recording")
        return {"run_id": recorded.run_id}
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
    s = S(request, mode)
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
    return PortfolioView(S(request, mode), mode).history(start.isoformat() if start else None, end.isoformat() if end else None)


@router.get("/portfolio/pnl")
def pnl(request: Request, mode: Mode | None = None, period: PnlPeriod = "since_purchase") -> PortfolioPnl:
    try:
        return PortfolioView(S(request, mode), mode).pnl(period)
    except PortfolioDataUnavailable as exc:
        err(409, "validation_error", str(exc))


@router.get("/portfolio/rebalances")
def rebalances(request: Request, mode: Mode | None = None, limit: int = Query(default=20, ge=1)) -> PortfolioRebalances:
    return PortfolioView(S(request, mode), mode).rebalances(limit)


@router.get("/benchmarks")
def benchmarks(request: Request, mode: Mode | None = None):
    """Same numbers as eval/metrics.json (#24): the last finished replay in this mode's DB."""
    s = S(request, mode)
    if s.recording is not None:
        payload = s.recording.benchmarks
        if s.clock.as_of_str() < s.recording.end_day:
            return {"series": {}, "metrics": {}, "periods": payload["periods"]}
        return payload
    return benchmarks_payload(s.db)


@router.get("/risk/correlation")
def correlation(request: Request, lookback: int | None = None, tickers: str | None = None,
                as_of: str | None = None, mode: Mode | None = None):
    """Correlation lattice as of `as_of` (any past date up to the clock; default = now)."""
    s = S(request, mode)
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
    s = S(request, mode)
    rows = s.db.execute(
        """SELECT json FROM events
           WHERE run_id IS NOT NULL AND mode = ? AND as_of <= ? AND type IN ('run.started', 'run.completed')
           ORDER BY ts_wall""",
        (mode or s.clock.mode, s.clock.as_of_str()),
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
    recorded = S(request).recording is not None
    if format == "json":
        return {"items": [e.model_dump() for e in bus.history(run_id, after)]}
    if recorded and (cursor := request.headers.get("last-event-id")):
        try:
            after = max(after, int(cursor))
        except ValueError:
            err(422, "validation_error", "Last-Event-ID must be an event sequence number")
        if not bus.history(run_id, after) and any(e.type == "run.completed" for e in bus.history(run_id)):
            # EventSource stops reconnecting on 204. A broken connection before the last frame
            # instead resumes after its saved sequence and still receives trailing gate evidence.
            return Response(status_code=204)

    def frame(event: Event) -> str:
        return f"id: {event.seq}\n{sse_frame(event)}" if recorded else sse_frame(event)

    async def stream():
        q = bus.subscribe(run_id)
        try:
            last = after
            history = bus.history(run_id, after)
            for e in history:
                last = e.seq
                yield frame(e)
            if recorded and any(e.type == "run.completed" for e in bus.history(run_id)):
                return
            while True:
                if await request.is_disconnected():
                    break
                try:
                    e = await asyncio.wait_for(q.get(), timeout=15)
                    if e.seq > last:
                        last = e.seq
                        yield frame(e)
                        if recorded and e.type == "run.completed":
                            while not q.empty():
                                trailing = q.get_nowait()
                                if trailing.seq > last:
                                    last = trailing.seq
                                    yield frame(trailing)
                            return
                except TimeoutError:
                    yield ": ping\n\n"
        finally:
            bus.unsubscribe(q)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/events/stream")
async def all_events(request: Request, mode: Mode | None = None):
    bus = S(request, mode).events

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
    s = S(request)
    p = (s.recording.visible_proposal(proposal_id) if s.recording is not None
         else s.proposals.get(proposal_id))
    if not p or p.as_of > s.clock.as_of_str():
        err(404, "not_found", "proposal not found")
    return p


class ApproveBody(BaseModel):
    option: str | None = None


class DeclineBody(BaseModel):
    reason: str | None = None


def _approval_err(e: ApprovalError):
    raise HTTPException(status_code=e.status,
                        detail={"error": {"code": e.code, "message": e.message, "details": e.details}})


@router.post("/proposals/{proposal_id}/approve")
async def approve(proposal_id: str, request: Request, body: ApproveBody | None = None):
    s = S(request)
    if s.recording is not None:
        err(409, "validation_error", "This is a recorded demo. Switch to live mode to make your own decisions.")
    try:
        out = approvals.approve_by_user(s, proposal_id, (body or ApproveBody()).option)
    except ApprovalError as e:
        _approval_err(e)
    await sim_controller(s).after_decision()
    return out


@router.post("/proposals/{proposal_id}/decline")
async def decline(proposal_id: str, request: Request, body: DeclineBody | None = None):
    s = S(request)
    if s.recording is not None:
        err(409, "validation_error", "This is a recorded demo. Switch to live mode to make your own decisions.")
    try:
        out = approvals.decline_by_user(s, proposal_id, (body or DeclineBody()).reason)
    except ApprovalError as e:
        _approval_err(e)
    await sim_controller(s).after_decision()
    return out


@router.get("/evidence/{evidence_id}")
def evidence(evidence_id: str, request: Request) -> Evidence:
    s = S(request)
    item = find_evidence(s.gw, s.db, evidence_id)
    if item is None:
        err(404, "not_found", "evidence not found")
    return item


@router.get("/notifications")
async def notifications(request: Request, mode: Mode | None = None, unread: bool = False) -> Notifications:
    s = S(request, mode)
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
    if b.run_agents:
        guard_agent_run(request)
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


@router.post("/chat", dependencies=[Depends(require_passcode)])
def chat(body: ChatBody, request: Request):
    s = S(request)
    if s.settings.public_demo and s.settings.llm_mode == "live":
        check_budget(s)
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

