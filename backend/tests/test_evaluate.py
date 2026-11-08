"""Evaluation (#24): metrics.json + table.md + chart from recorded runs; same numbers as /api/benchmarks."""
import asyncio
import json

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.config import params
from app.container import build_state
from app.engine.metrics import compute
from app.settings import Settings
from app.sim import evaluate, runner

START = params()["sim"]["start"]


def _record(snapshot_dir, path, agents=False, end=None):
    state = build_state(Settings(snapshot_dir=snapshot_dir, llm_mode="fake", app_mode="historical"), db_path=str(path))
    asyncio.run(runner.run(state, START, end, agents=agents, approvals="batch_policy"))
    return state


@pytest.fixture(scope="module")
def recorded(snapshot_dir, tmp_path_factory):
    d = tmp_path_factory.mktemp("runs")
    year, base = d / "year.sqlite", d / "no_agents.sqlite"
    states = {"year": _record(snapshot_dir, year, agents=True), "base": _record(snapshot_dir, base)}
    return d, year, base, states


def test_twr_strips_contributions_hand_check():
    nav = pd.Series([100.0, 110.0, 330.0], index=["d0", "d1", "d2"])
    m = compute(nav, pd.Series({"d2": 200.0}))
    assert m.total_return == pytest.approx(1.10 * (130 / 110) - 1)   # 10%, then 18.18% after removing the £200


def test_evaluate_writes_table_json_and_chart(recorded, tmp_path):
    _, year, base, _ = recorded
    res = evaluate.evaluate({"ours": year, "ours_no_agents": base}, tmp_path)
    m = json.loads((tmp_path / "metrics.json").read_text())
    assert set(m["metrics"]) == {"ours", "ours_no_agents", *evaluate.BENCHMARKS}
    assert m["label"] == "simulated, not a forecast" and m["window"][0] == START
    table = (tmp_path / "table.md").read_text()
    for name in ("Ours (Gemini agents + engine)", "Ours, engine only (no agents)", "Buy and hold",
                 "One global ETF (VWRP)", "Simulated, not a forecast", "Four months is one short path"):
        assert name in table
    assert (tmp_path / "nav.png").exists() or (tmp_path / "nav.svg").exists()
    c = res["ours_only"]
    assert c["reviews"] >= 1 and c["events"] > 100 and c["agent_runs"] >= c["reviews"]


def test_numbers_match_api_benchmarks(recorded, tmp_path, monkeypatch):
    from app.main import app

    _, year, _, states = recorded
    res = evaluate.evaluate({"ours": year}, tmp_path)
    monkeypatch.setattr(app.state, "app", states["year"], raising=False)
    api = TestClient(app).get("/api/benchmarks").json()
    assert api["metrics"] == res["metrics"]
    assert api["periods"]["held_out"] == res["window"]
    assert set(api["series"]) == set(res["metrics"])
    assert api["series"]["ours"][-1]["nav_gbp"] == res["final_nav_gbp"]["ours"]


def test_api_benchmarks_empty_before_any_replay(state):
    assert evaluate.benchmarks_payload(state.db)["series"] == {}


def test_every_strategy_starts_from_the_same_cash(recorded):
    _, _, _, states = recorded
    res = evaluate.load_results(states["base"].db)
    starts = {n: (s["series"][0]["date"], s["series"][0]["nav_gbp"]) for n, s in res["strategies"].items()}
    assert set(starts.values()) == {(START, float(params()["sim"]["capital_gbp"]))}


def test_benchmarks_invest_contributions_and_quarterly_is_quarterly(snapshot_dir, tmp_path):
    state = build_state(Settings(snapshot_dir=snapshot_dir, llm_mode="fake", app_mode="historical"), db_path=":memory:")
    sim = runner.Simulation(state, START)
    asyncio.run(sim.run_to_end())
    by = {b.name: b for b in sim.bench}
    for name in ("buy_and_hold", "global_etf", "mechanical_5pct"):
        led = by[name].ledger
        target_cash = 1 - sum(by[name].targets.values())
        # contributions were invested (only the target's own cash share + sub-£25 legs stay in cash);
        # before the fix ~£800 of contributions sat idle on top (about +7% of NAV)
        assert led.cash_gbp / led.nav() < target_cash + 0.03, name
    q = by["quarterly_rebalance"].ledger
    sell_months = {f.date[:7] for f in q.fills if f.action == "sell"}
    quarter_starts = {d[:7] for d, _ in by["quarterly_rebalance"].nav_series if d[5:7] in ("10", "01", "04", "07")}
    assert sell_months <= quarter_starts                     # only rebalances (sells) at a new quarter


def test_evaluate_refuses_bad_inputs(recorded, tmp_path, snapshot_dir):
    d, year, _, _ = recorded
    with pytest.raises(FileNotFoundError):
        evaluate.evaluate({"ours": d / "missing.sqlite"}, tmp_path)
    short = d / "short.sqlite"
    _record(snapshot_dir, short, end=str(build_state(Settings(snapshot_dir=snapshot_dir, llm_mode="fake"),
                                                     db_path=":memory:").gw.trading_days(START)[10].date()))
    with pytest.raises(ValueError, match="covers"):
        evaluate.evaluate({"ours": year, "short": short}, tmp_path)


def test_no_forecast_ablation_uses_no_forecast(snapshot_dir):
    state = build_state(Settings(snapshot_dir=snapshot_dir, llm_mode="fake", app_mode="historical"), db_path=":memory:")
    state.forecast_off = True
    asyncio.run(runner.run(state, START, None))
    assert not [e for e in state.events.history(limit=100000) if e.type == "calc.result"
                and e.payload.get("name") == "forecast_2w"]
    assert evaluate.load_results(state.db)["forecast"] is False
