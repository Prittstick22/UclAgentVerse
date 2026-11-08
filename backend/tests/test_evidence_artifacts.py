"""Evidence returned by tools must remain inspectable, versioned and clock-limited."""
import asyncio

import pytest
from fastapi.testclient import TestClient

from app.agents.schemas import InvestmentCase
from app.agents.supervisor import RunState
from app.main import app
from app.schemas import DecisionCard, Proposal


@pytest.fixture
def client(state, monkeypatch):
    monkeypatch.setattr(app.state, "app", state, raising=False)
    with TestClient(app) as client:
        yield client


def retrieved(state, evidence_id, tool="save_investment_case", **fields):
    return state.events.emit("tool.result", title="Retrieved evidence", evidence_ids=[evidence_id],
                             payload={"tool": tool, "ok": True}, **fields)


def test_catalogue_is_inspectable_gateway_reference(client, state):
    body = client.get("/api/evidence/catalogue").json()
    assert body["kind"] == "catalogue" and body["source"] == "project_catalogue"
    assert body["data"]["items"] == [item.model_dump() for item in state.gw.catalogue()]
    assert state.gw.catalogue()[0].name in body["excerpt"]


def test_legacy_recording_case_resolves_only_exact_visible_version(client, state):
    case = InvestmentCase(case_id="case_IGLS.LSE", ticker="IGLS.LSE", purpose="Short gilts for stability",
                          assumptions=["A bond allocation is required"], reconsider_if=["Mandate changes"])
    state.db.put("cases", case.ticker, case.model_dump_json())
    ref = "case:IGLS.LSE:v1"
    assert client.get(f"/api/evidence/{ref}").status_code == 404  # no retrieval proof
    retrieved(state, ref)
    response = client.get(f"/api/evidence/{ref}")
    assert response.status_code == 200
    assert response.json()["kind"] == "case" and response.json()["data"] == case.model_dump()
    assert "Mandate changes" in response.json()["excerpt"]
    # A citation cannot silently show a different current case in an old recording.
    state.db.put("cases", case.ticker, case.model_copy(update={"version": 2}).model_dump_json())
    assert client.get(f"/api/evidence/{ref}").status_code == 404
    assert client.get("/api/evidence/case:IGLS.LSE:v99").status_code == 404


def test_case_versions_survive_reviews_and_hide_future_and_other_modes(client, state):
    run = RunState(run_id="case_versions", kind="review", trigger_text="Review")
    agent = {"run_id": run.run_id, "agent_id": "lead", "role": "lead"}

    def save(purpose):
        return asyncio.run(state.supervisor.tools.call(
            "save_investment_case", {"case": {"ticker": "IGLS.LSE", "purpose": purpose}},
            role="lead", run=run, agent=agent))

    first_day = state.clock.as_of_str()
    a = save("Original role")
    state.clock.set("2026-07-21")
    b = save("Revised role")
    for result, purpose in ((a, "Original role"), (b, "Revised role")):
        item = client.get("/api/evidence/" + result["evidence_ids"][0])
        assert item.status_code == 200 and item.json()["data"]["purpose"] == purpose
    state.clock.set(first_day)
    assert client.get("/api/evidence/" + a["evidence_ids"][0]).status_code == 200
    assert client.get("/api/evidence/" + b["evidence_ids"][0]).status_code == 404
    state.db.execute("UPDATE events SET mode = 'live' WHERE type = 'tool.result'")
    assert client.get("/api/evidence/" + a["evidence_ids"][0]).status_code == 404


def test_proposal_evidence_has_original_content_without_later_approval_state(client, state):
    proposal = Proposal(id="prop_saved", run_id="run_saved", kind="construction", as_of="2026-07-21",
                        created_at="2026-07-21T12:00:00+00:00", options=[], status="executed",
                        decision_card=DecisionCard(headline="A balanced paper portfolio", body="Spread the investment."))
    state.db.put("proposals", proposal.id, proposal.model_dump_json())
    ref = "proposal:" + proposal.id
    state.clock.set("2026-07-21")
    retrieved(state, ref, "propose_adjustment")
    response = client.get("/api/evidence/" + ref)
    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "proposal" and body["title"] == proposal.decision_card.headline
    assert "Spread the investment." in body["excerpt"]
    assert not {"status", "selected", "gates"}.intersection(body["data"])
    state.clock.set("2026-07-07")
    assert client.get("/api/evidence/" + ref).status_code == 404
    state.clock.set("2026-07-21")
    state.db.execute("UPDATE events SET mode='live'")
    assert client.get("/api/evidence/" + ref).status_code == 404


def test_past_earnings_and_web_links_resolve_without_external_requests(client, state):
    day = state.clock.as_of_str()
    state.gw.snapshot.earnings = [{"ticker": "AAPL.US", "date": "2026-05-01"},
                                 {"ticker": "AAPL.US", "date": "2026-10-01"}]
    retrieved(state, "earnings:AAPL.US", "earnings_calendar")
    body = client.get("/api/evidence/earnings:AAPL.US").json()
    assert body["kind"] == "earnings" and body["data"]["past_dates"] == ["2026-05-01"]
    state.clock.set("2026-10-02")
    assert client.get("/api/evidence/earnings:AAPL.US").json()["data"]["past_dates"] == ["2026-05-01"]
    state.events.emit("source.inspect", title="Saved web search", evidence_ids=["web:saved"],
                               payload={"evidence_id": "web:saved", "title": "Market sources", "source": "google_search",
                                        "sources": [{"title": "Source article", "url": "https://example.org/article"}]})
    body = client.get("/api/evidence/web:saved").json()
    assert body["kind"] == "web" and body["url"] == "https://example.org/article"
    assert body["available_at"] == state.clock.now().isoformat()
    state.clock.set(day)
    assert client.get("/api/evidence/web:saved").status_code == 404


@pytest.mark.parametrize("ref", ["case:IGLS.LSE:v1", "proposal:missing", "web:missing", "earnings:unknown", "unknown"])
def test_unknown_or_failed_retrieval_does_not_invent_evidence(client, state, ref):
    state.events.emit("tool.result", title="Failed", status="failed", evidence_ids=[ref], payload={"ok": False})
    assert client.get("/api/evidence/" + ref).status_code == 404
