"""Public demo safety (#12): passcode, budget refusal, per-IP rate limit, replay with no keys."""
import asyncio
import json
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.agents.llm import LLMCacheMiss
from app.api.demo_guard import TokenBucket
from app.container import build_state
from app.main import app
from app.settings import Settings

KEYS_OFF = {"gemini_api_key": None, "gemini_api_key_backups": None, "eodhd_api_key": None,
            "finnhub_api_key": None, "alpaca_key_id": None, "alpaca_secret_key": None}


def _state(snapshot_dir, **kw):
    s = Settings(_env_file=None, snapshot_dir=snapshot_dir, app_mode="historical", **{**KEYS_OFF, **kw})
    return build_state(s, db_path=":memory:")


def _client(monkeypatch, state):
    monkeypatch.setattr(app.state, "app", state, raising=False)
    app.state.rate_limiter = None   # fresh bucket per client; reset again after each test (fixture below)
    return TestClient(app)


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    yield
    app.state.rate_limiter = None


def _spend(state, usd):
    day = datetime.now(UTC).date().isoformat()
    state.db.put("llm_spend", day, json.dumps({"usd": usd, "tokens": 1, "calls": 1}))


# ------------------------------------------------------------------ settings
def test_public_demo_defaults_to_replay(snapshot_dir):
    assert Settings(_env_file=None, public_demo=True).llm_mode == "replay"
    assert Settings(_env_file=None, public_demo=True, llm_mode="live").llm_mode == "live"   # explicit wins
    assert Settings(_env_file=None).llm_mode == "fake"


# ------------------------------------------------------------------ passcode
def test_chat_needs_passcode_in_public_mode(snapshot_dir, monkeypatch):
    c = _client(monkeypatch, _state(snapshot_dir, public_demo=True, demo_passcode="open-sesame"))
    r = c.post("/api/chat", json={"message": "hi"})
    assert r.status_code == 401 and r.json()["error"]["code"] == "unauthorized"
    assert c.post("/api/chat", json={"message": "hi"}, headers={"X-Demo-Passcode": "wrong"}).status_code == 401
    assert c.post("/api/chat", json={"message": "hi"}, headers={"X-Demo-Passcode": "open-sesame"}).status_code == 200


def test_public_mode_without_configured_passcode_stays_locked(snapshot_dir, monkeypatch):
    c = _client(monkeypatch, _state(snapshot_dir, public_demo=True, demo_passcode=None))
    assert c.post("/api/chat", json={"message": "hi"}, headers={"X-Demo-Passcode": ""}).status_code == 401


def test_no_passcode_needed_locally(snapshot_dir, monkeypatch):
    c = _client(monkeypatch, _state(snapshot_dir, llm_mode="fake"))
    assert c.post("/api/chat", json={"message": "hi"}).status_code == 200


def test_live_agent_runs_need_passcode(snapshot_dir, monkeypatch):
    live = _client(monkeypatch, _state(snapshot_dir, public_demo=True, demo_passcode="pw", llm_mode="live"))
    assert live.post("/api/portfolio/build").status_code == 401
    assert live.post("/api/sim/start", json={"run_agents": True}).status_code == 401


def test_replay_runs_need_no_passcode(snapshot_dir, monkeypatch):
    replay = _client(monkeypatch, _state(snapshot_dir, public_demo=True, demo_passcode="pw"))
    r = replay.post("/api/sim/start", json={"speed": 0})   # engine-only replay: free, open to visitors
    assert r.status_code == 200, r.text


# ------------------------------------------------------------------ budget
def test_budget_refusal(snapshot_dir, monkeypatch):
    state = _state(snapshot_dir, public_demo=True, demo_passcode="pw", llm_mode="live", daily_llm_budget_usd=5.0)
    c = _client(monkeypatch, state)
    _spend(state, 5.01)
    pw = {"X-Demo-Passcode": "pw"}
    for path, body in [("/api/portfolio/build", None), ("/api/sim/start", {"run_agents": True}),
                       ("/api/chat", {"message": "hi"})]:
        r = c.post(path, json=body, headers=pw)
        assert r.status_code == 429, (path, r.text)
        err = r.json()["error"]
        assert err["code"] == "budget_exceeded" and err["details"] == {"limit": 5.0, "value": 5.01}
    assert any(e.type == "budget.exceeded" for e in state.events.history(None))


def test_under_budget_chat_is_allowed(snapshot_dir, monkeypatch):
    state = _state(snapshot_dir, public_demo=True, demo_passcode="pw", llm_mode="live", daily_llm_budget_usd=5.0)
    _spend(state, 1.0)
    c = _client(monkeypatch, state)
    assert c.post("/api/chat", json={"message": "hi"}, headers={"X-Demo-Passcode": "pw"}).status_code == 200


# ------------------------------------------------------------------ rate limit
def test_token_bucket_refills():
    now = [0.0]
    b = TokenBucket(per_minute=2, capacity=2, clock=lambda: now[0])
    assert b.allow("a") and b.allow("a") and not b.allow("a")
    assert b.allow("b")                     # per key
    now[0] = 30.0                           # 30 s at 2/min = 1 token back
    assert b.allow("a") and not b.allow("a")


def test_posts_are_rate_limited_per_ip_in_public_mode(snapshot_dir, monkeypatch):
    c = _client(monkeypatch, _state(snapshot_dir, public_demo=True, demo_passcode="pw", rate_limit_per_minute=3))
    ip1, ip2 = {"X-Forwarded-For": "1.1.1.1"}, {"X-Forwarded-For": "6.6.6.6, 2.2.2.2"}   # last entry = real IP
    codes = [c.post("/api/notifications/x/read", headers=ip1).status_code for _ in range(4)]
    assert codes[:3] == [404, 404, 404] and codes[3] == 429
    r = c.post("/api/notifications/x/read", headers=ip1)
    assert r.json()["error"]["code"] == "rate_limited"
    assert c.post("/api/notifications/x/read", headers=ip2).status_code == 404   # other visitor unaffected
    assert c.get("/api/health", headers=ip1).status_code == 200                  # GETs never limited
    assert c.post("/api/tasks/live-eod", headers=ip1).status_code == 401         # cron path exempt


def test_no_rate_limit_locally(snapshot_dir, monkeypatch):
    c = _client(monkeypatch, _state(snapshot_dir, rate_limit_per_minute=1))
    assert all(c.post("/api/notifications/x/read").status_code == 404 for _ in range(5))


# ------------------------------------------------------------------ replay with no keys
def test_replay_works_with_no_keys(snapshot_dir, monkeypatch):
    state = _state(snapshot_dir, public_demo=True)
    assert state.settings.llm_mode == "replay" and not state.settings.gemini_api_key

    class Answer(BaseModel):
        ok: bool

    llm = state.llm
    key = llm.cache_key("m", "sys", "prompt", Answer, "2026-07-07")
    state.db.execute("INSERT OR REPLACE INTO llm_cache(key, response, tokens, created) VALUES (?,?,?,?)",
                     (key, '{"ok": true}', 10, "2026-11-08T00:00:00Z"))
    hit = asyncio.run(llm.generate(model="m", system="sys", prompt="prompt", schema=Answer, as_of="2026-07-07"))
    assert hit.cached and Answer.model_validate_json(hit.text).ok
    with pytest.raises(LLMCacheMiss):   # an unrecorded call fails fast; it never reaches Gemini
        asyncio.run(llm.generate(model="m", system="sys", prompt="new", schema=Answer, as_of="2026-07-07"))
    assert llm.live_calls == 0

    c = _client(monkeypatch, state)
    h = c.get("/api/health").json()
    assert h["live_runs_enabled"] is True
    assert h["llm_mode"] == "replay"
    assert c.post("/api/sim/start", json={"speed": 0}).status_code == 200
