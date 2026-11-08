"""Historical persona is fixed; live visitors can still create and edit their mandate."""

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.config import demo_persona
from app.container import build_state, state_for_mode
from app.profile.quiz import mandate_for, score
from app.schemas import Goal


@pytest.fixture
def api(state, monkeypatch):
    from app.main import app

    monkeypatch.setattr(app.state, "app", state, raising=False)
    with TestClient(app) as client:
        yield client


def test_demo_response_matches_config_scoring_and_historical_mandate(api):
    persona = demo_persona()
    response = api.get("/api/profile/demo")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"name", "age", "story", "profile", "goal", "answers", "synthetic", "result", "mandate"}
    for key in ("name", "age", "story", "profile", "goal", "answers", "synthetic"):
        assert body[key] == persona[key]
    assert body["synthetic"] is True
    assert body["result"] == score(persona["answers"]).model_dump(mode="json")
    expected = mandate_for(persona["profile"], Goal(**persona["goal"]), persona["exclusions"])
    assert body["mandate"] == expected.model_dump(mode="json") == api.get("/api/mandate").json()


@pytest.mark.parametrize("endpoint", ["/api/profile/quiz", "/api/mandate"])
def test_historical_edits_are_refused_without_mutation(api, state, endpoint):
    before = state.mandate.model_dump(mode="json")
    if endpoint.endswith("quiz"):
        response = api.post(endpoint, json={"answers": {}})
    else:
        edited = mandate_for("growth").model_dump(mode="json")
        response = api.put(endpoint, json=edited)
    assert response.status_code == 409
    assert response.json() == {"error": {
        "code": "validation_error",
        "message": "This demo follows Priya. Switch to live mode to create your own profile.",
        "details": {},
    }}
    assert state.mandate.model_dump(mode="json") == before
    assert api.get("/api/mandate").json() == before


def test_live_quiz_and_edit_survive_mode_switch_without_changing_demo(api, state):
    historical = api.get("/api/mandate").json()
    assert api.post("/api/mode", json={"mode": "live"}).status_code == 200
    assert api.get("/api/mandate").json() == mandate_for("balanced").model_dump(mode="json")
    goal = Goal(name="Visitor goal", starting_amount_gbp=2000, monthly_contribution_gbp=50)
    response = api.post("/api/profile/quiz", json={
        "answers": {}, "goal": goal.model_dump(), "exclusions": ["AAPL.US"],
    })
    assert response.status_code == 200
    mandate = response.json()["mandate"]
    assert mandate["profile"] == "cautious"
    assert mandate["goal"] == goal.model_dump()
    assert mandate["exclusions"] == ["AAPL.US"]
    mandate["goal"]["name"] = "Edited live goal"
    edited = api.put("/api/mandate", json=mandate)
    assert edited.status_code == 200
    assert edited.json()["version"] == mandate["version"] + 1
    assert api.get("/api/profile/demo").json()["mandate"] == historical
    assert api.get("/api/mandate").json() == edited.json()
    assert api.post("/api/mode", json={"mode": "historical"}).status_code == 200
    assert api.get("/api/mandate").json() == historical
    assert api.post("/api/profile/quiz", json={"answers": {}}).status_code == 409
    api.post("/api/mode", json={"mode": "live"})
    assert api.get("/api/mandate").json() == edited.json()
    assert state.mandate.model_dump(mode="json") == historical


def test_historical_state_created_from_live_uses_persona(snapshot_dir):
    from app.settings import Settings

    live = build_state(Settings(snapshot_dir=snapshot_dir, llm_mode="fake", app_mode="live"), db_path=":memory:")
    historical = state_for_mode(live, "historical")
    persona = demo_persona()
    assert historical.mandate == mandate_for(persona["profile"], Goal(**persona["goal"]), persona["exclusions"])
    assert live.mandate == mandate_for("balanced")


@pytest.mark.parametrize("profile", ["balanced", "cautious", "growth", "adventurous"])
def test_cli_recording_keeps_full_starting_mandate(api, state, tmp_path, monkeypatch, profile):
    from app.container import build_state as real_build_state
    from app.settings import Settings
    from app.sim import runner

    def offline_state(db_path):
        settings = Settings(_env_file=None, snapshot_dir=state.settings.snapshot_dir, llm_mode="fake")
        return real_build_state(settings, db_path=db_path)

    monkeypatch.setattr(runner, "build_state", offline_state)
    record = tmp_path / f"{profile}.sqlite"
    days = state.gw.trading_days(state.clock.as_of_str())
    runner.main(["--no-agents", "--start", str(days[0].date()), "--end", str(days[1].date()),
                 "--profile", profile, "--record", str(record)])

    with sqlite3.connect(f"{record.as_uri()}?mode=ro", uri=True) as db:
        stored = db.execute("SELECT json FROM kv WHERE ns = ? AND key = ?", ("sim_mandate", "initial")).fetchone()
        assert stored is not None
        mandate = json.loads(stored[0])
        assert db.execute("SELECT COUNT(*) FROM events").fetchone()[0] > 0
        assert db.execute("SELECT json FROM kv WHERE ns = 'sim_results' AND key = 'latest'").fetchone()

    expected = (api.get("/api/profile/demo").json()["mandate"] if profile == "balanced"
                else mandate_for(profile).model_dump(mode="json"))
    assert mandate == expected
