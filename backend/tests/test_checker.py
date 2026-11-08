"""Checker (#17), a judged control: one test per violation code, recomputed numbers, and revalidation."""
import numpy as np
import pytest

from app.engine import checker
from app.profile.quiz import mandate_for
from app.schemas import Instrument


def inst(ticker, asset_class="equity", kind="etf", currency="GBP", unit="GBP", ocf=0.002, sleeve="core", eligible=True):
    return Instrument(ticker=ticker, name=ticker, asset_class=asset_class, sleeve=sleeve, currency=currency,
                      quote_unit=unit, ocf=ocf, accumulating=True, kind=kind, eligible=eligible)


CAT = [inst("EQ1"), inst("EQ2"), inst("BD1", "bond", ocf=0.001), inst("BD2", "bond", ocf=0.001),
       inst("GOLD", "commodity"), inst("STK1", kind="stock", currency="USD", unit="USD", ocf=0.0),
       inst("STK2", kind="stock", currency="USD", unit="USD", ocf=0.0), inst("STK3", kind="stock", ocf=0.0),
       inst("STK4", kind="stock", ocf=0.0), inst("STK5", kind="stock", ocf=0.0),
       inst("OLD", eligible=False), inst("ESG", sleeve="tobacco"),
       inst("ODD", currency="USD", unit="GBX")]
GROWTH = mandate_for("growth")   # equity 60–80%, bond 15–35%, cash ≥ 2%, per fund 60%, per stock 4%, stocks ≤ 15%
OK = {"EQ1": 0.40, "EQ2": 0.30, "BD1": 0.25}


def codes(weights, cash, mandate=GROWTH, **kw):
    rep = checker.check_proposal(weights, cash, mandate, CAT, **kw)
    return {v.code for v in rep.violations}, rep


def test_valid_portfolio_passes_with_recomputed_numbers():
    found, rep = codes(OK, 0.05, current_weights={"EQ1": 0.5}, nav_gbp=10_000)
    assert not found and rep.passed
    r = rep.recomputed
    assert r["equity"] == pytest.approx(0.70) and r["bond"] == pytest.approx(0.25) and r["sum"] == pytest.approx(1.0)
    assert r["ocf_weighted"] == pytest.approx(0.4 * 0.002 + 0.3 * 0.002 + 0.25 * 0.001)
    assert r["fees_gbp_per_year"] == pytest.approx(16.5)
    assert r["turnover"] == pytest.approx((0.1 + 0.3 + 0.25) / 2)       # |0.4-0.5| + 0.3 + 0.25, one-way
    assert r["cost_gbp"] == pytest.approx(0.65 * 10_000 * 0.001)


@pytest.mark.parametrize("weights,cash,code", [
    ({"EQ1": 0.40, "EQ2": 0.30, "BD1": 0.25}, 0.10, "sum"),                     # 105%
    ({"EQ1": 0.42, "EQ2": 0.30, "BD1": 0.27}, 0.01, "cash_min"),
    ({**OK, "EQ1": 0.35, "OLD": 0.05}, 0.05, "ineligible"),
    ({**OK, "EQ1": 0.35, "NOPE": 0.05}, 0.05, "ineligible"),                    # not in the catalogue at all
    ({**OK, "EQ1": 0.35, "ODD": 0.05}, 0.05, "units"),
    ({"EQ1": 0.45, "EQ2": 0.30, "BD1": 0.25, "BD2": -0.05}, 0.05, "short"),
    ({**OK, "EQ1": 0.35, "ESG": 0.05}, 0.05, "excluded"),                       # excluded by sleeve
    ({"EQ1": 0.65, "EQ2": 0.05, "BD1": 0.25}, 0.05, "concentration"),           # fund over 60%
    ({"EQ1": 0.36, "EQ2": 0.30, "BD1": 0.25, "STK1": 0.04}, 0.05, None),        # stock at its 4% cap: fine
    ({"EQ1": 0.35, "EQ2": 0.30, "BD1": 0.25, "STK1": 0.05}, 0.05, "concentration"),   # stock over 4%
    ({"EQ1": 0.40, "EQ2": 0.10, "BD1": 0.30, "BD2": 0.15}, 0.05, "equity_range"),
    ({"EQ1": 0.50, "EQ2": 0.30, "BD1": 0.10, "GOLD": 0.05}, 0.05, "bond_range"),
    ({"EQ1": 0.25, "EQ2": 0.25, "BD1": 0.25, **{f"STK{i}": 0.04 for i in range(1, 5)}}, 0.09, "stocks_total"),
])
def test_each_violation_code(weights, cash, code):
    excl = mandate_for("growth", exclusions=["tobacco"])
    found, rep = codes(weights, cash, excl)
    if code is None:
        assert rep.passed, rep.violations
    else:
        assert code in found, rep.violations
        v = next(x for x in rep.violations if x.code == code)
        assert v.message                                   # plain-English reason for the UI


def test_stocks_total_is_its_own_code():
    w = {"EQ1": 0.30, "EQ2": 0.24, "BD1": 0.25, **{f"STK{i}": 0.04 for i in range(1, 5)}}   # 16% in stocks
    found, _ = codes(w, 0.05)
    assert "stocks_total" in found and "concentration" not in found


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), "0.4", None])
def test_not_a_number_is_caught_not_silently_passed(bad):
    found, rep = codes({**OK, "EQ1": bad}, 0.05)
    assert found == {"not_a_number"} and not rep.passed
    found, _ = codes(OK, float("nan"))
    assert found == {"not_a_number"}


def test_numpy_numbers_are_fine():
    _found, rep = codes({k: np.float64(v) for k, v in OK.items()}, np.float32(0.05))
    assert rep.passed, rep.violations


def test_mandate_blocks_concentration_on_the_real_catalogue(state):
    rep = checker.check_proposal({"NVDA.US": 0.25, "VWRP.LSE": 0.48, "VAGS.LSE": 0.25}, 0.02, GROWTH,
                                 state.gw.catalogue())
    assert not rep.passed and any(v.code == "concentration" and v.ticker == "NVDA.US" for v in rep.violations)


# ------------------------------------------------------------------ revalidation (pre-execution)
def _reval(**kw):
    base = {"proposal_as_of": "2026-09-01", "price_dates": {"EQ1": "2026-09-01"}, "today": "2026-09-01",
                "mandate_version_at_proposal": 1, "mandate_version_now": 1, "holdings_hash_at_proposal": "a",
                "holdings_hash_now": "a", "pending_order_keys": set(), "order_key": "proposal:p1"}
    return {v.code for v in checker.revalidate(**{**base, **kw}).violations}


def test_revalidate_passes_when_nothing_changed():
    assert _reval() == set()
    assert _reval(today="2026-09-04") == set()                     # 3 trading days: still fresh


@pytest.mark.parametrize("change,code", [
    ({"today": "2026-09-07", "proposal_as_of": "2026-09-07"}, "stale_data"),   # price 4 trading days old
    ({"today": "2026-09-07", "price_dates": {"EQ1": "2026-09-07"}}, "stale_data"),   # proposal 4 days old
    ({"mandate_version_now": 2}, "mandate_changed"),
    ({"holdings_hash_now": "b"}, "holdings_changed"),
    ({"pending_order_keys": {"proposal:p1"}}, "duplicate_order"),
])
def test_revalidate_codes(change, code):
    assert code in _reval(**change)


def test_zero_weight_lines_are_not_violations():
    excl = mandate_for("growth", exclusions=["tobacco"])
    _found, rep = codes({**OK, "ESG": 0.0, "OLD": 0.0, "ODD": 0, "NOPE": 0.0}, 0.05, excl)
    assert rep.passed, rep.violations


def test_true_is_not_a_100_percent_weight():
    found, _ = codes({"EQ1": True}, 0.0)
    assert found == {"not_a_number"}
