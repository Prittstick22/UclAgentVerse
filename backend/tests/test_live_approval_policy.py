"""Live paper approval policy and durable next-close execution (#48)."""
import asyncio
import json
from datetime import datetime, time

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.container import build_state
from app.core.clock import LONDON, SimClock
from app.data.live import LiveUpdates
from app.settings import Settings
from app.sim.approvals import fill_live_orders


class LiveTestClock(SimClock):
    mode = "live"

    def now(self):
        return datetime.combine(self._day, time(22), tzinfo=LONDON)


@pytest.fixture
def live_api(snapshot_dir, tmp_path, monkeypatch):
    from app.main import app

    settings = Settings(_env_file=None, snapshot_dir=snapshot_dir, app_mode="live", llm_mode="fake",
                        state_db=tmp_path / "visitor.sqlite")
    state = build_state(settings)
    state.clock = state.gw.clock = state.events.clock = LiveTestClock("2026-11-05")
    monkeypatch.setattr(app.state, "app", state, raising=False)
    with TestClient(app) as client:
        yield client, state


def _save_policy(client, *, manual, cap):
    mandate = client.get("/api/mandate").json()
    mandate["approval"] = {"require_user_approval": manual, "batch_auto_approve_turnover_max": cap}
    response = client.put("/api/mandate", json=mandate)
    assert response.status_code == 200, response.text
    return response.json()


def _build(client, state, monkeypatch, *, unfinished=False):
    release = asyncio.Event()
    original_start = state.supervisor.start

    async def start(*args, **kwargs):
        await release.wait()
        run = await original_start(*args, **kwargs)
        if unfinished:
            state.proposals[run.proposal_id].gates[0].status = "pending"
        return run

    with monkeypatch.context() as patched:
        patched.setattr(state.supervisor, "start", start)
        response = client.post("/api/portfolio/build")
        assert response.status_code == 202, response.text
        run_id = response.json()["run_id"]

        async def finish():
            task = state.runs[run_id]
            release.set()
            await task

        client.portal.call(finish)
    proposal = next(item for item in state.proposals.values() if item.run_id == run_id)
    return proposal, state.events.history(run_id)


def test_default_manual_decline_survives_restart_and_opt_in(live_api, monkeypatch):
    client, state = live_api
    assert client.get("/api/mandate").json()["approval"]["require_user_approval"] is True
    proposal, events = _build(client, state, monkeypatch)
    assert proposal.status == "awaiting_approval"
    assert any(event.type == "approval.requested" for event in events)
    assert not state.ledger.pending and not state.ledger.positions and state.ledger.cash_gbp == 0
    endpoint = f"/api/proposals/{proposal.id}"
    response = client.post(endpoint + "/decline", json={"reason": "Keep the current portfolio"})
    assert response.status_code == 200 and response.json()["proposal"]["status"] == "declined"
    assert json.loads(state.db.get("proposal_decisions", proposal.id))["decision"] == "declined"
    saved = _save_policy(client, manual=False, cap=1)
    assert client.post(endpoint + "/approve").status_code == 409
    restarted = build_state(state.settings)
    assert restarted.mandate.model_dump(mode="json") == saved
    assert restarted.proposals[proposal.id].status == "declined"
    assert not restarted.ledger.pending and not restarted.ledger.positions and restarted.ledger.cash_gbp == 0


def test_live_policy_counts_cash_and_can_be_turned_off(live_api, monkeypatch):
    client, state = live_api
    _save_policy(client, manual=False, cap=0.5)
    outside, events = _build(client, state, monkeypatch)
    assert outside.status == "awaiting_approval"
    assert any(event.type == "approval.requested" for event in events)
    assert not state.ledger.pending
    assert client.post(f"/api/proposals/{outside.id}/decline").status_code == 200

    _save_policy(client, manual=False, cap=1)
    approved, events = _build(client, state, monkeypatch)
    assert approved.status == "approved"
    assert not any(event.type == "approval.requested" for event in events)
    decision, = [event for event in events if event.type == "approval.decided"]
    assert decision.payload["by"] == "user_policy"
    assert decision.payload["fill_date"] == "2026-11-06"
    assert 0.5 < decision.payload["turnover"] <= 1
    assert state.ledger.pending[0]["reason"] == f"proposal:{approved.id}"
    assert not state.ledger.positions and not state.ledger.fills
    assert client.post(f"/api/proposals/{approved.id}/decline").status_code == 409

    _save_policy(client, manual=True, cap=1)
    manual, events = _build(client, state, monkeypatch)
    assert manual.status == "awaiting_approval"
    assert any(event.type == "approval.requested" for event in events)
    assert state.ledger.pending[0]["reason"] == f"proposal:{approved.id}"


def test_unfinished_gate_cannot_queue_live_orders(live_api, monkeypatch):
    client, state = live_api
    _save_policy(client, manual=False, cap=1)
    proposal, events = _build(client, state, monkeypatch, unfinished=True)
    assert proposal.status == "blocked"
    assert not any(event.type in ("approval.decided", "approval.requested") for event in events)
    assert client.post(f"/api/proposals/{proposal.id}/approve").status_code == 409
    assert not state.ledger.pending


def test_live_order_fills_once_after_complete_close_and_survives_restart(live_api, tmp_path, monkeypatch):
    client, state = live_api
    proposal, _ = _build(client, state, monkeypatch)
    approval = client.post(f"/api/proposals/{proposal.id}/approve")
    assert approval.status_code == 200, approval.text
    assert approval.json()["orders"] and approval.json()["fill_date"] == "2026-11-06"
    fill_live_orders(state)
    assert state.ledger.pending and not state.ledger.fills

    restarted = build_state(state.settings)
    restarted.clock = restarted.gw.clock = restarted.events.clock = LiveTestClock("2026-11-06")
    assert restarted.ledger.pending == state.ledger.pending
    missing = next(iter(restarted.ledger.pending[0]["target_weights"]))
    snapshot = restarted.gw.snapshot
    dates = pd.to_datetime(snapshot.prices.date)
    snapshot.prices = snapshot.prices.loc[~(snapshot.prices.ticker.eq(missing) & dates.eq("2026-11-06"))]
    restarted.gw.replace_snapshot(snapshot)
    fill_live_orders(restarted)
    assert restarted.ledger.pending and not restarted.ledger.fills

    class OfflinePrices:
        def __init__(self, *_):
            self.client = self

        def close(self):
            pass

        def eod(self, ticker, *_):
            price = 1.25 if ticker == "GBPUSD.FOREX" else 100
            return [{"date": "2026-11-06", "open": price, "high": price, "low": price,
                     "close": price, "adjusted_close": price, "volume": 100}]

    monkeypatch.setattr("app.data.live.EODHD", OfflinePrices)
    restarted.settings.eodhd_api_key = "offline-test"
    restarted.settings.snapshot_dir = tmp_path
    assert LiveUpdates(restarted).refresh("eod")["ok"]
    assert restarted.proposals[proposal.id].status == "executed"
    assert not restarted.ledger.pending
    assert restarted.ledger.fills and {fill.date for fill in restarted.ledger.fills} == {"2026-11-06"}
    events = [event for event in restarted.events.history(proposal.run_id) if event.type == "order.filled"]
    assert len(events) == len(restarted.ledger.fills)
    assert all(event.payload["proposal_id"] == proposal.id for event in events)
    assert restarted.db.get("ledger_checkpoints:live", "2026-11-06")

    restored = build_state(state.settings)
    assert restored.ledger.fills == restarted.ledger.fills
    fill_live_orders(restored)
    assert len([event for event in restored.events.history(proposal.run_id) if event.type == "order.filled"]) == len(events)


def test_home_review_requires_holdings_and_starts_one_supervised_run(live_api, monkeypatch):
    client, state = live_api
    assert client.post("/api/portfolio/review").status_code == 409

    state.ledger.deposit(10_000)
    state.ledger.mark_to_market(state.gw.latest_prices().to_dict())
    state.ledger.rebalance_to({"VUAG.LSE": 0.4, "VGOV.LSE": 0.3, "VAGS.LSE": 0.2}, state.clock.as_of_str())
    release = asyncio.Event()
    original_start = state.supervisor.start

    async def start(*args, **kwargs):
        await release.wait()
        return await original_start(*args, **kwargs)

    monkeypatch.setattr(state.supervisor, "start", start)
    response = client.post("/api/portfolio/review")
    assert response.status_code == 202, response.text
    run_id = response.json()["run_id"]
    assert client.post("/api/portfolio/review").json()["run_id"] == run_id

    async def finish():
        task = state.runs[run_id]
        release.set()
        await task

    client.portal.call(finish)
    events = state.events.history(run_id)
    assert events[0].type == "run.started" and events[0].trigger_kind == "review"
    assert any(event.type == "run.completed" for event in events)
