import asyncio
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client(state, monkeypatch):
    monkeypatch.setattr(app.state, "app", state, raising=False)
    with TestClient(app) as client:
        yield client


def test_construction_returns_distinct_ids_without_waiting_for_agent(client, state, monkeypatch):
    release = asyncio.Event()
    original_start = state.supervisor.start

    async def delayed_start(*args, **kwargs):
        await asyncio.wait_for(release.wait(), timeout=5)
        return await original_start(*args, **kwargs)

    monkeypatch.setattr(state.supervisor, "start", delayed_start)
    responses = [client.post("/api/portfolio/build") for _ in range(2)]
    assert all(response.status_code == 202 for response in responses)
    ids = [response.json()["run_id"] for response in responses]
    assert len(set(ids)) == 2
    assert set(state.runs) == set(ids)
    assert all(not state.events.history(run_id) for run_id in ids)

    async def finish():
        tasks = [state.runs[run_id] for run_id in ids]
        release.set()
        await asyncio.gather(*tasks)

    client.portal.call(finish)
    for run_id in ids:
        response = client.get(f"/api/runs/{run_id}")
        assert response.status_code == 200
        body = response.json()
        assert body["run_id"] == run_id and body["status"] == "completed"
        nodes = {node["agent_id"]: node for node in body["agents"]}
        denied, = [node for node in nodes.values() if node["status"] == "denied"]
        assert denied["role"] == "news_analyst"
        assert denied["question"] == "Any news on this filing?"
        assert denied["purpose"] == "context"
        assert nodes[denied["parent_agent_id"]]["role"] == "filing_reader"
        assert max(node["depth"] for node in nodes.values()) <= 2
        assert all(node["status"] == "done" and node["model"] for node in nodes.values() if node != denied)

    items = client.get("/api/runs?kind=construction").json()["items"]
    assert {item["run_id"] for item in items} == set(ids)
    assert all("agents" not in item for item in items)
    assert client.get("/api/runs/unknown").status_code == 404


def test_failed_build_reaches_terminal_state(client, state, monkeypatch):
    release = asyncio.Event()

    async def fail(*args):
        await release.wait()
        raise RuntimeError("test agent failure")

    monkeypatch.setattr(state.supervisor, "_run_agent", fail)
    run_id = client.post("/api/portfolio/build").json()["run_id"]

    async def finish():
        task = state.runs[run_id]
        release.set()
        with pytest.raises(RuntimeError, match="test agent failure"):
            await task

    client.portal.call(finish)
    body = client.get(f"/api/runs/{run_id}").json()
    assert body["status"] == "failed"
    assert body["finished_at"]


def test_run_detail_maps_agent_failure_and_badges(client, state):
    def emit(event_type, **fields):
        return state.events.emit(event_type, title=event_type, run_id="run_recorded", **fields)

    emit("run.started", trigger_kind="review", trigger_text="Scheduled review")
    emit("agent.spawned", agent_id="lead", role="lead", depth=0, payload={"model": "fake"})
    emit("agent.spawned", agent_id="reader", parent_agent_id="lead", role="filing_reader", depth=1)
    emit("source.inspect", evidence_ids=["source"])
    emit("tool.result", agent_id="reader", evidence_ids=["source"])
    emit("finding", agent_id="reader", evidence_ids=["source"])
    emit("gate.verdict", evidence_ids=["source"], payload={"gate": "evidence", "status": "pass"})
    emit("gate.verdict", agent_id="lead", payload={"gate": "numbers", "status": "pass"})
    emit("gate.verdict", agent_id="lead", payload={"gate": "numbers", "status": "pass"})
    emit("gate.verdict", payload={"gate": "critic", "status": "pass_with_flags"})
    emit("gate.verdict", agent_id="lead", payload={"gate": "evidence", "status": "fail"})
    emit("agent.status", agent_id="reader", status="failed", payload={"status": "failed"})
    emit("agent.status", agent_id="lead", status="ok", payload={"status": "done"})
    emit("run.completed", status="failed", payload={"outcome": "investigate_further"})

    body = client.get("/api/runs/run_recorded").json()
    assert body["status"] == "failed"
    assert body["outcome"] == "investigate_further"
    assert body["finished_at"]
    lead, reader = body["agents"]
    assert lead["status"] == "done"
    assert lead["badges"] == ["calculation_recomputed", "judgement_uncertain"]
    assert reader["status"] == "failed"
    assert reader["badges"] == ["source_retrieved", "claim_supported"]


def test_evidence_respects_historical_clock_and_resolves_passages_and_calculations(client, state):
    assert client.get("/api/evidence/news_syn_001").status_code == 404
    state.clock.set("2026-10-02")
    news = client.get("/api/evidence/news_syn_001").json()
    assert news["kind"] == "news" and news["source"] == "synthetic"
    assert news["excerpt"]
    injected = client.get("/api/evidence/news_syn_inject").json()
    assert injected["quarantined"] and injected["excerpt"] is None

    filing = state.gw.filings()[0]
    assert client.get(f"/api/evidence/{filing.id}").json()["kind"] == "filing"
    passage = filing.passages[0]
    item = client.get(f"/api/evidence/{quote(passage.id, safe='')}").json()
    assert item["excerpt"] == passage.text
    assert item["published_at"] == filing.accepted_at

    payload = {"name": "risk_stats", "inputs": {"ticker": "VWRP.LSE"}, "outputs": {"vol": 0.2}}
    calc = state.events.emit("calc.result", title="Risk calculated", payload=payload)
    url = f"/api/evidence/calc:{calc.id}"
    item = client.get(url).json()
    assert item["kind"] == "calc" and item["data"] == payload
    assert item["available_at"] == state.clock.now().isoformat()
    state.clock.set("2026-10-01")
    assert client.get(url).status_code == 404
    assert client.get("/api/evidence/calc:unknown").status_code == 404
