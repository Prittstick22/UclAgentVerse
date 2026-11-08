"""Portfolio endpoints backed by the real paper ledger and persisted events."""
import asyncio

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.agents.supervisor import RunState
from app.core.clock import SimClock
from app.engine.portfolio import record_checkpoint
from app.main import app
from app.sim.runner import run

TARGETS = {"VWRP.LSE": 0.50, "VAGS.LSE": 0.45}


@pytest.fixture
def client(state, monkeypatch):
    monkeypatch.setattr(app.state, "app", state, raising=False)
    return TestClient(app)


def test_portfolio_shows_ledger_and_as_of_case(state, client):
    asyncio.run(run(state, "2026-07-07", "2026-07-10", targets=TARGETS))
    run_state = RunState(run_id="run_case", kind="construction", trigger_text="test")
    asyncio.run(state.supervisor.tools.call(
        "save_investment_case", {"ticker": "VWRP.LSE", "purpose": "Global diversification"},
        role="lead", run=run_state, agent={"run_id": run_state.run_id},
    ))
    response = client.get("/api/portfolio")
    assert response.status_code == 200, response.json()
    portfolio = response.json()
    assert portfolio["nav_gbp"] == round(state.ledger.nav(), 2)
    assert portfolio["cash_gbp"] == round(state.ledger.cash_gbp, 2)
    assert portfolio["contributions_gbp"] == 10000.0
    holdings = {row["ticker"]: row for row in portfolio["holdings"]}
    assert holdings["VWRP.LSE"]["target_weight"] == TARGETS["VWRP.LSE"]
    assert holdings["VWRP.LSE"]["purpose"] == "Global diversification"
    assert holdings["VWRP.LSE"]["case_id"] == "case_VWRP.LSE"
    assert holdings["VWRP.LSE"]["price_as_of"] == "2026-07-10"
    assert holdings["VWRP.LSE"]["stale"] is False

    state.clock.set("2026-07-09")
    historical = client.get("/api/portfolio").json()
    assert historical["as_of"] == "2026-07-09"
    assert all(row["case_id"] is None for row in historical["holdings"])
    assert all(row["price_as_of"] <= "2026-07-09" for row in historical["holdings"])


def test_history_reads_checkpoints_after_restart_and_filters(state, client):
    asyncio.run(run(state, "2026-07-07", "2026-07-10", targets=TARGETS))
    state.ledger = type(state.ledger)(catalogue=state.ledger.catalogue)
    state.clock.set("2026-07-09")
    response = client.get("/api/portfolio/history?mode=historical&start=2026-07-08&end=2026-07-10")
    assert response.status_code == 200, response.json()
    points = response.json()["points"]
    assert [row["date"] for row in points] == ["2026-07-08", "2026-07-09"]
    assert all(row["contributions_gbp"] == 10000.0 and row["weights"] for row in points)
    assert client.get("/api/portfolio").json()["holdings"]
    assert client.get("/api/portfolio/history?mode=live").json() == {"points": []}
    assert client.get("/api/portfolio/history?start=2026-07-10&end=2026-07-09").status_code == 422


def test_legacy_tick_history_preserves_unknown_contributions(state, client):
    state.events.emit("clock.tick", title="Recorded close", payload={"nav_gbp": 12000.0, "weights": TARGETS})
    assert client.get("/api/portfolio/history").json()["points"] == [
        {"date": "2026-07-07", "nav_gbp": 12000.0, "weights": TARGETS, "contributions_gbp": None}
    ]
    assert client.get("/api/portfolio").status_code == 409
    assert client.get("/api/portfolio/pnl").status_code == 409


def test_cash_contributions_are_not_returns(state, client):
    state.ledger.deposit(10000)
    record_checkpoint(state.db, "historical", state.ledger, "2026-07-07", {})
    state.clock.set("2026-07-08")
    state.ledger.deposit(200)
    record_checkpoint(state.db, "historical", state.ledger, "2026-07-08", {})

    portfolio = client.get("/api/portfolio").json()
    assert portfolio["contributions_gbp"] == portfolio["nav_gbp"] == 10200
    assert portfolio["total_return"] == 0.0


def test_holding_staleness_uses_observations_before_forward_fill(state, client):
    asyncio.run(run(state, "2026-07-07", "2026-07-08", targets=TARGETS))
    prices = state.gw.snapshot.prices
    dates = pd.to_datetime(prices["date"])
    state.gw.snapshot.prices = prices[~(prices["ticker"].eq("VWRP.LSE") & dates.gt("2026-07-08"))]
    state.gw._prices_gbp = state.gw.snapshot.adj_close_gbp()
    state.clock.set("2026-07-15")
    body = client.get("/api/portfolio").json()
    holdings = {row["ticker"]: row for row in body["holdings"]}
    assert holdings["VWRP.LSE"]["price_as_of"] == "2026-07-08"
    assert holdings["VWRP.LSE"]["stale"] is True
    assert holdings["VAGS.LSE"]["stale"] is False
    assert body["status"] == "monitoring_degraded"


def test_pnl_period_uses_opening_ledger_mark_and_rejects_missing_baseline(state, client):
    ledger = state.ledger
    ledger.deposit(10000)
    for day in ("2026-07-07", "2026-08-06", "2026-09-07"):
        state.clock.set(day)
        ledger.mark_to_market(state.gw.latest_prices().to_dict())
        if day == "2026-07-07":
            ledger.rebalance_to(TARGETS, day)
        if day != "2026-09-07":
            record_checkpoint(state.db, "historical", ledger, day, TARGETS)

    def get_pnl(period):
        response = client.get(f"/api/portfolio/pnl?period={period}")
        assert response.status_code == 200, response.json()
        return response.json()

    lifetime = get_pnl("since_purchase")
    trailing = get_pnl("1m")
    assert len(lifetime["rows"]) == len(TARGETS)
    assert trailing["total_pnl_gbp"] != lifetime["total_pnl_gbp"]
    assert get_pnl("3m")["total_pnl_gbp"] == lifetime["total_pnl_gbp"]
    assert get_pnl("ytd")["rows"] == lifetime["rows"]
    assert get_pnl("sim_year")["rows"] == lifetime["rows"]
    assert client.get("/api/portfolio/pnl?period=invalid").status_code == 422

    state.db.execute("DELETE FROM kv WHERE ns=?", ("ledger_checkpoints:historical",))
    unavailable = client.get("/api/portfolio/pnl?period=1m")
    assert unavailable.status_code == 409
    assert "does not cover" in unavailable.json()["error"]["message"]


def test_rebalances_join_approvals_and_fills_at_the_close(state, client):
    state.ledger.deposit(10000)
    record_checkpoint(state.db, "historical", state.ledger, "2026-07-07", TARGETS)
    state.events.emit("run.started", run_id="review-1", title="Review", trigger_kind="review",
                      trigger_text="Fortnightly review")
    state.events.emit("approval.decided", run_id="review-1", title="Approved",
                      payload={"decision": "approved", "proposal_id": "p1", "by": "user"})
    state.clock.set("2026-07-08")
    state.ledger.mark_to_market(state.gw.latest_prices().to_dict())
    fills = state.ledger.rebalance_to(TARGETS, "2026-07-08")
    for fill in fills:
        state.events.emit("order.filled", title="Paper fill", payload={**vars(fill), "proposal_id": "p1"})
    state.events.emit("order.filled", run_id="unapproved", title="Unrelated fill", payload=vars(fills[0]))
    record_checkpoint(state.db, "historical", state.ledger, "2026-07-08", TARGETS)

    items = client.get("/api/portfolio/rebalances?limit=1").json()["items"]
    assert len(items) == 1
    item = items[0]
    assert (item["date"], item["run_id"], item["trigger_kind"], item["trigger_text"]) == (
        "2026-07-08", "review-1", "review", "Fortnightly review",
    )
    assert item["cost_gbp"] == pytest.approx(sum(fill.cost_gbp for fill in fills))
    assert {change["ticker"] for change in item["changes"]} == set(TARGETS)
    assert all(change["from_weight"] == 0 and change["to_weight"] > 0 for change in item["changes"])
    assert client.get("/api/portfolio/rebalances?mode=live").json() == {"items": []}
    assert client.get("/api/portfolio/rebalances?limit=0").status_code == 422
    state.clock.set("2026-07-07")
    assert client.get("/api/portfolio/rebalances").json() == {"items": []}


def test_history_does_not_include_future_or_other_mode_ticks(state, client):
    state.events.clock = SimClock("2026-07-08")
    state.events.emit("clock.tick", title="Future", payload={"nav_gbp": 999})
    other_mode = SimClock("2026-07-07")
    other_mode.mode = "live"
    state.events.clock = other_mode
    state.events.emit("clock.tick", title="Live", payload={"nav_gbp": 500})

    assert client.get("/api/portfolio/history").json() == {"points": []}
    assert client.get("/api/portfolio/history?mode=live").json()["points"][0]["nav_gbp"] == 500
