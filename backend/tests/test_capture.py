import asyncio
import json
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from app.agents.llm import LLM, LLMError
from app.core.db import DB
from app.settings import Settings
from app.sim.capture import CaptureBudget, CaptureError, capture, check_real_inputs


def test_budget_survives_attempts_and_stops_at_threshold(tmp_path):
    path = tmp_path / "budget.json"
    first = CaptureBudget(path, 5)
    first.record(2, 100)
    second = CaptureBudget(path, 5)
    second.check()
    second.record(3, 200)
    with pytest.raises(CaptureError):
        first.check()
    assert first.read() == {"limit_usd": 5, "usd": 5, "tokens": 300, "calls": 2}
    with pytest.raises(ValueError):
        CaptureBudget(path, 10)


def test_existing_attempt_is_never_replaced(tmp_path, snapshot_dir):
    out = tmp_path / "existing"
    out.mkdir()
    marker = out / "recording.sqlite"
    marker.write_bytes(b"preserve this recording")
    with pytest.raises(FileExistsError):
        asyncio.run(capture(Settings(snapshot_dir=snapshot_dir), out, tmp_path / "budget.json",
                            5, "2026-07-07", "2026-07-10"))
    assert marker.read_bytes() == b"preserve this recording"


def test_synthetic_inputs_are_rejected(state):
    with pytest.raises(CaptureError, match="verified EODHD"):
        check_real_inputs(state)


def test_preflight_runs_offline_and_does_not_publish_ready(tmp_path, snapshot_dir, monkeypatch):
    monkeypatch.setattr("app.sim.capture.check_real_inputs", lambda state: None)
    out = tmp_path / "preflight"
    result = asyncio.run(capture(Settings(snapshot_dir=snapshot_dir, llm_mode="fake"), out,
                                 tmp_path / "budget.json", 5, "2026-07-07", "2026-07-10", agents=False))
    assert result["status"] == "preflight_passed" and result["days"] == 4
    assert result["llm_calls"] == 0 and result["estimated_campaign_spend"]["usd"] == 0
    assert not (out / "READY.json").exists()
    assert (out / "recording.sqlite").is_file()
    assert not (tmp_path / "budget.lock").exists()


def test_failure_keeps_diagnostics_without_ready(tmp_path, snapshot_dir, monkeypatch):
    monkeypatch.setattr("app.sim.capture.check_real_inputs", lambda state: None)
    async def fail(self):
        raise RuntimeError("injected offline failure")
    monkeypatch.setattr("app.sim.capture.Simulation.step", fail)
    out = tmp_path / "failed"
    with pytest.raises(RuntimeError):
        asyncio.run(capture(Settings(snapshot_dir=snapshot_dir, llm_mode="fake"), out,
                            tmp_path / "budget.json", 5, "2026-07-07", "2026-07-10", agents=False))
    report = json.loads((out / "attempt.json").read_text(encoding="utf-8"))
    assert report["status"] == "incomplete" and report["error_type"] == "RuntimeError"
    assert not (out / "READY.json").exists() and (out / "recording.sqlite").is_file()


def test_live_request_guard_and_spend_callback_do_not_affect_cached_replay(tmp_path):
    class Reply(BaseModel):
        ok: bool
    calls = []
    async def generate_content(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(text='{"ok":true}', usage_metadata=SimpleNamespace(
            prompt_token_count=10, candidates_token_count=5, thoughts_token_count=0, total_token_count=15))
    client = SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate_content)))
    llm = LLM(DB(), Settings(llm_mode="live", gemini_api_key="unit-test"), client_factory=lambda key: client)
    budget = CaptureBudget(tmp_path / "budget.json", 5)
    llm.before_live_call, llm.on_spend = budget.check, budget.record
    args = {"model": "gemini-3.8-flash", "system": "test", "prompt": "first", "schema": Reply, "as_of": "2026-07-07"}
    asyncio.run(llm.generate(**args))
    assert budget.read()["calls"] == 1 and len(calls) == 1
    budget.record(5, 1)
    assert asyncio.run(llm.generate(**args)).cached  # already captured response is free
    with pytest.raises(CaptureError):
        asyncio.run(llm.generate(**{**args, "prompt": "new request"}))
    assert len(calls) == 1


def test_provider_error_messages_do_not_include_request_secrets():
    class ProviderError(Exception):
        code = 400
    async def fail(**kwargs):
        raise ProviderError("https://provider.invalid?token=do-not-emit-this")
    client = SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=fail)))
    llm = LLM(DB(), Settings(llm_mode="live", gemini_api_key="unit-test"), client_factory=lambda key: client)
    with pytest.raises(LLMError) as error:
        asyncio.run(llm._call_live("gemini-3.8-flash", "test", "test", None, False))
    assert "do-not-emit-this" not in str(error.value)


@pytest.mark.parametrize("event_type,title", [
    ("agent.status", "Agent failed"), ("run.completed", "Run failed"),
    ("budget.exceeded", "Run limit"), ("decision.made", "Initial portfolio built by the engine"),
])
def test_agent_failure_or_fallback_stops_before_next_day(tmp_path, snapshot_dir, monkeypatch, event_type, title):
    monkeypatch.setattr("app.sim.capture.check_real_inputs", lambda state: None)
    days = []
    async def failed_step(self):
        days.append(self.i)
        self.state.events.emit(event_type, title=title, status="failed")
        self.i += 1
    monkeypatch.setattr("app.sim.capture.Simulation.step", failed_step)
    out = tmp_path / "failed-agent"
    with pytest.raises(CaptureError, match="technical agent failure"):
        asyncio.run(capture(Settings(snapshot_dir=snapshot_dir, llm_mode="live"), out,
                            tmp_path / "budget.json", 5, "2026-07-07", "2026-07-10"))
    assert days == [0] and not (out / "READY.json").exists()


def test_snapshot_text_is_utf8(tmp_path, snapshot_dir):
    import shutil

    from app.data.snapshot import load_snapshot
    for name in ("prices_daily.parquet", "fx_daily.parquet"):
        shutil.copy2(snapshot_dir / name, tmp_path / name)
    news = {"id": "utf8", "tickers": ["AAPL.US"], "headline": "£ prices — marchés",
            "source": "unit-test", "published_at": "2026-07-07T10:00:00+00:00",
            "available_at": "2026-07-07T10:00:00+00:00"}
    (tmp_path / "news.jsonl").write_text(json.dumps(news, ensure_ascii=False) + "\n", encoding="utf-8")
    (tmp_path / "manifest.json").write_text('{"label":"unit-test"}', encoding="utf-8")
    assert load_snapshot(tmp_path).news[0].headline == news["headline"]
