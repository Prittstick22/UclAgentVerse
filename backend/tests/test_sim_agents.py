"""Sim ↔ agents (#22): supervisor on review/trigger days, approval policy, sim API controls."""
import asyncio
import time

import pytest
from fastapi.testclient import TestClient

from app.config import params
from app.schemas import GateResult
from app.sim import approvals, runner

START = params()["sim"]["start"]


def _end(state, n):
    return str(state.gw.trading_days(START)[n].date())


def _events(state, kind):
    return [e for e in state.events.history(limit=100000) if e.type == kind]


# ------------------------------------------------------------------ agents in the loop
def test_two_week_agent_run_with_batch_policy_trades_and_records(state):
    r = asyncio.run(runner.run(state, START, _end(state, 10), agents=True, approvals="batch_policy"))
    assert r.runs[0]["kind"] == "construction" and r.runs[0]["action"] == "approved"
    assert state.ledger.fills and min(f.date for f in state.ledger.fills) == r.nav_series[1][0]   # t+1 fill
    props = list(state.proposals.values())
    assert props and props[0].status == "executed" and props[0].kind == "construction"
    decided = _events(state, "approval.decided")
    assert decided and decided[0].payload["by"] == "batch_policy"
    started = _events(state, "run.started")   # timeline markers
    assert {e.trigger_kind for e in started} >= {"construction", "review"}
    assert all(e.as_of and e.trigger_text for e in started)
    assert len(started) == len(r.runs)


def test_manual_approval_waits_in_cash_and_says_so(state):
    r = asyncio.run(runner.run(state, START, _end(state, 3), agents=True, approvals="manual"))
    assert r.runs[0]["action"] == "awaiting_approval"
    assert not state.ledger.fills and state.ledger.cash_gbp == params()["sim"]["capital_gbp"]
    assert _events(state, "approval.requested")
    assert _events(state, "clock.tick")[-1].payload["status"] == "awaiting_approval"


def test_crashing_agent_run_holds_instead_of_stopping_the_sim(state, monkeypatch):
    async def boom(kind, text, *a, **k):
        raise RuntimeError("model down")

    monkeypatch.setattr(state.supervisor, "start", boom)
    r = asyncio.run(runner.run(state, START, _end(state, 12), agents=True, approvals="batch_policy"))
    assert r.days == 13 and r.runs[0]["action"] == "agent_failed"
    assert state.ledger.fills   # engine fallback built the starting portfolio, labelled as such
    assert any("engine built the starting portfolio" in e.payload["reason"] for e in _events(state, "decision.made"))


# ------------------------------------------------------------------ approval policy
def _proposal(state):
    asyncio.run(runner.run(state, START, _end(state, 1), agents=True, approvals="manual"))
    return next(iter(state.proposals.values()))


def test_checker_blocks_a_proposal_that_breaks_the_mandate(state):
    prop = _proposal(state)
    opt = next(o for o in prop.options if o.label == prop.selected)
    opt.holdings[0].weight = 0.95   # way over the per-fund cap
    targets, outcome = approvals.handle(state, prop, "batch_policy", construction=True)
    assert targets is None and outcome == "blocked" and prop.status == "blocked"
    assert _events(state, "gate.verdict")[-1].payload["status"] == "fail"


def test_failed_gate_blocks_batch_approval(state):
    prop = _proposal(state)
    prop.gates = [GateResult(gate="critic", status="fail", issues=["weak evidence"])]
    assert approvals.handle(state, prop, "batch_policy", construction=True) == (None, "blocked")


def test_batch_turnover_limit_applies_to_adjustments_not_construction(state):
    m = state.mandate
    limit = m.approval.batch_auto_approve_turnover_max
    assert approvals.batch_allows(True, 1.0, m, construction=True)
    assert approvals.batch_allows(True, limit, m) and not approvals.batch_allows(True, limit + 0.01, m)
    assert not approvals.batch_allows(False, 0.0, m)
    prop = _proposal(state)
    _, outcome = approvals.handle(state, prop, "batch_policy", construction=False)   # 100% turnover from cash
    assert outcome == "awaiting_approval"


# ------------------------------------------------------------------ API
@pytest.fixture()
def api(state, monkeypatch):
    from app.main import app

    monkeypatch.setattr(app.state, "app", state, raising=False)
    with TestClient(app) as c:
        yield c


def _wait(api, cond, timeout=30):
    t = time.monotonic()
    while time.monotonic() - t < timeout:
        st = api.get("/api/sim/status").json()
        if cond(st):
            return st
        time.sleep(0.05)
    raise AssertionError(f"timed out: {st}")


def test_api_step_advances_days(api, state):
    r = api.post("/api/sim/step", json={"days": 3})
    assert r.status_code == 200 and r.json()["as_of"] == _end(state, 2)
    st = api.get("/api/sim/status").json()
    assert not st["sim"]["running"] and st["sim"]["start"] == START and 0 < st["progress"] < 1
    assert api.get("/api/mode").json()["sim"]["start"] == START


def test_api_start_runs_to_the_end(api, state):
    r = api.post("/api/sim/start", json={"end": _end(state, 15), "speed": 0})
    assert r.status_code == 200 and r.json()["sim"]["end"] == _end(state, 15)
    st = _wait(api, lambda s: s["progress"] == 1.0 and not s["sim"]["running"])
    assert st["as_of"] == _end(state, 15)
    assert state.ledger.nav() > 0 and state.ledger.fills


def test_api_pause_then_step_then_conflicts(api, state):
    api.post("/api/sim/start", json={"speed": 20})
    _wait(api, lambda s: s["progress"] > 0)
    assert api.post("/api/sim/start", json={}).status_code == 409      # already running
    assert api.post("/api/sim/step", json={"days": 1}).status_code == 409
    paused = api.post("/api/sim/pause").json()
    assert not paused["sim"]["running"]
    p0 = api.get("/api/sim/status").json()["progress"]
    assert 0 < p0 < 1
    api.post("/api/sim/step", json={"days": 2})
    assert api.get("/api/sim/status").json()["progress"] > p0


def test_api_rejects_bad_input(api):
    assert api.post("/api/sim/start", json={"start": "2030-01-01", "end": "2030-02-01"}).status_code == 422
    assert api.post("/api/sim/start", json={"speed": -1}).status_code == 422
    assert api.post("/api/sim/step", json={"days": 0}).status_code == 422


def test_api_restart_replaces_history_and_expires_old_proposals(api, state):
    from app.engine.portfolio import checkpoints

    api.post("/api/sim/start", json={"end": _end(state, 12), "speed": 0, "run_agents": True,
                                     "approvals": "batch_policy"})
    _wait(api, lambda s: s["progress"] == 1.0 and not s["sim"]["running"])
    api.post("/api/sim/start", json={"end": _end(state, 6), "speed": 0, "run_agents": True})   # manual
    _wait(api, lambda s: not s["sim"]["running"])          # pauses on day 0 for the user's approval
    api.post("/api/sim/start", json={"end": _end(state, 4), "speed": 0})
    _wait(api, lambda s: s["progress"] == 1.0 and not s["sim"]["running"])
    days = [c.date for c in checkpoints(state.db, state.clock.mode)]
    assert max(days) == _end(state, 4)   # nothing left over from the longer first replay
    assert all(p.status in ("executed", "expired", "blocked") for p in state.proposals.values())


def test_pause_returns_quickly_even_mid_day(state):
    from app.sim.controller import SimController

    async def go():
        ctl = SimController(state)
        gate = asyncio.Event()
        real = state.supervisor.start

        async def slow(kind, text, *a, **k):
            await gate.wait()
            return await real(kind, text, *a, **k)

        state.supervisor.start = slow
        await ctl.start(end=_end(state, 5), speed=0, run_agents=True)
        await asyncio.sleep(0.05)
        t = time.monotonic()
        info = await ctl.pause(wait_s=0.2)
        assert time.monotonic() - t < 1 and info["running"]   # still finishing day 0's agent run
        gate.set()
        await ctl.task
        assert not ctl.running and ctl.sim.i == 1             # stopped after that day

    asyncio.run(go())
