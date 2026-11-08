"""Live profile boundaries, follow-up and durable mandate history (#8)."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.container import build_state
from app.profile.quiz import mandate_for
from app.settings import Settings


@pytest.fixture
def live_api(snapshot_dir, tmp_path, monkeypatch):
    from app.main import app

    settings = Settings(_env_file=None, snapshot_dir=snapshot_dir, app_mode="live", llm_mode="fake",
                        state_db=tmp_path / "visitor.sqlite")
    state = build_state(settings)
    monkeypatch.setattr(app.state, "app", state, raising=False)
    with TestClient(app) as client:
        yield client, state


@pytest.mark.parametrize(("section", "field", "value"), [
    ("ranges", "equity", [0.4, 0.9]),
    ("ranges", "bond", [0.1, 0.55]),
    ("ranges", "cash_min", 0.0),
    ("ranges", "equity", [0.6, 0.4]),
    ("ranges", "cash_min", 0.4),  # minima cannot sum above one
    ("caps", "per_fund", 0.9),
    ("caps", "per_stock", -0.1),
    ("caps", "stocks_total", 0.5),
    ("goal", "starting_amount_gbp", -1),
    ("approval", "require_user_approval", False),
])
def test_invalid_edit_does_not_mutate_or_persist(live_api, section, field, value):
    client, state = live_api
    before = client.get("/api/mandate").json()
    edited = json.loads(json.dumps(before))
    edited[section][field] = value
    response = client.put("/api/mandate", json=edited)
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["details"]["fields"]
    assert client.get("/api/mandate").json() == before
    assert state.db.list("mandate") == []


def test_edit_history_survives_restart_and_mode_switch(live_api):
    client, state = live_api
    before = client.get("/api/mandate").json()
    edited = json.loads(json.dumps(before))
    edited["ranges"]["equity"] = [0.45, 0.55]
    edited["caps"]["per_stock"] = 0.02
    response = client.put("/api/mandate", json=edited)
    assert response.status_code == 200, response.json()
    saved = response.json()
    assert saved["version"] == before["version"] + 1
    assert json.loads(state.db.get("mandate", "1")) == before
    assert json.loads(state.db.get("mandate", str(saved["version"]))) == saved
    assert json.loads(state.db.get("mandate", "latest")) == saved
    assert state.events.history(limit=1)[0].type == "mandate.updated"
    restarted = build_state(state.settings)
    assert restarted.mandate.model_dump(mode="json") == saved
    client.post("/api/mode", json={"mode": "historical"})
    assert client.get("/api/mandate").json() != saved
    client.post("/api/mode", json={"mode": "live"})
    assert client.get("/api/mandate").json() == saved


def test_profile_cannot_be_changed_by_edit(live_api):
    client, _ = live_api
    response = client.put("/api/mandate", json=mandate_for("adventurous").model_dump(mode="json"))
    assert response.status_code == 422
    assert "profile" in response.json()["error"]["details"]["fields"]


def test_stale_edit_cannot_overwrite_newer_mandate(live_api):
    client, _ = live_api
    old = client.get("/api/mandate").json()
    assert client.put("/api/mandate", json=old).status_code == 200
    response = client.put("/api/mandate", json=old)
    assert response.status_code == 422
    assert "version" in response.json()["error"]["details"]["fields"]


@pytest.mark.parametrize("payload", [{"ranges": {}}, {"answers": {}, "follow_up_answer": "maybe"}])
def test_invalid_request_shapes_use_error_envelope(live_api, payload):
    client, _ = live_api
    response = (client.post("/api/profile/quiz", json=payload) if "answers" in payload
                else client.put("/api/mandate", json=payload))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert response.json()["error"]["details"]["fields"]


@pytest.mark.parametrize("answer", ["yes", "no"])
def test_follow_up_rescores_without_overriding_other_capacity_limits(live_api, answer):
    client, state = live_api
    answers = {"horizon": "lt3", "emergency": "no", "loss_goal": "yes", "income": "unsteady",
               "reaction": "buy", "swings": "widest", "worry": "rarely"}
    first = client.post("/api/profile/quiz", json={"answers": answers}).json()
    assert first["profile"]["conflict"] and first["profile"]["follow_up_question"]
    response = client.post("/api/profile/quiz", json={"answers": answers, "follow_up_answer": answer})
    assert response.status_code == 200
    body = response.json()
    assert body["profile"]["follow_up_question"] is None
    assert body["mandate"]["profile"] == "cautious"
    assert body["mandate"]["version"] == first["mandate"]["version"] + 1
    assert json.loads(state.db.get("mandate", "latest")) == body["mandate"]


def test_documented_fixtures_match_live_contract(live_api):
    client, _ = live_api
    fixtures = Path(__file__).resolve().parents[2] / "fixtures"
    edited = client.get("/api/mandate").json()
    edited["ranges"]["equity"][1] = 0.9
    expected = json.loads((fixtures / "mandate_validation_error.json").read_text())
    assert client.put("/api/mandate", json=edited).json() == expected
    payload = json.loads((fixtures / "quiz_follow_up_request.json").read_text())
    response = client.post("/api/profile/quiz", json=payload)
    assert response.status_code == 200
    assert response.json()["profile"]["follow_up_question"] is None


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_weights_are_rejected_without_mutation(live_api, literal):
    client, state = live_api
    before = client.get("/api/mandate").json()
    raw = json.dumps(before).replace('"cash_min": 0.03', f'"cash_min": {literal}')
    response = client.put("/api/mandate", content=raw, headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert "ranges.cash_min" in response.json()["error"]["details"]["fields"]
    assert state.db.list("mandate") == []


def test_steadier_follow_up_uses_lower_tolerance(live_api):
    client, _ = live_api
    answers = {"horizon": "gt15", "emergency": "yes", "loss_goal": "no", "income": "steady",
               "reaction": "some", "swings": "mid", "worry": "weekly"}
    first = client.post("/api/profile/quiz", json={"answers": answers}).json()
    assert first["profile"]["conflict"]
    body = client.post("/api/profile/quiz", json={"answers": answers, "follow_up_answer": "yes"}).json()
    assert body["profile"]["tolerance_score"] <= first["profile"]["tolerance_score"]
    assert body["profile"]["name"] == "cautious"
    assert body["profile"]["follow_up_question"] is None
