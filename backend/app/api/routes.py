"""HTTP routes per docs/04-api-contracts.md. Owner: Jin (routing) with Cem/Dev for their handlers.

SCAFFOLD: every endpoint exists with the contract shape. Endpoints marked TODO return valid-but-empty data so the
frontend can integrate now. Replace each TODO in its issue.
"""
from __future__ import annotations

import asyncio
import json

from datetime import date

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.events import sse_frame
from app.data.gateway import AsOfViolation
from app.engine import risk
from app.profile.quiz import mandate_for, questions_payload, score
from app.schemas import Goal, Mandate, Portfolio

router = APIRouter(prefix="/api")


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
async def build(request: Request, background: BackgroundTasks):
    s = S(request)
    task = asyncio.create_task(s.supervisor.start("construction", "User asked to build a portfolio"))
    await asyncio.sleep(0)  # let run.started emit so we can return its id
    runs = s.events.history(None)
    started = [e for e in runs if e.type == "run.started"]
    background.add_task(lambda: None)
    s.runs["latest_task"] = task
    return {"run_id": started[-1].run_id if started else None}


@router.get("/portfolio")
def portfolio(request: Request) -> Portfolio:
    s = S(request)
    led = s.ledger  # TODO(#portfolio-api): holdings with P&L, targets, purposes, status, counters
    return Portfolio(mode=s.clock.mode, as_of=s.clock.as_of_str(), nav_gbp=round(led.nav(), 2),
                     cash_gbp=round(led.cash_gbp, 2), invested_gbp=round(led.nav() - led.cash_gbp, 2),
                     contributions_gbp=led.contributions_gbp, total_return=0.0)


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
@router.get("/runs")
def runs(request: Request, limit: int = 50):
    evs = [e for e in S(request).events.history(None) if e.type in ("run.started", "run.completed")]
    by_run: dict[str, dict] = {}
    for e in evs:
        r = by_run.setdefault(e.run_id, {"run_id": e.run_id, "kind": e.trigger_kind, "trigger_text": e.trigger_text,
                                         "as_of": e.as_of, "status": "running", "outcome": None,
                                         "started_at": e.ts_wall, "finished_at": None, "agents": [],
                                         "proposal_id": None})
        if e.type == "run.completed":
            r.update(status="completed", outcome=e.payload.get("outcome"), finished_at=e.ts_wall,
                     proposal_id=e.payload.get("proposal_id"))
    return {"items": list(by_run.values())[-limit:]}


@router.get("/runs/{run_id}")
def run_detail(run_id: str, request: Request):
    items = runs(request, limit=10_000)["items"]
    for r in items:
        if r["run_id"] == run_id:
            agents = {}
            for e in S(request).events.history(run_id):  # TODO(#runs-api): badges from gate verdicts
                if e.type == "agent.spawned":
                    agents[e.agent_id] = {"agent_id": e.agent_id, "parent_agent_id": e.parent_agent_id,
                                          "depth": e.depth, "role": e.role, "model": e.payload.get("model"),
                                          "question": e.payload.get("question"), "purpose": e.purpose,
                                          "status": "running", "badges": []}
                if e.type == "agent.status" and e.agent_id in agents:
                    agents[e.agent_id]["status"] = "done"
            return {**r, "agents": list(agents.values())}
    err(404, "not_found", f"run {run_id} not found")


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
                except asyncio.TimeoutError:
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
                except asyncio.TimeoutError:
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
def evidence(evidence_id: str, request: Request):
    err(404, "not_found", "TODO(#evidence): look up news/filing/calc by id")


@router.get("/notifications")
def notifications(request: Request):
    return {"items": []}  # TODO(#notifications)


# ------------------------------------------------------------------ sim, chat, tasks
@router.post("/sim/start")
def sim_start(request: Request):
    err(501, "internal", "TODO(#sim-api): start runner as a background task")


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


_ = json  # keep import for handlers that need it
