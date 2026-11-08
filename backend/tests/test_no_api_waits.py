"""Request paths use local cache and live construction returns before the worker finishes."""

import asyncio
import json
from unittest.mock import Mock

from fastapi import Request
from fastapi.testclient import TestClient

from app.api.routes import run_events
from app.container import state_for_mode
from app.data.live import LiveUpdates
from app.main import app


def test_live_build_is_passcode_guarded_nonblocking_and_streams(state, monkeypatch):
    live = state_for_mode(state, "live")
    live.settings.public_demo = True
    live.settings.llm_mode = "live"
    live.settings.demo_passcode = "offline-passcode"
    monkeypatch.setattr(app.state, "app", live, raising=False)
    monkeypatch.delattr(app.state, "rate_limiter", raising=False)
    release = asyncio.Event()

    async def delayed_start(kind, text, *, run_id):
        live.events.emit("run.started", title="Delayed live construction", run_id=run_id,
                         trigger_kind="construction", payload={"kind": kind})
        await release.wait()
        live.events.emit("run.completed", title="Offline construction complete", run_id=run_id,
                         status="ok", payload={"outcome": "built"})

    monkeypatch.setattr(live.supervisor, "start", delayed_start)
    with TestClient(app) as client:
        assert client.post("/api/portfolio/build").status_code == 401
        response = client.post("/api/portfolio/build", headers={"X-Demo-Passcode": "offline-passcode"})
        assert response.status_code == 202
        run_id = response.json()["run_id"]
        assert run_id in live.runs
        assert not live.runs[run_id].done()
        assert client.get("/api/health").status_code == 200

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def finish_and_read_stream():
            request = Request({"type": "http", "method": "GET", "path": "/", "headers": [], "app": app}, receive)
            stream = await run_events(run_id, request)
            frames = []
            try:
                frames.append(await asyncio.wait_for(anext(stream.body_iterator), timeout=2))
                release.set()
                while "event: run.completed" not in frames[-1]:
                    frames.append(await asyncio.wait_for(anext(stream.body_iterator), timeout=2))
            finally:
                await stream.body_iterator.aclose()
            return frames

        frames = client.portal.call(finish_and_read_stream)
        events = [json.loads(frame.split("data: ", 1)[1]) for frame in frames]
        assert [event["type"] for event in events] == ["run.started", "run.completed"]
        assert all(event["run_id"] == run_id and event["mode"] == "live" for event in events)
        assert client.get(f"/api/runs/{run_id}").json()["status"] == "completed"


def test_live_page_requests_do_not_refresh_providers(state, monkeypatch):
    live = state_for_mode(state, "live")
    monkeypatch.setattr(app.state, "app", live, raising=False)
    refresh = Mock(side_effect=AssertionError("A page request tried to refresh a provider"))
    monkeypatch.setattr(LiveUpdates, "refresh", refresh)
    with TestClient(app) as client:
        for path in ("health", "mode", "profile/demo", "profile/questions", "mandate", "catalogue",
                     "portfolio", "portfolio/history", "portfolio/pnl", "portfolio/rebalances",
                     "benchmarks", "risk/correlation", "runs", "notifications"):
            response = client.get(f"/api/{path}")
            assert response.status_code == 200, (path, response.text)
    refresh.assert_not_called()
