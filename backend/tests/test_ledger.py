"""Paper ledger (#18): fills, costs, fees, realised/unrealised P&L, contributions, fill events."""
import asyncio

import pandas as pd
import pytest

from app.config import params
from app.engine.ledger import Ledger
from app.engine.metrics import compute
from app.schemas import Instrument
from app.sim import runner

COSTS = params()["costs"]
START = params()["sim"]["start"]


def inst(t, currency="GBP", ocf=0.0):
    return Instrument(ticker=t, name=t, asset_class="equity", sleeve="x", currency=currency, quote_unit=currency,
                      ocf=ocf, accumulating=True, kind="etf")


def ledger(**instruments) -> Ledger:
    return Ledger(catalogue={t: inst(t, *spec) for t, spec in instruments.items()})


def test_buy_price_up_sell_gives_the_right_realised_pnl():
    L = ledger(A=("GBP",))
    L.deposit(10_000)
    L.mark_to_market({"A": 100.0})
    L.rebalance_to({"A": 0.5}, "d1")                         # buy £5,000 = 50 units at £100
    pos = L.positions["A"]
    assert pos.units == pytest.approx(50) and pos.cost_basis_gbp == pytest.approx(5_000)
    L.mark_to_market({"A": 120.0})                           # +20%
    row = next(r for r in L.pnl_rows() if r["ticker"] == "A")
    assert row["unrealised_pnl_gbp"] == pytest.approx(1_000) and row["unrealised_pnl_pct"] == pytest.approx(0.2)
    nav = L.nav()
    L.rebalance_to({"A": 3_600 / nav}, "d2")             # A is worth £6,000: sell 20 of 50 units (£2,400)
    assert pos.units == pytest.approx(30)
    assert pos.realised_pnl_gbp == pytest.approx(20 * (120 - 100))           # £400 realised
    assert pos.cost_basis_gbp == pytest.approx(30 * 100)                      # average cost kept for the rest
    L.rebalance_to({}, "d3")                                                  # sell the rest
    assert pos.units == pytest.approx(0) and pos.realised_pnl_gbp == pytest.approx(1_000)
    assert next(r for r in L.pnl_rows() if r["ticker"] == "A")["realised_pnl_gbp"] == pytest.approx(1_000)


def test_costs_trade_and_fx_on_what_is_actually_traded():
    L = ledger(UK=("GBP",), US=("USD",))
    L.deposit(10_000)
    L.mark_to_market({"UK": 10.0, "US": 10.0})
    fills = {f.ticker: f for f in L.rebalance_to({"UK": 0.4, "US": 0.4}, "d1")}
    assert fills["UK"].cost_gbp == pytest.approx(4_000 * COSTS["trade"])
    assert fills["US"].cost_gbp == pytest.approx(4_000 * (COSTS["trade"] + COSTS["fx"]))   # FX on US shares
    assert L.costs_paid_gbp == pytest.approx(4_000 * (2 * COSTS["trade"] + COSTS["fx"]))
    assert L.cash_gbp == pytest.approx(10_000 - 8_000 - L.costs_paid_gbp)


def test_short_of_cash_buys_less_and_pays_cost_only_on_that():
    L = ledger(A=("GBP",), B=("GBP",))
    L.deposit(1_000)
    L.mark_to_market({"A": 10.0, "B": 10.0})
    fills = L.rebalance_to({"A": 0.6, "B": 0.6}, "d1")                        # asks for 120%
    spent = sum(f.amount_gbp for f in fills)
    assert L.cash_gbp >= -1e-9 and L.cash_gbp == pytest.approx(0, abs=0.01)
    assert L.costs_paid_gbp == pytest.approx(spent * COSTS["trade"], abs=0.01)  # used to charge on £1,200


def test_no_cash_no_fill_and_never_negative_cash():
    L = ledger(A=("GBP",))
    L.deposit(0.05)
    L.mark_to_market({"A": 10.0})
    assert L.rebalance_to({"A": 0.9}, "d1") == [] and L.cash_gbp == pytest.approx(0.05)


def test_trades_below_the_minimum_are_skipped():
    L = ledger(A=("GBP",))
    L.deposit(1_000)
    L.mark_to_market({"A": 10.0})
    assert L.rebalance_to({"A": params()["min_trade_gbp"] / 1_000 * 0.9}, "d1") == []


def test_fees_reduce_nav_by_ocf_over_365_per_day():
    L = ledger(A=("GBP", 0.0073))                        # 0.73% a year
    L.deposit(10_000)
    L.mark_to_market({"A": 100.0})
    L.rebalance_to({"A": 1.0}, "d1")
    before = L.nav()
    value = L.value("A")
    L.accrue_fund_fees(days=3)                            # a weekend: 3 calendar days
    assert before - L.nav() == pytest.approx(value * 0.0073 * 3 / 365)
    assert L.fees_paid_gbp == pytest.approx(value * 0.0073 * 3 / 365)


def test_contributions_do_not_count_as_returns():
    L = ledger(A=("GBP",))
    L.deposit(10_000)
    L.mark_to_market({"A": 100.0})
    L.rebalance_to({"A": 1.0}, "d0")
    navs, flows = {"d0": L.nav()}, {}
    L.deposit(200)                                        # money in, price flat
    flows["d1"] = 200
    navs["d1"] = L.nav()
    m = compute(pd.Series(navs), pd.Series(flows))
    assert L.nav() > navs["d0"] and m.total_return == pytest.approx(0.0)


def test_sim_emits_fill_events_and_invests_contributions_with_buys_only(state):
    sim = runner.Simulation(state, START)
    asyncio.run(sim.run_to_end())
    led = state.ledger
    evs = [e for e in state.events.history(limit=100_000) if e.type == "order.filled"]
    assert len(evs) == len(led.fills) > 0
    assert {"ticker", "action", "units", "price_gbp", "amount_gbp", "cost_gbp"} <= set(evs[0].payload)
    assert sum(e.payload["cost_gbp"] for e in evs) == pytest.approx(led.costs_paid_gbp, abs=0.05)
    first_fill = led.fills[0].date
    for day in sim.flows:                                  # contribution days: invested, never a rebalance
        fills = [f for f in led.fills if f.date == day]
        assert all(f.action == "buy" for f in fills if f.date != first_fill)
    assert led.cash_gbp >= 0 and led.fees_paid_gbp > 0


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), 0.0, -5.0])
def test_bad_price_keeps_the_last_good_one(bad):
    L = ledger(A=("GBP",))
    L.deposit(1_000)
    L.mark_to_market({"A": 10.0})
    L.rebalance_to({"A": 0.5}, "d1")
    nav = L.nav()
    L.mark_to_market({"A": bad})
    assert L.last_prices["A"] == 10.0 and L.nav() == pytest.approx(nav)
