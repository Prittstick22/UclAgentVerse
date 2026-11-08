"""Approve / decline (#23): revalidate, queue for the next close, 409s for duplicate / mandate change / stale."""
import asyncio
import time

import pytest
from fastapi.testclient import TestClient

from app.config import params
from app.profile.quiz import mandate_for
from app.sim import runner

START = params()["sim"]["start"]


def _day(state, n):
    return str(state.gw.trading_days(START)[n].date())


@pytest.fixture()
def api(state, monkeypatch):
    from app.main import app

    monkeypatch.setattr(app.state, "app", state, raising=False)
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def waiting(state):
    """A manual agent replay: day 0 construction proposal waiting for the user (money in cash)."""
    sim = runner.Simulation(state, START, _day(state, 20), agents=True, approvals="manual")
    asyncio.run(sim.step())
    prop = next(p for p in state.proposals.values() if p.status == "awaiting_approval")
    return sim, prop


def test_approve_queues_orders_for_the_next_close(api, state, waiting):
    sim, prop = waiting
    r = api.post(f"/api/proposals/{prop.id}/approve", json={})
    assert r.status_code == 200, r.json()
    body = r.json()
    assert body["proposal"]["status"] == "approved" and body["fill_date"] == _day(state, 1)
    assert body["orders"] and all(o["action"] == "buy" for o in body["orders"])
    assert state.ledger.pending and not state.ledger.fills
    asyncio.run(sim.step())                                   # next close
    assert state.ledger.fills and state.ledger.fills[0].date == _day(state, 1)
    decided = [e for e in state.events.history(limit=100000) if e.type == "approval.decided"]
    assert decided[-1].payload == {**decided[-1].payload, "decision": "approved", "by": "user"}


def test_approve_twice_is_409_duplicate(api, waiting):
    _, prop = waiting
    assert api.post(f"/api/proposals/{prop.id}/approve").status_code == 200
    r = api.post(f"/api/proposals/{prop.id}/approve")
    assert r.status_code == 409 and r.json()["error"]["code"] == "duplicate_order"


def test_approve_after_mandate_edit_is_409_mandate_changed(api, state, waiting):
    _, prop = waiting
    m = state.mandate.model_dump()
    m["caps"]["per_fund"] = 0.40
    assert api.put("/api/mandate", json=m).status_code == 200
    r = api.post(f"/api/proposals/{prop.id}/approve")
    assert r.status_code == 409 and r.json()["error"]["code"] == "mandate_changed"
    assert not state.ledger.pending


def test_new_quiz_profile_counts_as_a_mandate_change(api, state, waiting):
    _, prop = waiting
    state.mandate = mandate_for("growth")       # same version number, different rules
    r = api.post(f"/api/proposals/{prop.id}/approve")
    assert r.status_code == 409 and r.json()["error"]["code"] == "mandate_changed"


def test_old_proposal_is_409_stale(api, state, waiting):
    sim, prop = waiting
    for _ in range(5):
        asyncio.run(sim.step())
    r = api.post(f"/api/proposals/{prop.id}/approve")
    assert r.status_code == 409 and r.json()["error"]["code"] == "stale_data"


def test_holdings_changed_since_proposal_is_409(api, state, waiting):
    _, prop = waiting
    state.ledger.deposit(1.0)
    state.ledger.mark_to_market(state.gw.latest_prices().to_dict())
    state.ledger.rebalance_to({"VWRP.LSE": 0.5}, state.clock.as_of_str())   # a trade filled meanwhile
    r = api.post(f"/api/proposals/{prop.id}/approve")
    assert r.status_code == 409 and r.json()["error"]["code"] == "holdings_changed"


def test_option_choice_and_unknown_option(api, waiting):
    _, prop = waiting
    labels = [o.label for o in prop.options]
    assert api.post(f"/api/proposals/{prop.id}/approve", json={"option": "nope"}).status_code == 422
    other = next(lb for lb in labels if lb != prop.selected)
    r = api.post(f"/api/proposals/{prop.id}/approve", json={"option": other})
    assert r.status_code == 200 and r.json()["proposal"]["selected"] == other


def test_mandate_violation_is_409(api, state, waiting):
    _, prop = waiting
    opt = next(o for o in prop.options if o.label == prop.selected)
    opt.holdings[0].weight = 0.95
    r = api.post(f"/api/proposals/{prop.id}/approve")
    assert r.status_code == 409 and r.json()["error"]["code"] == "mandate_violation"


def test_decline_records_reason_and_blocks_approval(api, state, waiting):
    _, prop = waiting
    r = api.post(f"/api/proposals/{prop.id}/decline", json={"reason": "Too much in one fund"})
    assert r.status_code == 200 and r.json()["proposal"]["status"] == "declined"
    assert "Declined: Too much in one fund" in r.json()["proposal"]["uncertainties"]
    assert not state.ledger.pending
    assert api.post(f"/api/proposals/{prop.id}/approve").status_code == 409
    assert api.post(f"/api/proposals/{prop.id}/decline").status_code == 409
    assert api.post("/api/proposals/nope/decline").status_code == 404


def test_running_replay_pauses_for_approval_then_resumes(api, state):
    api.post("/api/sim/start", json={"end": _day(state, 8), "speed": 0, "run_agents": True})
    t = time.monotonic()
    while api.get("/api/sim/status").json()["sim"]["running"] and time.monotonic() - t < 20:
        time.sleep(0.05)
    st = api.get("/api/sim/status").json()
    assert st["as_of"] == START and st["progress"] < 1          # paused on day 0, waiting for the user
    prop = next(p for p in state.proposals.values() if p.status == "awaiting_approval")
    assert api.post(f"/api/proposals/{prop.id}/approve").status_code == 200
    t = time.monotonic()
    while api.get("/api/sim/status").json()["progress"] < 1 and time.monotonic() - t < 20:
        time.sleep(0.05)
    assert api.get("/api/sim/status").json()["progress"] == 1.0  # resumed by the approval
    assert state.ledger.fills and state.ledger.fills[0].date == _day(state, 1)


def test_refused_approval_does_not_change_the_selected_option(api, state, waiting):
    _, prop = waiting
    other = next(o.label for o in prop.options if o.label != prop.selected)
    before = prop.selected
    state.mandate = mandate_for("growth")
    assert api.post(f"/api/proposals/{prop.id}/approve", json={"option": other}).status_code == 409
    assert prop.selected == before


def test_second_proposal_cannot_replace_a_queued_order(api, state, waiting):
    _, prop = waiting
    twin = prop.model_copy(update={"id": "prop_twin", "status": "awaiting_approval"})
    state.proposals[twin.id] = twin
    assert api.post(f"/api/proposals/{prop.id}/approve").status_code == 200
    r = api.post(f"/api/proposals/{twin.id}/approve")
    assert r.status_code == 409 and r.json()["error"]["code"] == "duplicate_order"
    assert state.ledger.pending[0]["reason"] == f"proposal:{prop.id}"


def test_orders_only_list_trades_the_ledger_will_make(api, waiting):
    _, prop = waiting
    body = api.post(f"/api/proposals/{prop.id}/approve").json()
    assert all(o["amount_gbp"] >= params()["min_trade_gbp"] for o in body["orders"])


def test_approved_proposal_becomes_executed_when_it_fills(api, state, waiting):
    sim, prop = waiting
    api.post(f"/api/proposals/{prop.id}/approve")
    asyncio.run(sim.step())
    assert state.proposals[prop.id].status == "executed"


def test_batch_approved_proposal_is_executed_after_fill(state):
    asyncio.run(runner.run(state, START, _day(state, 3), agents=True, approvals="batch_policy"))
    assert [p.status for p in state.proposals.values()] == ["executed"]
