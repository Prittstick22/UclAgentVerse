"""Optimiser (#16): every profile × variant is optimal and passes the independent checker."""
import copy
import time

import numpy as np
import pandas as pd
import pytest

from app.config import params
from app.engine import checker, optimiser, risk
from app.profile.quiz import mandate_for

PROFILES = ["cautious", "balanced", "growth", "adventurous"]


@pytest.fixture()
def universe(state):
    insts = state.gw.catalogue()
    px = state.gw.prices([i.ticker for i in insts])
    cov = risk.covariance(risk.log_returns(px.tail(params()["optimiser"]["lookback"] + 1)))
    return insts, cov


def _run(m, insts, cov, **kw):
    return optimiser.optimise(optimiser.OptimiseRequest(mandate=m, instruments=insts, cov=cov, **kw))


def _with_params(monkeypatch, **forecast):
    p = copy.deepcopy(params())
    p.setdefault("forecast", {}).update(forecast)
    monkeypatch.setattr(optimiser, "params", lambda: p)


@pytest.mark.parametrize("profile", PROFILES)
@pytest.mark.parametrize("variant", optimiser.VARIANTS)
def test_every_profile_and_variant_is_optimal_and_checker_passes(universe, profile, variant):
    insts, cov = universe
    m = mandate_for(profile)
    res = _run(m, insts, cov, variant=variant)
    assert res.status == "optimal", res.binding_constraints
    rep = checker.check_proposal(res.weights, res.cash_weight, m, insts)
    assert rep.passed, [v.message for v in rep.violations]   # lower_risk used to land at 59.998% equity
    assert abs(sum(res.weights.values()) + res.cash_weight - 1) < 1e-9
    assert all(w >= optimiser.MIN_WEIGHT for w in res.weights.values())  # no dust holdings


@pytest.mark.parametrize("profile", PROFILES)
def test_variants_are_meaningfully_different(universe, profile):
    insts, cov = universe
    m = mandate_for(profile)
    rec, cheap, safe = (_run(m, insts, cov, variant=v) for v in optimiser.VARIANTS)
    assert safe.vol_annual <= rec.vol_annual + 1e-9
    assert cheap.ocf_weighted <= rec.ocf_weighted + 1e-9
    assert rec.weights != cheap.weights and rec.weights != safe.weights


def test_runs_under_one_second_for_20_instruments(universe):
    insts, _ = universe
    rng = np.random.default_rng(0)
    extra = [i.model_copy(update={"ticker": f"X{k}.LSE", "ocf": 0.001 + 0.001 * k}) for k, i in
             enumerate([i for i in insts if i.kind == "etf"][: 20 - len(insts)])]
    insts20 = insts + extra
    assert len(insts20) == 20
    a = rng.normal(size=(20, 20)) * 0.02
    cov20 = pd.DataFrame(a @ a.T + np.eye(20) * 0.01, index=[i.ticker for i in insts20],
                         columns=[i.ticker for i in insts20])
    t = time.perf_counter()
    res = _run(mandate_for("growth"), insts20, cov20)
    assert res.status == "optimal" and time.perf_counter() - t < 1.0


def test_infeasible_mandate_gives_readable_reasons(universe):
    insts, cov = universe
    bonds_only = [i for i in insts if i.asset_class == "bond"]
    res = _run(mandate_for("growth"), bonds_only, cov)
    assert res.status == "infeasible"
    assert res.binding_constraints == [("The growth profile needs at least 60% in shares, "
                                        "but none of the candidates hold shares. Add a fund that holds shares.")]


def test_infeasible_counts_the_stocks_total_cap(universe):
    insts, cov = universe
    stocks_and_bonds = [i for i in insts if i.kind == "stock" or i.asset_class == "bond"]
    res = _run(mandate_for("growth"), stocks_and_bonds, cov)
    assert res.status == "infeasible"
    assert "at most 15%" in res.binding_constraints[0]  # stocks_total, not the sum of per-stock caps


def test_exclusions_are_respected(universe):
    insts, cov = universe
    m = mandate_for("growth", exclusions=["VWRP.LSE"])
    res = _run(m, insts, cov)
    assert res.status == "optimal" and "VWRP.LSE" not in res.weights


def test_missing_risk_data_is_an_error_not_zero_risk(universe):
    insts, cov = universe
    res = _run(mandate_for("growth"), insts, cov.drop(index="VWRP.LSE", columns="VWRP.LSE"))
    assert res.status == "error" and "VWRP.LSE" in res.binding_constraints[0]
    nan_cov = cov.copy()
    nan_cov.loc["VWRP.LSE", "VAGS.LSE"] = np.nan
    assert _run(mandate_for("growth"), insts, nan_cov).status == "error"


def test_turnover_penalty_keeps_close_to_current_holdings(universe):
    insts, cov = universe
    m = mandate_for("growth")
    held = _run(m, insts, cov).weights
    fresh = _run(m, insts, cov * 1.05)
    sticky = _run(m, insts, cov * 1.05, current_weights=held)
    assert sticky.turnover <= 0.01 and sticky.turnover <= fresh.turnover + 1e-9


def test_no_forecast_and_lambda_zero_are_identical(universe, monkeypatch):
    insts, cov = universe
    m = mandate_for("growth")
    mu = pd.Series({i.ticker: (0.5 if i.ticker == "VWRP.LSE" else 0.0) for i in insts})
    base = _run(m, insts, cov)
    _with_params(monkeypatch, lambda_return=0.0)
    assert _run(m, insts, cov, mu=mu).weights == base.weights   # ablation: λ_return = 0 → no forecast


def test_forecast_tilts_towards_higher_expected_return(universe, monkeypatch):
    insts, cov = universe
    m = mandate_for("balanced")
    _with_params(monkeypatch, lambda_return=1.0)
    base = _run(m, insts, cov)
    target = min((t for t in base.weights if t != "VWRP.LSE"), key=lambda t: base.weights[t])
    tilted = _run(m, insts, cov, mu=pd.Series({target: 0.2}))
    assert tilted.weights.get(target, 0) > base.weights[target]
    assert checker.check_proposal(tilted.weights, tilted.cash_weight, m, insts).passed  # never loosens the mandate


def test_limits_that_only_just_fit_are_still_feasible(universe):
    insts, cov = universe
    m = mandate_for("growth")  # equity min 60% = exactly one fund at its 60% cap
    one_equity_fund = [i for i in insts if i.ticker == "VWRP.LSE" or i.asset_class == "bond"]
    res = _run(m, one_equity_fund, cov)
    assert res.status == "optimal", res.binding_constraints
    assert checker.check_proposal(res.weights, res.cash_weight, m, insts).passed


def test_infinite_forecast_is_an_error_not_a_crash(universe, monkeypatch):
    insts, cov = universe
    _with_params(monkeypatch, lambda_return=1.0)
    res = _run(mandate_for("growth"), insts, cov, mu=pd.Series({"VWRP.LSE": np.inf}))
    assert res.status == "error"


def test_binding_list_only_names_mandate_limits(universe):
    insts, cov = universe
    for p in PROFILES:
        res = _run(mandate_for(p), insts, cov, variant="lower_risk")
        assert not {"sum_to_one", "min_holding"} & set(res.binding_constraints)
