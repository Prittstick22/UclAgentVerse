"""Exposure + overlap (#25): look-through ownership and fund overlap, never a predicted loss."""
import asyncio

import pytest

from app.agents.tools import ToolContext, default_registry
from app.engine import exposure

HOLD = {
    "FUND_A": [{"ticker": "X", "name": "X Corp", "weight": 0.30}, {"ticker": "Y", "name": "Y plc", "weight": 0.20}],
    "FUND_B": [{"ticker": "X", "name": "X Corp", "weight": 0.10}, {"ticker": "Z", "name": "Z Inc", "weight": 0.40}],
    "FUND_N": [{"name": "Acme Ltd", "weight": 0.05}, {"name": "ACME LTD ", "weight": 0.02}],   # no tickers, 2 lines
    "FUND_M": [{"name": "acme ltd", "weight": 0.10}],
}


def test_overlap_hand_check_and_symmetry():
    r = exposure.overlap("FUND_A", "FUND_B", HOLD)
    assert r.overlap == pytest.approx(0.10)                       # min(30%, 10%) in X; Y and Z not shared
    assert [h.key for h in r.common] == ["X"] and r.common[0].weight_a == 0.30
    assert r.coverage_a == pytest.approx(0.50) and r.coverage_b == pytest.approx(0.50)
    assert exposure.overlap("FUND_B", "FUND_A", HOLD).overlap == r.overlap
    assert "lower bound" in r.note


def test_fund_vs_a_single_stock_it_holds():
    r = exposure.overlap("FUND_A", "X", HOLD, stocks={"X"})
    assert r.overlap == pytest.approx(0.30) and r.coverage_b == 1.0   # the stock 'holds' itself at 100%


def test_no_data_is_unknown_not_zero():
    r = exposure.overlap("FUND_A", "NO_DATA_FUND", HOLD)
    assert r.overlap is None and r.missing == ["NO_DATA_FUND"] and r.common == []


def test_name_matching_when_no_ticker_and_duplicate_lines_add_up():
    r = exposure.overlap("FUND_N", "FUND_M", HOLD)
    assert r.overlap == pytest.approx(0.07)                       # 5% + 2% Acme in N, 10% in M -> min = 7%


def test_pairs_sorted_biggest_first_unknown_last():
    pairs = exposure.overlap_pairs(["FUND_A", "NO_DATA", "FUND_B", "X", "FUND_A"], HOLD, stocks={"X"})
    assert len(pairs) == 6                                         # 4 distinct tickers -> 6 pairs (duplicate dropped)
    known = [p.overlap for p in pairs if p.overlap is not None]
    assert known == sorted(known, reverse=True) and pairs[0].overlap == pytest.approx(0.30)
    assert all(p.overlap is None for p in pairs[len(known):])


def test_look_through_exposure_hand_check():
    r = exposure.look_through({"FUND_A": 0.5, "FUND_B": 0.3, "X": 0.04}, HOLD, "X")
    assert r.direct == 0.04 and r.via_funds == {"FUND_A": pytest.approx(0.15), "FUND_B": pytest.approx(0.03)}
    assert r.total == pytest.approx(0.22) and "not a predicted loss" in r.note


def _tool(state, args):
    reg = default_registry(ToolContext(gw=state.gw, events=state.events, state=state))
    return asyncio.run(reg._tools["overlap"](reg.ctx, args, None))


def test_overlap_tool_on_the_snapshot(state):
    vwrp = {h.get("ticker") for h in state.gw.etf_holdings("VWRP.LSE")}
    stock = next(t for t in ("NVDA.US", "AAPL.US") if t in vwrp)
    out = _tool(state, {"tickers": ["VWRP.LSE", stock]})
    assert out["ok"] and "share" in out["summary"] and "not a predicted loss" in out["summary"]
    assert out["pairs"][0]["overlap"] > 0 and out["evidence_ids"][0].startswith("calc:")
    calc = [e for e in state.events.history(limit=10_000) if e.type == "calc.result" and e.payload["name"] == "overlap"]
    assert calc and calc[-1].payload["inputs"]["tickers"] == ["VWRP.LSE", stock]


def test_overlap_tool_says_unknown_without_data(state):
    no_data = [i.ticker for i in state.gw.catalogue() if i.kind == "etf" and not state.gw.etf_holdings(i.ticker)][:2]
    out = _tool(state, {"tickers": no_data})
    assert out["ok"] and "unknown (not zero)" in out["summary"]


def test_overlap_tool_needs_two_tickers(state):
    with pytest.raises(ValueError):
        _tool(state, {"tickers": ["VWRP.LSE"]})


def test_roles_that_list_overlap_can_now_use_it(state):
    from app.agents.roles import ROLES

    reg = default_registry(ToolContext(gw=state.gw, events=state.events, state=state))
    assert "overlap" in reg._tools
    assert any("overlap" in r.tools for r in (ROLES.values() if isinstance(ROLES, dict) else ROLES))


EDGE = {"T": [{"ticker": "NVDA.US", "name": "NVIDIA Corp.", "weight": 0.05}],
        "NAME": [{"name": "Nvidia corp", "weight": 0.03}],                                # same company, no ticker
        "PCT": [{"ticker": "X", "weight": 4.5}, {"ticker": "Y", "weight": 2.0}],          # percent, not fraction
        "PCT2": [{"ticker": "X", "weight": 3.0}, {"ticker": "Z", "weight": 1.0}],
        "TWO": [{"ticker": "X", "weight": 0.02}, {"ticker": "X", "weight": 0.01}],        # two share classes
        "BAD": [{"ticker": "X", "weight": float("nan")}, {"ticker": "Y", "weight": "abc"},
                {"ticker": "Z", "weight": None}, {"ticker": "W", "weight": 0.04}]}


def test_ticker_line_matches_a_name_only_line():
    assert exposure.overlap("T", "NAME", EDGE).overlap == pytest.approx(0.03)   # used to be 0.0


def test_percent_holdings_are_read_as_percent():
    r = exposure.overlap("PCT", "PCT2", EDGE)
    assert r.overlap == pytest.approx(0.03) and r.coverage_a == pytest.approx(0.065)   # not 300% / 100%


def test_look_through_adds_up_a_company_listed_twice():
    assert exposure.look_through({"TWO": 1.0}, EDGE, "X").total == pytest.approx(0.03)   # used to keep only 1%


def test_bad_weights_are_skipped_not_a_crash():
    r = exposure.overlap("BAD", "TWO", EDGE)
    assert r.overlap == 0.0 and r.coverage_a == pytest.approx(0.04)


def test_overlap_tool_accepts_a_comma_separated_string_and_caps_output(state):
    vwrp = {h.get("ticker") for h in state.gw.etf_holdings("VWRP.LSE")}
    stock = next(t for t in ("NVDA.US", "AAPL.US") if t in vwrp)
    out = _tool(state, {"tickers": f"VWRP.LSE, {stock}"})
    assert out["pairs"][0]["overlap"] > 0                      # used to split the string into letters
    out = _tool(state, {"tickers": [i.ticker for i in state.gw.catalogue()]})
    assert len(out["pairs"]) <= 10 and out["pairs_total"] == 66    # 12 tickers max -> 66 pairs, 10 returned
