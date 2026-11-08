"""#29: every agent tool against the engine + gateway, in fake mode (no network)."""
import asyncio
import re

import pytest

from app.agents.supervisor import RunState

CALC = re.compile(r"^calc:[0-9a-f]{32}$")


def call(state, name, args=None, role="lead", run=None):
    run = run or RunState(run_id="run_tools", kind="construction", trigger_text="test")
    agent = {"run_id": run.run_id, "agent_id": f"{role}_t", "parent_agent_id": None, "depth": 0, "role": role}
    return asyncio.run(state.supervisor.tools.call(name, args or {}, role=role, run=run, agent=agent)), run


def calc_events(state):
    return [e for e in state.events.history("run_tools") if e.type == "calc.result"]


def test_get_prices_summary(state):
    out, _ = call(state, "get_prices", {"tickers": ["VWRP.LSE", "AAPL.US"]})
    assert out["ok"] and {r["ticker"] for r in out["rows"]} == {"VWRP.LSE", "AAPL.US"}
    assert all(r["last_date"] <= state.clock.as_of_str() for r in out["rows"])
    assert CALC.match(out["evidence_ids"][0]) and calc_events(state)


@pytest.mark.parametrize("tool,args", [
    ("get_prices", {"tickers": ["VWRP.LSE"], "end": "2026-12-01"}),
    ("backtest", {"weights": {"VWRP.LSE": 1.0}, "end": "2026-12-01"}),
])
def test_no_tool_reads_past_as_of(state, tool, args):
    out, _ = call(state, tool, args)
    assert not out["ok"] and out["error"] == "asof_violation"
    assert any(e.type == "asof.violation" for e in state.events.history(None))


def test_build_options_then_check_cost_risk_backtest(state):
    out, run = call(state, "build_options")
    assert out["ok"] and set(run.scratch["options"]) == {"recommended", "lower_cost", "lower_risk"}
    assert len(calc_events(state)) == 3 and all(CALC.match(e) for e in out["evidence_ids"])
    for tool in ("check_proposal", "cost_turnover", "risk_stats", "backtest"):
        res, _ = call(state, tool, {"option": "recommended"}, run=run)
        assert res["ok"] and CALC.match(res["evidence_ids"][0]), (tool, res)
    chk, _ = call(state, "check_proposal", {"option": "recommended"}, run=run)
    assert chk["passed"]
    cost, _ = call(state, "cost_turnover", {"option": "recommended"}, run=run)
    assert cost["cost_gbp"] > 0 and cost["trades"]
    bt, _ = call(state, "backtest", {"option": "lower_risk"}, run=run)
    assert bt["end"] <= state.clock.as_of_str() and "not a forecast" in bt["label"]


def test_check_proposal_flags_concentration(state):
    out, _ = call(state, "check_proposal", {"weights": {"NVDA.US": 0.5, "VWRP.LSE": 0.48}, "cash_weight": 0.02})
    assert out["ok"] and not out["passed"]
    assert any(v["code"] == "concentration" for v in out["violations"])


def test_propose_adjustment_creates_proposal(state):
    _, run = call(state, "build_options")
    out, run = call(state, "propose_adjustment", {"option": "recommended", "purposes": {"VWRP.LSE": "core"}}, run=run)
    assert out["ok"] and run.proposal_id == out["proposal_id"]
    prop = state.proposals[run.proposal_id]
    assert prop.kind == "construction" and prop.decision_card.changes and len(prop.options) == 3
    assert "not a forecast" in prop.decision_card.body
    assert state.db.get("proposals", prop.id)
    assert any(e.type == "proposal.created" for e in state.events.history("run_tools"))


def test_propose_adjustment_refuses_mandate_breach(state):
    _, run = call(state, "build_options")
    run.scratch["options"]["recommended"].holdings[0].weight = 0.9
    out, run = call(state, "propose_adjustment", {"option": "recommended"}, run=run)
    assert not out["ok"] and out["error"] == "mandate_violation" and run.proposal_id is None


def test_propose_adjustment_is_lead_only(state):
    out, _ = call(state, "propose_adjustment", {"option": "recommended"}, role="risk_analyst")
    assert out["error"] == "tool_not_allowed"


def test_investment_case_roundtrip_bumps_version(state):
    case = {"ticker": "VWRP.LSE", "purpose": "Core global shares", "reconsider_if": ["fees rise above 0.3%"]}
    a, _ = call(state, "save_investment_case", {"case": case})
    b, _ = call(state, "save_investment_case", {"case": case})
    assert (a["version"], b["version"]) == (1, 2)
    got, _ = call(state, "get_investment_case", {"ticker": "VWRP.LSE"})
    assert got["case"]["version"] == 2 and got["evidence_ids"] == ["case:VWRP.LSE:v2"]


def test_search_filings_returns_passages_with_source_events(state):
    out, _ = call(state, "search_filings", {"ticker": "NVDA.US", "query": "suppliers"})
    assert out["ok"] and out["passages"] and out["evidence_ids"][0].startswith("filing_syn_001")
    assert any(e.type == "source.inspect" for e in state.events.history("run_tools"))


def test_earnings_calendar_past_dates_only(state):
    state.gw.snapshot.earnings = [{"ticker": "AAPL.US", "date": "2026-05-01", "source": "test"},
                                  {"ticker": "AAPL.US", "date": "2026-07-30", "source": "test"}]
    out, _ = call(state, "earnings_calendar", {"tickers": ["AAPL.US"]}, role="stock_analyst")
    assert out["ok"] and out["past_dates"] == {"AAPL.US": ["2026-05-01"]}
    assert all(r["date"] <= state.clock.as_of_str() for r in state.gw.earnings())


def test_exposure_looks_through_funds(state):
    holding = state.gw.etf_holdings("VWRP.LSE")[0]
    entity = holding.get("ticker") or holding["name"]
    out, _ = call(state, "exposure", {"entity": entity, "weights": {"VWRP.LSE": 0.6, "VAGS.LSE": 0.38}})
    assert out["ok"] and out["total"] > 0 and "not a predicted loss" in out["summary"]


def test_forecast_waits_for_engine(state):
    out, _ = call(state, "forecast", {"tickers": ["VWRP.LSE"]})
    assert out["ok"] or out["error"] == "not_available"


def test_web_search_refused_in_historical_mode(state):
    out, _ = call(state, "web_search", {"query": "Bank of England base rate"}, role="news_analyst")
    assert not out["ok"] and out["error"] == "historical_mode"
    failed = [e for e in state.events.history("run_tools") if e.type == "tool.result" and e.status == "failed"]
    assert failed and failed[-1].payload["tool"] == "web_search"


def test_fake_construction_run_is_built(state):
    run = asyncio.run(state.supervisor.start("construction", "build me a portfolio"))
    done = [e for e in state.events.history(run.run_id) if e.type == "run.completed"][-1]
    assert run.proposal_id and done.payload["outcome"] == "built"
    assert run.proposal_id in state.proposals
