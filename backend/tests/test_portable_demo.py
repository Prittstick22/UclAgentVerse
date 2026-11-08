"""The public bundle works in a clean directory with no keys and no provider requests."""
import hashlib
import importlib.util
import json
import shutil
import zipfile
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.container import build_state
from app.main import app, mount_frontend
from app.settings import Settings

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("portable_demo", ROOT / "scripts/demo.py")
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


@pytest.fixture
def fresh_bundle(tmp_path):
    shutil.copytree(ROOT / "demo", tmp_path / "demo")
    manifest, data = launcher.prepare_bundle(tmp_path)
    return tmp_path, manifest, data


def test_complete_bundle_replays_without_keys_or_external_calls(fresh_bundle, monkeypatch):
    root, manifest, data = fresh_bundle
    before = launcher.sha256(data / "recording.sqlite")
    settings = Settings(_env_file=None, app_mode="historical", llm_mode="replay", replay_only=True,
                        public_demo=True, recorded_run=data / "recording.sqlite", snapshot_dir=data / "snapshot",
                        state_db=root / "runtime.sqlite", gemini_api_key=None, gemini_api_key_backups=None,
                        eodhd_api_key=None, finnhub_api_key=None, task_secret=None)
    calls = ["app.data.adapters.eodhd.EODHD." + name for name in ("eod", "news", "live")]
    calls += ["app.data.adapters.finnhub.Finnhub." + name for name in ("company_news", "earnings_calendar")]
    calls += ["app.data.adapters.edgar.Edgar." + name for name in ("submissions", "document")]
    with ExitStack() as stack:
        mocks = [stack.enter_context(patch(name, side_effect=AssertionError("No provider calls"))) for name in calls]
        model = stack.enter_context(patch("app.agents.llm.LLM._call_live", new=AsyncMock(side_effect=AssertionError("No model calls"))))
        state = build_state(settings)
        monkeypatch.setattr(app.state, "app", state, raising=False)
        app.state.rate_limiter = None
        with TestClient(app) as client:
            health = client.get("/api/health").json()
            assert health["live_runs_enabled"] is False
            assert health["as_of"] == manifest["end"] and health["llm_mode"] == "replay"
            portfolio = client.get("/api/portfolio").json()
            assert len(portfolio["holdings"]) == 4
            assert len(client.get("/api/runs").json()["items"]) == 9
            assert len(client.get("/api/benchmarks").json()["series"]) == 5
            refs = set()
            for (raw,) in state.db.execute("SELECT json FROM events"):
                event = json.loads(raw)
                refs.update(event.get("evidence_ids", []))
                if event["type"] == "calc.result":
                    refs.add("calc:" + event["id"])
            assert len(refs) == 54
            assert all(client.get("/api/evidence/" + ref).status_code == 200 for ref in refs)
            assert client.post("/api/sim/step", json={"days": 1}).status_code == 200
            assert client.get("/api/health").json()["as_of"] == manifest["start"]
            assert client.post("/api/sim/step", json={"days": 1000}).status_code == 200
            assert client.get("/api/portfolio").json() == portfolio
            assert client.post("/api/mode", json={"mode": "live"}).status_code == 200
            assert client.get("/api/health").json()["live_runs_enabled"] is False
            assert client.get("/api/profile/questions").status_code == 200
            for path in ("/api/portfolio/build", "/api/portfolio/review"):
                response = client.post(path)
                assert response.status_code == 409 and "offline demo" in response.json()["error"]["message"]
            assert client.post("/api/mode", json={"mode": "historical"}).status_code == 200
            assert client.get("/api/portfolio").json() == portfolio
        assert model.call_count == 0 and all(mock.call_count == 0 for mock in mocks)
        for mode in state.modes.values():
            mode.db.conn.close()
    app.state.rate_limiter = None
    assert launcher.sha256(data / "recording.sqlite") == before == manifest["recording_sha256"]


def test_cache_tampering_is_refused_without_overwriting(fresh_bundle):
    root, _, data = fresh_bundle
    recording = data / "recording.sqlite"
    recording.write_bytes(b"preserve damaged copy for diagnosis")
    with pytest.raises(ValueError, match="missing or changed"):
        launcher.prepare_bundle(root)
    assert recording.read_bytes() == b"preserve damaged copy for diagnosis"


def test_archive_tampering_is_refused_before_extraction(tmp_path):
    shutil.copytree(ROOT / "demo", tmp_path / "demo")
    manifest = json.loads((tmp_path / "demo/manifest.json").read_text(encoding="utf-8"))
    (tmp_path / "demo" / manifest["archive"]).write_bytes(b"changed archive")
    with pytest.raises(ValueError, match="archive checksum"):
        launcher.prepare_bundle(tmp_path)
    assert not (tmp_path / ".demo-data").exists()


def test_archive_cannot_escape_its_cache(tmp_path):
    demo = tmp_path / "demo"
    demo.mkdir()
    archive = demo / "bad.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("../escape", "bad")
    (demo / "manifest.json").write_text(json.dumps({"archive": "bad.zip", "archive_sha256": launcher.sha256(archive),
        "bundle_id": "bad", "files": {"../escape": hashlib.sha256(b"bad").hexdigest()}}), encoding="utf-8")
    with pytest.raises(ValueError, match="Unsafe path"):
        launcher.prepare_bundle(tmp_path)
    assert not (tmp_path / "escape").exists()


def test_launcher_environment_overrides_host_keys_and_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "unit-test-host-key")
    monkeypatch.setenv("LLM_MODE", "live")
    env = launcher.replay_environment(tmp_path, tmp_path / "bundle")
    assert env["GEMINI_API_KEY"] == "" and env["LLM_MODE"] == "replay" and env["REPLAY_ONLY"] == "1"
    assert Path(env["RECORDED_RUN"]) == tmp_path / "bundle/recording.sqlite"
    assert Path(env["STATIC_DIR"]) == tmp_path / "frontend/dist"
    assert not (tmp_path / ".env").exists()
def test_frontend_navigation_does_not_swallow_unknown_api_routes(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<title>Stead</title>", encoding="utf-8")
    web = FastAPI()
    mount_frontend(web, tmp_path)
    with TestClient(web) as client:
        assert client.get("/onboarding").text == "<title>Stead</title>"
        missing = client.get("/api/unknown")
        assert missing.status_code == 404
        assert missing.json()["error"]["code"] == "not_found"
