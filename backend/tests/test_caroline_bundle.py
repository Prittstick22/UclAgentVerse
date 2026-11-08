"""A second persona's recording can be packaged, shared via the repo, and replayed (offline, synthetic inputs)."""
import asyncio
import hashlib
import importlib.util
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.container import build_state
from app.main import app
from app.profile.demo import demo_mandate
from app.settings import Settings
from app.sim.runner import run

ROOT = Path(__file__).resolve().parents[2]


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


launcher, builder = load("launcher", "scripts/demo.py"), load("builder", "scripts/make_demo_bundle.py")


@pytest.fixture(scope="module")
def attempt(snapshot_dir, tmp_path_factory):
    """A short Caroline recording with fake agents, laid out like a validated capture attempt."""
    folder = tmp_path_factory.mktemp("caroline-attempt")
    path = folder / "recording.sqlite"
    settings = Settings(_env_file=None, snapshot_dir=snapshot_dir, llm_mode="fake", app_mode="historical",
                        demo_persona="caroline", public_demo=False, recorded_run=None, runs_dir=folder / "unused")
    state = build_state(settings, db_path=str(path))
    try:
        assert state.mandate == demo_mandate("caroline") and state.mandate.profile == "aggressive"
        state.db.put("sim_mandate", "initial", state.mandate.model_dump_json())
        days = state.gw.trading_days("2026-07-07")[:state.mandate.review_every_n_days + 1]
        result = asyncio.run(run(state, str(days[0].date()), str(days[-1].date()), agents=True,
                                 approvals="batch_policy"))
        assert result.fills > 0
    finally:
        state.db.conn.close()
    report = {"status": "validated", "start": str(days[0].date()), "end": str(days[-1].date()), "days": len(days),
              "agent_runs": 1, "recording_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    (folder / "READY.json").write_text(json.dumps(report), encoding="utf-8")
    return folder


@pytest.fixture
def repo(attempt, snapshot_dir, tmp_path):
    """A scratch copy of the bundle area, so the real demo/ folder is never written by tests."""
    (tmp_path / "demo").mkdir()
    builder.build("caroline", attempt, snapshot_dir, "Test clearance wording", root=tmp_path)
    return tmp_path


def test_bundle_round_trips_through_the_launcher(repo, attempt):
    manifest, data = launcher.prepare_bundle(repo, persona="caroline")
    assert manifest["persona"] == "caroline" and manifest["bundle_id"].startswith("caroline-")
    assert manifest["distribution_clearance"]["confirmation"] == "Test clearance wording"
    assert launcher.sha256(data / "recording.sqlite") == manifest["recording_sha256"]
    env = launcher.replay_environment(repo, data, persona="caroline")
    assert env["DEMO_PERSONA"] == "caroline" and Path(env["RECORDED_RUN"]) == data / "recording.sqlite"
    assert launcher.replay_environment(repo, data)["DEMO_PERSONA"] == "priya"


def test_caroline_replays_with_her_own_profile_and_mandate(repo, monkeypatch):
    manifest, data = launcher.prepare_bundle(repo, persona="caroline")
    settings = Settings(_env_file=None, app_mode="historical", llm_mode="replay", replay_only=True, public_demo=True,
                        demo_persona="caroline", recorded_run=data / "recording.sqlite",
                        snapshot_dir=data / "snapshot", state_db=repo / "runtime.sqlite", gemini_api_key=None)
    state = build_state(settings)
    monkeypatch.setattr(app.state, "app", state, raising=False)
    app.state.rate_limiter = None
    try:
        with TestClient(app) as client:
            profile = client.get("/api/profile/demo").json()
            assert profile["name"] == "Caroline" and profile["profile"] == "aggressive"
            assert profile["mandate"]["caps"]["stocks_min"] == 0.57
            assert client.get("/api/health").json()["as_of"] == manifest["end"]
            held = client.get("/api/portfolio").json()["holdings"]
            kinds = {i.ticker: i.kind for i in state.gw.catalogue(eligible_only=False)}
            assert any(kinds[h["ticker"]] == "stock" for h in held)   # holds single stocks, unlike Priya
            assert client.post("/api/mode", json={"mode": "live"}).status_code == 200
            blocked = client.post("/api/portfolio/build")
            assert blocked.status_code == 409 and "replays Caroline" in blocked.json()["error"]["message"]
    finally:
        for mode in state.modes.values():
            mode.db.conn.close()
        app.state.rate_limiter = None


def test_priya_is_still_the_default_persona():
    assert Settings(_env_file=None).demo_persona == "priya"


def test_one_server_selects_both_recordings_per_browser(tmp_path, monkeypatch):
    bundles = {
        persona: launcher.prepare_bundle(ROOT, tmp_path / persona, persona=persona)[1]
        for persona in ("priya", "caroline")
    }
    settings = Settings(_env_file=None, snapshot_dir=tmp_path / "empty-snapshot",
                        state_db=tmp_path / "state.sqlite", llm_mode="replay", replay_only=True, demo_bundles=bundles)
    state = build_state(settings)
    monkeypatch.setattr(app.state, "app", state, raising=False)
    try:
        with TestClient(app) as caroline:
            priya = TestClient(app)
            assert set(priya.get("/api/profile/demos").json()) == {"priya", "caroline"}
            assert priya.post("/api/mode", json={"mode": "historical", "persona": "priya"}).is_success
            assert caroline.post("/api/mode", json={"mode": "historical", "persona": "caroline"}).is_success
            assert caroline.get("/api/profile/demo").json()["name"] == "Caroline"
            assert priya.get("/api/profile/demo").json()["name"] == "Priya"
            assert caroline.get("/api/mandate").json()["profile"] == "aggressive"
            assert priya.get("/api/mandate").json()["profile"] == "balanced"
            assert caroline.get("/api/portfolio").json()["nav_gbp"] != priya.get("/api/portfolio").json()["nav_gbp"]
            assert caroline.get("/api/benchmarks").json() != priya.get("/api/benchmarks").json()
            fills = caroline.get("/api/portfolio/rebalances?limit=500").json()["items"]
            assert sum(len(batch["changes"]) for batch in fills) == 59
            assert all(batch["run_id"] is None for batch in fills)
            run_id = caroline.get("/api/runs").json()["items"][0]["run_id"]
            events = f"/api/runs/{run_id}/events"
            assert caroline.get(events + "?format=json").json()["items"]
            assert priya.get(events + "?format=json").json()["items"] == []
            assert "event: run.completed" in caroline.get(events).text
            assert caroline.post("/api/mode", json={"mode": "live"}).is_success
            assert caroline.get("/api/portfolio").json()["mode"] == "live"
            assert state.modes["live"].gw.snapshot.source_label == "eodhd"
            assert priya.get("/api/portfolio").json()["mode"] == "historical"
            assert caroline.get("/api/portfolio?mode=historical").json()["nav_gbp"] != priya.get("/api/portfolio").json()["nav_gbp"]
            assert caroline.post("/api/portfolio/build").status_code == 409
            assert caroline.post("/api/mode", json={"mode": "historical"}).is_success
            assert caroline.get("/api/profile/demo").json()["name"] == "Caroline"
            assert caroline.post("/api/mode", json={"mode": "historical", "persona": "priya"}).is_success
            assert caroline.get("/api/profile/demo").json()["name"] == "Priya"
            priya.close()
    finally:
        for st in [*state.demo_states.values(), state.modes["live"]]:
            st.db.conn.close()
    assert demo_mandate().profile == "balanced"


def test_builder_refuses_incomplete_or_unsafe_input(attempt, snapshot_dir, tmp_path):
    (tmp_path / "demo").mkdir()
    bad = tmp_path / "bad-attempt"
    shutil.copytree(attempt, bad)
    (bad / "READY.json").unlink()
    with pytest.raises(ValueError, match="READY.json"):
        builder.build("caroline", bad, snapshot_dir, "x", root=tmp_path)
    leaky = tmp_path / "leaky"
    shutil.copytree(snapshot_dir, leaky)
    (leaky / "news.jsonl").write_bytes(b'{"url": "https://eodhd.com/api/news?api_token=abc123"}\n')
    with pytest.raises(ValueError, match="credential"):
        builder.build("caroline", attempt, leaky, "x", root=tmp_path)
    assert not list((tmp_path / "demo").rglob("*.zip"))


def test_a_published_bundle_is_never_overwritten(repo, attempt, snapshot_dir):
    with pytest.raises(ValueError, match="immutable"):
        builder.build("caroline", attempt, snapshot_dir, "x", root=repo)
