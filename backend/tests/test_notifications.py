import asyncio
import json

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.core.clock import SimClock
from app.engine.ledger import Position


@pytest.fixture
def client(state, monkeypatch):
    from app.main import app

    monkeypatch.setattr(app.state, "app", state, raising=False)
    return TestClient(app)


def test_fake_adjustment_notifies_once_when_ready_for_approval(state, client, monkeypatch):
    state.ledger.deposit(10_000)
    state.ledger.mark_to_market(state.gw.latest_prices().to_dict())
    state.ledger.rebalance_to({"VWRP.LSE": 0.40, "VAGS.LSE": 0.30}, state.clock.as_of_str())
    fake = state.llm.fake
    original_lead = fake._lead

    def adjusting_lead(kind, step):
        if kind == "drift" and step in (1, 2):
            return original_lead("construction", step)
        return original_lead(kind, step)

    monkeypatch.setattr(fake, "_lead", adjusting_lead)
    run = asyncio.run(state.supervisor.start("drift", "A holding drifted past its target"))
    assert run.proposal_id is not None
    proposal = state.proposals[run.proposal_id]
    assert proposal.kind == "adjustment"
    assert client.get("/api/notifications").json() == {"items": []}

    approval = {"proposal_id": proposal.id, "by": "user"}
    for _ in range(2):
        state.events.emit(
            "approval.requested", title="Approval requested", run_id=run.run_id, payload=approval
        )
    items = client.get("/api/notifications").json()["items"]
    assert len(items) == 1
    assert items[0]["kind"] == "decision"
    assert items[0]["title"] == proposal.decision_card.headline
    assert items[0]["body"] == proposal.decision_card.body
    assert items[0]["run_id"] == run.run_id
    assert items[0]["proposal_id"] == proposal.id
    assert sum(e.type == "notification.created" for e in state.events.history(run.run_id)) == 1

    portfolio = client.get("/api/portfolio").json()
    assert portfolio["status"] == "awaiting_approval"
    assert portfolio["counters"] == {"reviews": 0, "checks": 1, "decisions_asked": 1, "adjustments": 0}

    notification_url = f"/api/notifications/{items[0]['id']}/read"
    for _ in range(2):
        assert client.post(notification_url).json() == {"ok": True}
    assert client.get("/api/notifications", params={"unread": "true"}).json() == {"items": []}
    assert client.get("/api/notifications").json()["items"][0]["read"] is True
    assert client.get("/api/portfolio").json()["status"] == "awaiting_approval"
    assert client.post("/api/notifications/missing/read").status_code == 404

    state.events.emit("approval.decided", title="Approved", payload={**approval, "decision": "approved"})
    for ticker in ("VWRP.LSE", "VAGS.LSE"):
        state.events.emit(
            "order.filled",
            title="Filled",
            run_id=run.run_id,
            payload={"proposal_id": proposal.id, "ticker": ticker},
        )
    portfolio = client.get("/api/portfolio").json()
    assert portfolio["status"] == "monitoring_normally"
    assert portfolio["counters"]["adjustments"] == 1


def test_awaiting_proposal_event_survives_clock_advance(state, client):
    state.events.emit(
        "proposal.created",
        title="A change needs approval",
        run_id="adjustment",
        payload={"proposal_id": "proposal", "kind": "adjustment", "status": "awaiting_approval"},
    )
    state.clock.set("2026-07-08")
    assert client.get("/api/notifications").json()["items"][0]["id"] == "decision:proposal"
    assert client.get("/api/portfolio").json()["status"] == "awaiting_approval"


def test_maintain_run_creates_digest_and_respects_as_of(state, client):
    state.events.emit("run.started", title="Check started", run_id="pending", trigger_kind="manual")
    assert client.get("/api/portfolio").json()["status"] == "investigating"
    state.events.emit("run.completed", title="Check failed", run_id="pending", status="failed")

    state.clock.set("2026-07-08")
    run = asyncio.run(state.supervisor.start("review", "Scheduled review"))
    items = client.get("/api/notifications").json()["items"]
    assert [(item["kind"], item["body"], item["run_id"]) for item in items] == [
        ("digest", run.decision.reason, run.run_id),
    ]
    assert all(e.type != "notification.created" for e in state.events.history(run.run_id))
    portfolio = client.get("/api/portfolio").json()
    assert portfolio["status"] == "monitoring_normally"
    assert portfolio["last_review_date"] == "2026-07-08"
    assert portfolio["counters"] == {"reviews": 1, "checks": 0, "decisions_asked": 0, "adjustments": 0}

    state.clock.set("2026-07-07")
    assert client.get("/api/notifications").json() == {"items": []}
    assert client.get("/api/portfolio").json()["counters"]["reviews"] == 0


def test_notifications_respect_mode_and_persist_read_state(state, client):
    class LiveTestClock(SimClock):
        mode = "live"

    state.events.clock = LiveTestClock(state.clock.today())
    state.events.emit(
        "approval.requested",
        title="Live proposal",
        run_id="live-run",
        payload={"proposal_id": "live-proposal", "by": "user"},
    )
    state.events.clock = state.clock
    assert client.get("/api/notifications").json() == {"items": []}
    live_items = client.get("/api/notifications", params={"mode": "live"}).json()["items"]
    assert [item["id"] for item in live_items] == ["decision:live-proposal"]
    assert client.post("/api/notifications/decision:live-proposal/read").status_code == 404

    state.events.emit(
        "approval.requested",
        title="Historical proposal",
        run_id="historical-run",
        payload={"proposal_id": "historical-proposal", "by": "user"},
    )
    assert client.post("/api/notifications/decision:historical-proposal/read").status_code == 200
    assert json.loads(state.db.get("notification_reads:historical", "decision:historical-proposal")) is True


def test_stale_observed_holding_price_creates_one_coverage_notice(state, client):
    ticker = "VWRP.LSE"
    state.ledger.positions[ticker] = Position(units=1)
    assert client.get("/api/portfolio").json()["status"] == "monitoring_normally"

    quotes = state.gw.snapshot.prices
    dates = pd.to_datetime(quotes["date"])
    missing = quotes["ticker"].eq(ticker) & dates.gt("2026-06-30") & dates.le("2026-07-07")
    state.gw.snapshot.prices = quotes.loc[~missing]

    state.events.emit("clock.tick", title="Portfolio checked")
    assert sum(e.type == "notification.created" for e in state.events.history()) == 1
    assert client.get("/api/portfolio").json()["status"] == "monitoring_degraded"
    for _ in range(2):
        items = client.get("/api/notifications").json()["items"]
        assert [(item["kind"], item["body"]) for item in items] == [
            ("coverage", "The last available price for VWRP.LSE is from 2026-06-30."),
        ]
    assert sum(e.type == "notification.created" for e in state.events.history()) == 1

    state.clock.set("2026-07-08")
    assert client.get("/api/portfolio").json()["status"] == "monitoring_normally"
    assert len(client.get("/api/notifications").json()["items"]) == 1


def test_entire_cached_feed_can_be_stale(state, client):
    ticker = "VWRP.LSE"
    state.ledger.positions[ticker] = Position(units=1)
    last_date = state.gw.trading_days("2026-07-07")[-1]
    state.clock.set((last_date + pd.offsets.BDay(3)).date())
    assert client.get("/api/portfolio").json()["status"] == "monitoring_normally"
    state.clock.set((last_date + pd.offsets.BDay(4)).date())
    assert client.get("/api/portfolio").json()["status"] == "monitoring_degraded"
