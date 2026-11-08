"""Offline integration coverage for immutable playback of a real simulator recording."""
from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
from unittest.mock import Mock

import httpx
import pytest
from fastapi.testclient import TestClient

from app.agents.llm import LLM
from app.agents.supervisor import Supervisor
from app.api.recorded_replay import RecordedEvents, RecordedReplay
from app.container import build_state, state_for_mode
from app.core.events import Event
from app.data.adapters.alpaca import Alpaca
from app.data.adapters.edgar import Edgar
from app.data.adapters.eodhd import EODHD
from app.data.adapters.finnhub import Finnhub
from app.engine import optimiser
from app.engine.portfolio import checkpoints
from app.main import app
from app.profile.demo import demo_mandate
from app.settings import Settings
from app.sim.runner import Simulation, run


@pytest.fixture(scope="module")
def recording(snapshot_dir, tmp_path_factory):
    """Pay for fake-agent construction/review once; each test gets a fresh memory clone."""
    folder = tmp_path_factory.mktemp("recorded-replay")
    path = folder / "short.sqlite"
    settings = Settings(
        _env_file=None, snapshot_dir=snapshot_dir, llm_mode="fake", app_mode="historical",
        public_demo=False, recorded_run=None, runs_dir=folder / "unused",
    )
    state = build_state(settings, db_path=str(path))
    try:
        state.db.put("sim_mandate", "initial", state.mandate.model_dump_json())
        days = state.gw.trading_days("2026-07-07")[:state.mandate.review_every_n_days + 1]
        result = asyncio.run(run(state, str(days[0].date()), str(days[-1].date()),
                                 agents=True, approvals="batch_policy"))
        assert result.days == len(days)
        assert result.fills > 0
        assert state.proposals
        assert len(checkpoints(state.db, "historical")) == len(days)
        # Fake reviews maintain. A second real construction supplies a later dated proposal
        # so the firewall test exercises persisted proposal visibility as well as run visibility.
        later = asyncio.run(state.supervisor.start("construction", "Offline later proposal"))
        assert later.proposal_id in state.proposals
    finally:
        state.db.conn.close()
    return path


@pytest.fixture
def replay_settings(snapshot_dir, recording, tmp_path):
    return Settings(
        _env_file=None, snapshot_dir=snapshot_dir, recorded_run=recording,
        llm_mode="live", app_mode="historical", public_demo=True,
        demo_passcode="test-only-passcode", daily_llm_budget_usd=0,
        state_db=tmp_path / "state.sqlite", runs_dir=tmp_path / "runs",
        rate_limit_per_minute=1000,
    )


@pytest.fixture
def replay_state(replay_settings, tmp_path):
    state = build_state(replay_settings, db_path=str(tmp_path / "ignored.sqlite"))
    yield state
    for mode in state.modes.values():
        mode.db.conn.close()


@pytest.fixture
def client(replay_state, monkeypatch):
    monkeypatch.setattr(app.state, "app", replay_state, raising=False)
    monkeypatch.delattr(app.state, "rate_limiter", raising=False)
    with TestClient(app) as client:
        yield client
        client.portal.call(replay_state.recording.pause)


def source_events(path: Path) -> list[Event]:
    with sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True) as db:
        return [Event.model_validate_json(row[0]) for row in db.execute(
            "SELECT json FROM events WHERE mode='historical' ORDER BY as_of, rowid"
        )]


def test_build_state_clones_source_and_only_historical_llm_is_replay(replay_state, replay_settings,
                                                                  recording, tmp_path):
    original = recording.read_bytes()
    assert isinstance(replay_state.recording, RecordedReplay)
    assert isinstance(replay_state.events, RecordedEvents)
    assert replay_state.db.path == ":memory:"
    assert not (tmp_path / "ignored.sqlite").exists()
    assert replay_state.settings is replay_settings
    assert replay_settings.llm_mode == "live"
    assert replay_state.llm.mode == "replay"
    assert replay_state.mandate == demo_mandate()
    assert replay_state.db.get("sim_mandate", "initial") == demo_mandate().model_dump_json()
    assert replay_state.events.history() == source_events(recording)
    replay_state.db.put("test_isolation", "only-in-clone", "true")
    with sqlite3.connect(f"{recording.as_uri()}?mode=ro", uri=True) as db:
        assert not db.execute("SELECT 1 FROM kv WHERE ns='test_isolation'").fetchall()
    live = state_for_mode(replay_state, "live")
    assert live is state_for_mode(replay_state, "live")
    assert live.recording is None
    assert live.llm.mode == "live"
    assert live.settings.llm_mode == "live"
    assert live.db is not replay_state.db
    assert live.events.history() == []
    assert live.proposals == {}
    assert recording.read_bytes() == original


def test_mode_query_reads_isolated_live_state_without_switching_active_replay(client, replay_state):
    historical = client.get("/api/portfolio?mode=historical")
    assert historical.status_code == 200
    assert historical.json()["holdings"]
    live = client.get("/api/portfolio?mode=live")
    assert live.status_code == 200
    assert live.json()["mode"] == "live"
    assert live.json()["holdings"] == []
    assert client.get("/api/portfolio/history?mode=live").json() == {"points": []}
    assert client.get("/api/runs?mode=live").json() == {"items": []}
    assert app.state.app is replay_state
    assert client.get("/api/health").json()["mode"] == "historical"


def test_initial_views_use_persisted_portfolio_checkpoints_and_proposals(client, replay_state):
    marks = checkpoints(replay_state.db, "historical")
    health = client.get("/api/health").json()
    assert health["llm_mode"] == "replay"
    assert health["as_of"] == marks[-1].date
    assert health["data_source"] == "synthetic"
    response = client.get("/api/portfolio")
    assert response.status_code == 200, response.text
    portfolio = response.json()
    assert portfolio["nav_gbp"] == round(marks[-1].nav_gbp, 2)
    assert portfolio["contributions_gbp"] == marks[-1].contributions_gbp
    assert {row["ticker"] for row in portfolio["holdings"]} == set(marks[-1].positions)
    assert portfolio["holdings"]
    points = client.get("/api/portfolio/history").json()["points"]
    assert [point["date"] for point in points] == [mark.date for mark in marks]
    assert [point["nav_gbp"] for point in points] == pytest.approx([mark.nav_gbp for mark in marks])
    for proposal in replay_state.proposals.values():
        response = client.get(f"/api/proposals/{proposal.id}")
        assert response.status_code == 200
        assert response.json() == proposal.model_dump(mode="json")
    assert client.get("/api/benchmarks").json()["series"]


@pytest.fixture
def forbidden_playback_calls(monkeypatch):
    """Fail at public execution boundaries, without replacing replay or its read models."""
    calls = []
    boundaries = [(Supervisor, "start"), (LLM, "generate"), (LLM, "search"),
                  (Simulation, "step"), (optimiser, "optimise")]
    for provider in (Alpaca, Edgar, EODHD, Finnhub):
        boundaries.extend((provider, name) for name in vars(provider)
                          if not name.startswith("_") and callable(getattr(provider, name)))
    for owner, name in boundaries:
        sentinel = Mock(side_effect=AssertionError(f"Playback called {owner.__name__}.{name}"))
        monkeypatch.setattr(owner, name, sentinel)
        calls.append(sentinel)
    yield calls
    for sentinel in calls:
        sentinel.assert_not_called()


def test_start_pause_step_publish_original_events_without_execution_or_source_writes(
    client, replay_state, recording, forbidden_playback_calls,
):
    original = recording.read_bytes()
    events = source_events(recording)
    observed = []
    replay_state.events.listen(observed.append)
    queue = client.portal.call(replay_state.events.subscribe)
    try:
        response = client.post("/api/sim/start", json={"speed": 0.001, "run_agents": True})
        assert response.status_code == 200, response.text
        assert recording.read_bytes() == original
        response = client.post("/api/sim/pause")
        assert response.status_code == 200
        assert response.json()["sim"]["running"] is False
        assert response.json()["as_of"] == replay_state.recording.start_day
        assert recording.read_bytes() == original
        response = client.post("/api/sim/step", json={"days": 1})
        assert response.status_code == 200
        assert response.json()["as_of"] == replay_state.recording.days[1]
        assert recording.read_bytes() == original
        response = client.post("/api/sim/step", json={"days": 100})
        assert response.status_code == 200
        assert client.get("/api/sim/status").json()["progress"] == 1.0

        async def drain():
            return [queue.get_nowait() for _ in range(queue.qsize())]

        published = client.portal.call(drain)
        assert published == events
        assert observed == []  # playback must not rerun tool/approval listeners
        assert replay_state.events.history() == events
        assert replay_state.llm.live_calls == 0
        assert recording.read_bytes() == original
    finally:
        client.portal.call(replay_state.events.unsubscribe, queue)


def test_date_firewall_hides_future_runs_events_proposals_evidence_and_benchmarks(client, replay_state,
                                                                               recording):
    events = source_events(recording)
    future_run = next(event for event in events if event.type == "run.started"
                      and event.as_of > replay_state.recording.start_day)
    future_calc = next(event for event in events if event.type == "calc.result"
                       and event.as_of == future_run.as_of)
    future_proposal = next(proposal for proposal in replay_state.proposals.values()
                           if proposal.as_of == future_run.as_of)
    response = client.post("/api/sim/step", json={"days": 1})
    assert response.status_code == 200
    day = response.json()["as_of"]
    assert day == replay_state.recording.start_day
    assert replay_state.events.history() == [event for event in events if event.as_of <= day]
    runs = client.get("/api/runs").json()["items"]
    assert runs and all(item["as_of"] <= day for item in runs)
    assert future_run.run_id not in {item["run_id"] for item in runs}
    assert client.get(f"/api/runs/{future_run.run_id}").status_code == 404
    assert client.get(f"/api/runs/{future_run.run_id}/events?format=json").json() == {"items": []}
    assert client.get(f"/api/proposals/{future_proposal.id}").status_code == 404
    assert client.get(f"/api/evidence/calc:{future_calc.id}").status_code == 404
    benchmarks = client.get("/api/benchmarks").json()
    assert benchmarks["series"] == benchmarks["metrics"] == {}
    points = client.get(f"/api/portfolio/history?end={replay_state.recording.end_day}").json()["points"]
    assert [point["date"] for point in points] == [day]
    assert client.get("/api/portfolio").json()["holdings"] == []
    assert client.post("/api/sim/step", json={"days": 100}).status_code == 200
    assert client.get(f"/api/runs/{future_run.run_id}").status_code == 200
    visible_events = client.get(f"/api/runs/{future_run.run_id}/events?format=json").json()["items"]
    assert visible_events == [event.model_dump(mode="json") for event in events
                              if event.run_id == future_run.run_id]
    assert client.get(f"/api/proposals/{future_proposal.id}").status_code == 200
    assert client.get(f"/api/evidence/calc:{future_calc.id}").json()["data"] == future_calc.payload
    assert client.get("/api/benchmarks").json()["series"]
    assert client.get("/api/benchmarks").json()["metrics"]


def test_completed_recorded_run_sse_terminates_and_preserves_ids_and_cursor(client, recording):
    events = source_events(recording)
    run_id = next(event.run_id for event in events if event.type == "run.started")
    expected = [event.model_dump(mode="json") for event in events if event.run_id == run_id]
    assert any(event["type"] == "run.completed" for event in expected)

    async def read_sse(after):
        # TestClient's HTTP timeout does not bound an ASGI stream: bound the actual coroutine.
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
            return await asyncio.wait_for(http.get(f"/api/runs/{run_id}/events?after={after}"), timeout=3)

    for after in (0, expected[len(expected) // 2]["seq"], expected[-1]["seq"]):
        response = client.portal.call(read_sse, after)
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        frames = [frame.splitlines() for frame in response.text.strip().split("\n\n") if frame]
        streamed = [json.loads(next(line[6:] for line in frame if line.startswith("data: ")))
                    for frame in frames]
        assert streamed == [event for event in expected if event["seq"] > after]
        assert [next(line for line in frame if line.startswith("event: ")) for frame in frames] == [
            f"event: {event['type']}" for event in streamed
        ]
        assert [next(line for line in frame if line.startswith("id: ")) for frame in frames] == [
            f"id: {event['seq']}" for event in streamed
        ]
    # Native EventSource retries carry the last dispatched sequence, including after completion.
    completed_seq = next(event["seq"] for event in expected if event["type"] == "run.completed")
    response = client.get(f"/api/runs/{run_id}/events", headers={"Last-Event-ID": str(completed_seq)})
    if completed_seq < expected[-1]["seq"]:
        assert response.status_code == 200
        assert f"id: {expected[-1]['seq']}" in response.text
    else:
        assert response.status_code == 204
    response = client.get(f"/api/runs/{run_id}/events", headers={"Last-Event-ID": str(expected[-1]["seq"])})
    assert response.status_code == 204 and not response.content


def test_recorded_build_selects_existing_run_without_passcode_and_decisions_reject(
    client, replay_state, recording, forbidden_playback_calls,
):
    original = recording.read_bytes()
    construction = next(event for event in source_events(recording)
                        if event.type == "run.started" and event.trigger_kind == "construction")
    before = replay_state.db.execute("SELECT COUNT(*) FROM events")
    for _ in range(2):
        response = client.post("/api/portfolio/build")
        assert response.status_code == 202, response.text
        assert response.json() == {"run_id": construction.run_id}
    assert replay_state.runs == {}
    for proposal in replay_state.proposals.values():
        previous = proposal.model_dump(mode="json")
        for action in ("approve", "decline"):
            response = client.post(f"/api/proposals/{proposal.id}/{action}", json={})
            assert response.status_code == 409, response.text
            assert "recorded demo" in response.json()["error"]["message"]
        assert client.get(f"/api/proposals/{proposal.id}").json() == previous
    assert replay_state.db.execute("SELECT COUNT(*) FROM events") == before
    assert recording.read_bytes() == original


@pytest.mark.parametrize("damage", [
    "missing-file", "malformed-sqlite", "missing-results", "malformed-results",
    "missing-checkpoint", "missing-tick", "missing-middle-tick", "malformed-event",
    "wrong-mandate", "missing-mandate",
])
def test_invalid_recording_fails_at_startup(replay_settings, recording, tmp_path, damage):
    path = tmp_path / "invalid.sqlite"
    if damage == "malformed-sqlite":
        path.write_bytes(b"This is not SQLite")
    elif damage != "missing-file":
        path.write_bytes(recording.read_bytes())
        with sqlite3.connect(path) as db:
            if damage == "missing-results":
                db.execute("DELETE FROM kv WHERE ns='sim_results'")
            elif damage == "malformed-results":
                db.execute("UPDATE kv SET json='{}' WHERE ns='sim_results'")
            elif damage == "missing-checkpoint":
                db.execute("DELETE FROM kv WHERE ns='ledger_checkpoints:historical' AND key="
                           "(SELECT MAX(key) FROM kv WHERE ns='ledger_checkpoints:historical')")
            elif damage == "missing-tick":
                db.execute("DELETE FROM events WHERE type='clock.tick' AND as_of="
                           "(SELECT MAX(as_of) FROM events WHERE type='clock.tick')")
            elif damage == "missing-middle-tick":
                db.execute("DELETE FROM events WHERE type='clock.tick' AND as_of="
                           "(SELECT as_of FROM events WHERE type='clock.tick' ORDER BY as_of LIMIT 1 OFFSET 1)")
            elif damage == "malformed-event":
                db.execute("UPDATE events SET json='{}' WHERE type='run.started'")
            elif damage == "wrong-mandate":
                mandate = demo_mandate().model_copy(update={"version": 999})
                db.execute("UPDATE kv SET json=? WHERE ns='sim_mandate' AND key='initial'",
                           (mandate.model_dump_json(),))
            elif damage == "missing-mandate":
                db.execute("DELETE FROM kv WHERE ns='sim_mandate'")
    original = path.read_bytes() if path.exists() else None
    settings = replay_settings.model_copy(update={"recorded_run": path})
    with pytest.raises((ValueError, KeyError, sqlite3.Error)):
        state = build_state(settings, db_path=":memory:")
        state.db.conn.close()
    assert (path.read_bytes() if path.exists() else None) == original


def test_single_day_playback_finishes_without_waiting_for_next_interval(client, replay_state):
    day = replay_state.recording.start_day
    response = client.post("/api/sim/start", json={"start": day, "end": day, "speed": 0.001})
    assert response.status_code == 200

    async def finish():
        await asyncio.wait_for(asyncio.shield(replay_state.recording.task), timeout=1)

    client.portal.call(finish)
    result = client.get("/api/sim/status").json()
    assert result["progress"] == 1
    assert not result["sim"]["running"]


def test_rewind_projects_execution_at_fill_day_not_recording_end(client, replay_state):
    proposal = next(prop for prop in replay_state.proposals.values() if prop.status == "executed")
    assert client.post("/api/sim/step", json={"days": 1}).status_code == 200
    assert client.get(f"/api/proposals/{proposal.id}").json()["status"] == "approved"
    assert client.post("/api/sim/step", json={"days": 1}).status_code == 200
    assert replay_state.clock.as_of_str() < replay_state.recording.end_day
    assert client.get(f"/api/proposals/{proposal.id}").json()["status"] == "executed"


def test_rewind_does_not_expose_a_later_decline_reason(snapshot_dir, tmp_path, monkeypatch):
    from app.sim.approvals import decline_by_user

    path = tmp_path / "manual.sqlite"
    settings = Settings(_env_file=None, snapshot_dir=snapshot_dir, llm_mode="fake", app_mode="historical")
    original = build_state(settings, db_path=str(path))
    days = original.gw.trading_days(original.clock.as_of_str())[:2]
    original.db.put("sim_mandate", "initial", original.mandate.model_dump_json())
    asyncio.run(run(original, str(days[0].date()), str(days[-1].date()), agents=True, approvals="manual"))
    proposal_id = next(iter(original.proposals))
    decline_by_user(original, proposal_id, "A decision made on the second day")
    original.db.conn.close()
    replay = build_state(settings.model_copy(update={"recorded_run": path}), db_path=":memory:")
    monkeypatch.setattr(app.state, "app", replay, raising=False)
    try:
        with TestClient(app) as http:
            http.post("/api/sim/step", json={"days": 1}).raise_for_status()
            first = http.get(f"/api/proposals/{proposal_id}").json()
            assert first["status"] == "awaiting_approval"
            assert not any(note.startswith("Declined: ") for note in first["uncertainties"])
            http.post("/api/sim/step", json={"days": 1}).raise_for_status()
            last = http.get(f"/api/proposals/{proposal_id}").json()
            assert last["status"] == "declined"
            assert "Declined: A decision made on the second day" in last["uncertainties"]
    finally:
        for state in replay.modes.values():
            state.db.conn.close()
