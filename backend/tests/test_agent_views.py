"""#74: agent views -> bounded forecast tilts (agents predict, code sizes). Offline."""
import asyncio
import json

from app.agents.schemas import View
from app.agents.supervisor import RunState
from app.config import params
from app.engine import forecast as fc

CAP = params()["forecast"]["max_view_tilt"]


def test_apply_views_direction_confidence_sum_and_clip():
    mu = {"A": 0.10, "B": 0.05, "C": 0.0}
    views = [{"ticker": "A", "direction": "up", "confidence": "high"},
             {"ticker": "A", "direction": "up", "confidence": "med"},          # sums past the cap -> clipped
             {"ticker": "B", "direction": "down", "confidence": "low"},
             {"ticker": "C", "direction": "neutral", "confidence": "high"},     # no tilt
             {"ticker": "ZZZ", "direction": "up", "confidence": "high"}]        # no forecast -> ignored
    out, audit = fc.apply_views(mu, views, CAP)
    assert out["A"] == mu["A"] + CAP and out["B"] == mu["B"] - 0.25 * CAP and out["C"] == 0.0
    assert {a["ticker"] for a in audit} == {"A", "B"} and "ZZZ" not in out


def _run_with_events(state, ids):
    run = RunState(run_id="run_v", kind="construction", trigger_text="t")
    for i in ids:   # make them "returned by a tool in this run"
        state.events.emit("tool.result", run_id="run_v", title="x", evidence_ids=[i], payload={"tool": "t", "ok": True})
    return run


def _collect(state, run, role, views):
    common = {"run_id": run.run_id, "agent_id": f"{role}_1", "parent_agent_id": None, "depth": 1, "role": role}
    state.supervisor._collect_views(run, role, f"{role}_1", views, common)


def test_views_need_real_evidence_and_an_allowed_role(state):
    news_id = state.gw.news()[0].id if state.gw.news() else None
    calc = state.events.emit("calc.result", run_id="run_v", title="c", payload={"name": "x", "inputs": {}, "outputs": {}})
    good_id = f"calc:{calc.id}"
    run = _run_with_events(state, [good_id] + ([news_id] if news_id else []))
    _collect(state, run, "stock_analyst", [View(ticker="VWRP.LSE", direction="up", confidence="med", evidence_ids=[good_id]),
                                           View(ticker="VAGS.LSE", direction="down", evidence_ids=["catalogue"]),
                                           View(ticker="VUAG.LSE", direction="down", evidence_ids=["made-up-id"])])
    _collect(state, run, "equity_scout", [View(ticker="VFEG.LSE", direction="up", evidence_ids=[good_id])])
    saved = [json.loads(v) for _, v in state.db.list("agent_views")]
    assert [v["ticker"] for v in saved] == ["VWRP.LSE"] and saved[0]["evidence_ids"] == [good_id]
    dropped = [e.title for e in state.events.history("run_v") if e.type == "finding" and "dropped" in e.title]
    assert not [f for f in run.findings if "dropped" in f.claim]       # audit events, not gate-checked claims
    assert len(dropped) == 3 and any("role may not" in d for d in dropped)


def test_views_expire_and_never_come_from_the_future(state):
    from app.agents.tools import _active_views
    ctx = state.supervisor.tools.ctx
    today = state.clock.as_of_str()
    days = [str(d.date()) for d in state.gw.trading_days("2026-06-01", today)]
    for key, as_of in {"fresh": days[-3], "old": days[-15], "future": "2026-12-01"}.items():
        state.db.put("agent_views", f"{as_of}|r|a|{key}", json.dumps(
            {"ticker": key, "direction": "up", "confidence": "low", "horizon_days": 10, "as_of": as_of, "role": "x"}))
    assert [v["ticker"] for v in _active_views(ctx)] == ["fresh"]


def _build(state, run):
    agent = {"run_id": run.run_id, "agent_id": "lead_1", "parent_agent_id": None, "depth": 0, "role": "lead"}
    return asyncio.run(state.supervisor.tools.call("build_options", {}, role="lead", run=run, agent=agent))


def test_build_options_applies_views_within_caps_and_ablations_switch_them_off(state):
    run = RunState(run_id="run_b", kind="construction", trigger_text="t")
    base = _build(state, run)
    w0 = {h.ticker: h.weight for h in run.scratch["options"]["recommended"].holdings}
    top = max(w0, key=w0.get)
    state.db.put("agent_views", f"{state.clock.as_of_str()}|r|a|{top}", json.dumps(
        {"ticker": top, "direction": "down", "confidence": "high", "horizon_days": 10,
         "as_of": state.clock.as_of_str(), "role": "news_analyst"}))
    run2 = RunState(run_id="run_c", kind="construction", trigger_text="t")
    out = _build(state, run2)
    names = [e.payload["name"] for e in state.events.history("run_c") if e.type == "calc.result"]
    assert "agent_view_tilt" in names and out["ok"]
    w1 = {h.ticker: h.weight for h in run2.scratch["options"]["recommended"].holdings}
    caps = params()["forecast"]
    assert all(abs(w1.get(t, 0) - w0.get(t, 0)) <= caps["max_tilt_per_holding"] + 1e-6 for t in set(w0) | set(w1))
    state.views_off = True
    run3 = RunState(run_id="run_d", kind="construction", trigger_text="t")
    _build(state, run3)
    assert "agent_view_tilt" not in [e.payload["name"] for e in state.events.history("run_d") if e.type == "calc.result"]
    state.views_off, state.forecast_off = False, True
    run4 = RunState(run_id="run_e", kind="construction", trigger_text="t")
    _build(state, run4)
    assert not [e for e in state.events.history("run_e") if e.type == "calc.result"
                and e.payload["name"] in ("forecast_2w", "agent_view_tilt")]          # bug fix: forecast_off honoured
    assert base["ok"]


def test_fake_construction_drops_a_catalogue_only_view(state):
    run = asyncio.run(state.supervisor.start("construction", "build"))
    claims = [e.title for e in state.events.history(run.run_id) if e.type == "finding"]
    assert any("dropped: no supported evidence" in c for c in claims)
    assert state.db.list("agent_views") == []
