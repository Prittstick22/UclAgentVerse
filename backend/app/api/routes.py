"""HTTP routes per docs/04-api-contracts.md. Owner: Jin (routing) with Cem/Dev for their handlers.

SCAFFOLD: every endpoint exists with the contract shape. Endpoints marked TODO return valid-but-empty data so the
frontend can integrate now. Replace each TODO in its issue.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import date

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.api.run_views import agent_tree, find_evidence, summarize
from app.core.events import Event, sse_frame
from app.data.gateway import AsOfViolation
from app.engine import risk
from app.profile.quiz import mandate_for, questions_payload, score
from app.schemas import Evidence, Goal, Mandate, Mode, Notifications, Portfolio, RunSummary, TriggerKind

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
    return {"mode": s.clock.mode, "as_of": s.clock.as_of_str(),
            "sim": {"running": False, "speed": 1, "start": None, "end": None}}  # TODO(#sim-api)


class ModeBody(BaseModel):
    mode: str


@router.post("/mode")
def set_mode(body: ModeBody, request: Request):
    err(501, "internal", "TODO(#11): swap SimClock/LiveClock and the portfolio namespace")


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
async def portfolio(request: Request) -> Portfolio:
    s = S(request)
    led = s.ledger  # TODO(#21): holdings with P&L, targets and purposes
    activity = s.activity.snapshot(s.clock.mode)
    return Portfolio(mode=s.clock.mode, as_of=s.clock.as_of_str(), nav_gbp=round(led.nav(), 2),
                     cash_gbp=round(led.cash_gbp, 2), invested_gbp=round(led.nav() - led.cash_gbp, 2),
                     contributions_gbp=led.contributions_gbp, total_return=0.0, status=activity.status,
                     counters=activity.counters, last_review_date=activity.last_review_date)


@router.get("/portfolio/history")
def history(request: Request):
    pts = [{"date": e.as_of, "nav_gbp": e.payload.get("nav_gbp"), "weights": e.payload.get("weights", {}),
            "contributions_gbp": None} for e in S(request).events.history(None) if e.type == "clock.tick"]
    return {"points": pts}


@router.get("/portfolio/pnl")
def pnl(request: Request, period: str = "since_purchase"):
    return {"period": period, "rows": [], "total_pnl_gbp": 0.0}  # TODO(#pnl)


@router.get("/portfolio/rebalances")
def rebalances(request: Request, limit: int = 20):
    return {"items": []}  # TODO(#rebalances)


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
@router.post("/sim/start")
def sim_start(request: Request):
    err(501, "internal", "TODO(#sim-api): start runner as a background task")


@router.post("/sim/pause")
def sim_pause(request: Request):
    err(501, "internal", "TODO(#22)")


@router.post("/sim/step")
def sim_step(request: Request):
    err(501, "internal", "TODO(#22)")


@router.get("/sim/status")
def sim_status(request: Request):
    s = S(request)
    return {"sim": {"running": False, "speed": 1, "start": None, "end": None}, "as_of": s.clock.as_of_str(),
            "progress": 0.0}


class ChatBody(BaseModel):
    message: str
    conversation_id: str | None = None


@router.post("/chat")
def chat(body: ChatBody, request: Request):
    return {"conversation_id": body.conversation_id or "conv_1", "run_id": None,
            "answer": "Chat isn't wired up yet (TODO #chat).", "citations": [], "proposal_id": None}


@router.post("/tasks/live-eod")
def live_eod(request: Request):
    s = S(request)
    if not s.settings.task_secret or request.headers.get("X-Task-Secret") != s.settings.task_secret:
        err(401, "unauthorized", "bad task secret")
    return {"ok": False, "fetched": 0, "stale": []}  # TODO(#live-mode)


@router.post("/tasks/live-news")
def live_news(request: Request):
    s = S(request)
    if not s.settings.task_secret or request.headers.get("X-Task-Secret") != s.settings.task_secret:
        err(401, "unauthorized", "bad task secret")
    return {"ok": False, "fetched": 0, "stale": []}  # TODO(#11)
