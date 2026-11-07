"""#28: the agent loop against a stub Gemini client (no network). Schema retry, failures, budgets, retries,
backup keys, cache hits on rerun, run record."""
import asyncio
import json
import re
from types import SimpleNamespace

import pytest

CALC_REAL = re.compile(r"^calc:[0-9a-f]{32}$")
ALIAS = re.compile(r"calc:[\w.]+:\d+")


class FakeAPIError(Exception):
    def __init__(self, code: int):
        super().__init__(f"HTTP {code}")
        self.code = code


def lead_brain(contents: str) -> str:
    """Lead asks for one tool, then decides citing the evidence id it was given."""
    if "TOOL correlation_lattice" not in contents:
        return json.dumps({"message": "Checking correlations.",
                           "tool_calls": [{"tool": "correlation_lattice", "args_json": "{\"lookback\": 252}"}]})
    ids = ALIAS.findall(contents)
    return json.dumps({"message": "Decided.", "final": {"decision": {
        "action": "maintain", "reason": "stub", "evidence_ids": ids[:1]}}})


class Stub:
    """Stands in for google.genai.Client. `script(key, contents, n)` returns text or raises."""

    def __init__(self, script, tokens: int = 100):
        self.script, self.tokens, self.calls, self.prompts = script, tokens, [], []

    def factory(self, key: str):
        stub = self

        async def generate_content(model, contents, config):
            stub.calls.append(key)
            stub.prompts.append(contents)
            text = stub.script(key, contents, len(stub.calls))
            um = SimpleNamespace(prompt_token_count=stub.tokens - 10, candidates_token_count=10,
                                 thoughts_token_count=0, total_token_count=stub.tokens)
            return SimpleNamespace(text=text, usage_metadata=um)

        return SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate_content)))


@pytest.fixture()
def live(snapshot_dir):
    from app.container import build_state
    from app.settings import Settings

    def make(script, tokens: int = 100):
        s = Settings(snapshot_dir=snapshot_dir, llm_mode="live", app_mode="historical",
                     gemini_api_key="key-1", gemini_api_key_backups="key-2")
        state = build_state(s, db_path=":memory:")
        stub = Stub(script, tokens)
        state.llm._client_factory = stub.factory

        async def no_sleep(_):
            return None

        state.llm._sleep = no_sleep
        return state, stub
    return make


def run(state, kind="review"):
    r = asyncio.run(state.supervisor.start(kind, "test trigger"))
    return r, state.events.history(r.run_id)


def payload(events, type_):
    return [e.payload for e in events if e.type == type_]


def test_live_run_then_rerun_is_all_cache_hits(live):
    state, stub = live(lambda key, c, n: lead_brain(c))
    r1, ev1 = run(state)
    assert r1.decision and r1.decision.action == "maintain"
    assert CALC_REAL.match(r1.decision.evidence_ids[0])          # alias mapped back to the real calc event
    calls_after_first = len(stub.calls)
    assert calls_after_first == 2 and r1.tokens == 200
    done = payload(ev1, "run.completed")[0]
    assert done["cost_estimate_usd"] > 0 and "duration_s" in done

    r2, _ = run(state)                                          # same as_of, same prompts → cache
    assert len(stub.calls) == calls_after_first
    assert r2.tokens == 0 and r2.cached_calls == r2.llm_calls == 2
    assert CALC_REAL.match(r2.decision.evidence_ids[0]) and r2.decision.evidence_ids != r1.decision.evidence_ids


def test_schema_retry_once_then_succeeds(live):
    state, stub = live(lambda key, c, n: "not json" if n == 1 else lead_brain(c))
    r, ev = run(state)
    assert r.decision is not None
    assert len(stub.calls) == 3 and "DID NOT MATCH" in stub.prompts[1]
    assert not [p for p in payload(ev, "agent.status") if p["status"] == "failed"]


def test_schema_fails_twice_marks_agent_failed_and_run_completes(live):
    state, stub = live(lambda key, c, n: '{"tool_calls": "oops"}')
    r, ev = run(state)
    assert len(stub.calls) == 2                                   # 1 try + schema_retry: 1
    assert [p for p in payload(ev, "agent.status") if p["status"] == "failed"]
    assert any("failed" in u for f in r.findings for u in f.uncertainties)
    assert payload(ev, "run.completed")[0]["outcome"] == "investigate_further"
    assert state.db.execute("SELECT COUNT(*) FROM llm_cache")[0][0] == 0   # invalid replies are never cached


def test_transient_error_is_retried(live):
    def script(key, c, n):
        if n == 1:
            raise FakeAPIError(503)
        return lead_brain(c)
    state, stub = live(script)
    r, _ = run(state)
    assert r.decision is not None and len(stub.calls) == 3


def test_quota_exhausted_switches_to_backup_key(live):
    def script(key, c, n):
        if key == "key-1":
            raise FakeAPIError(429)
        return lead_brain(c)
    state, stub = live(script)
    r, _ = run(state)
    assert r.decision is not None
    assert stub.calls.count("key-1") == state.llm.max_retries + 1 and "key-2" in stub.calls


def test_non_transient_error_fails_agent_without_retry(live):
    def script(key, c, n):
        raise FakeAPIError(400)
    state, stub = live(script)
    r, ev = run(state)
    assert len(stub.calls) == 1 and r.decision is None
    assert payload(ev, "run.completed")[0]["outcome"] == "investigate_further"


def test_token_budget_stops_the_run(live):
    state, stub = live(lambda key, c, n: lead_brain(c), tokens=5000)
    state.supervisor.cfg = {**state.supervisor.cfg, "run_token_budget": {"review": 1000}}
    _, ev = run(state)
    assert len(stub.calls) == 1
    assert payload(ev, "budget.exceeded")[0]["limit"] == "tokens"
    assert payload(ev, "run.completed")[0]["outcome"] == "investigate_further"


def test_run_summary_persisted(live):
    state, _ = live(lambda key, c, n: lead_brain(c))
    r, _ = run(state)
    saved = json.loads(state.db.get("runs", r.run_id))
    assert saved["status"] == "completed" and saved["outcome"] == "maintain" and saved["finished_at"]


def test_prompt_carries_as_of_and_mode(live):
    seen = []
    state, _ = live(lambda key, c, n: (seen.append(c), lead_brain(c))[1])
    run(state)
    assert f"AS_OF: {state.clock.as_of_str()}" in seen[0] and "MODE: historical" in seen[0]
