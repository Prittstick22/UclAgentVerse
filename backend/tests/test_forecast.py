"""2-week walk-forward forecast (#73): past data only, hand-checked EWMA, labelled estimate, ablation."""
import numpy as np
import pandas as pd
import pytest

from app.config import params
from app.data.gateway import AsOfViolation
from app.engine import forecast, optimiser, risk
from app.profile.quiz import mandate_for


class FakeGW:
    """Minimal gateway stand-in: returns the given prices up to `end`."""

    def __init__(self, px: pd.DataFrame):
        self.px = px

    def prices(self, tickers=None, start=None, end=None, caller=""):
        df = self.px.loc[: pd.Timestamp(end)] if end else self.px
        return df[tickers] if tickers else df


def _px(rets: dict[str, np.ndarray], start="2025-01-01") -> pd.DataFrame:
    n = len(next(iter(rets.values())))
    idx = pd.bdate_range(start, periods=n + 1)
    return pd.DataFrame({t: 100 * np.exp(np.concatenate([[0], np.cumsum(r)])) for t, r in rets.items()}, index=idx)


def test_constant_return_hand_check():
    r = 0.001
    px = _px({"A.LSE": np.full(300, r)})
    f = forecast.forecast(FakeGW(px), ["A.LSE"], str(px.index[-1].date()))
    shrink = params()["forecast"]["shrink"]
    a = f.assets[0]
    assert a.mu_annual == pytest.approx((1 - shrink) * r * risk.TRADING_DAYS, rel=1e-6)
    assert a.sigma_annual == pytest.approx(0.0, abs=1e-9)
    h = f.horizon_days
    expected = np.expm1(h * (1 - shrink) * r)
    assert a.band.p10 == pytest.approx(expected, abs=1e-6) and a.band.p90 == pytest.approx(expected, abs=1e-6)
    assert f.label == "estimate, not a promise"


def test_recent_days_weigh_most():
    calm_then_up = np.concatenate([np.full(250, -0.002), np.full(10, 0.01)])
    px = _px({"A.LSE": calm_then_up})
    f = forecast.forecast(FakeGW(px), ["A.LSE"], str(px.index[-1].date()))
    assert f.mu["A.LSE"] > 0   # a plain mean would be negative; the last 2 weeks dominate


def test_ewma_weights_sum_to_one_and_halve_each_halflife():
    w = forecast.ewma_weights(21, 10)
    assert w.sum() == pytest.approx(1.0) and w[-1] / w[-11] == pytest.approx(2.0)
    with pytest.raises(ValueError):
        forecast.ewma_weights(5, 0)


def test_bands_are_ordered_and_portfolio_band_present():
    rng = np.random.default_rng(1)
    px = _px({"A.LSE": rng.normal(0.0005, 0.01, 300), "B.LSE": rng.normal(0.0, 0.004, 300)})
    day = str(px.index[-1].date())
    f = forecast.forecast(FakeGW(px), ["A.LSE", "B.LSE"], day, weights={"A.LSE": 0.6, "B.LSE": 0.37})
    for a in f.assets:
        assert a.band.p10 < a.band.p50 < a.band.p90
    assert f.portfolio_basis == "given" and f.portfolio.p10 < f.portfolio.p50 < f.portfolio.p90
    eq = forecast.forecast(FakeGW(px), ["A.LSE", "B.LSE"], day)
    assert eq.portfolio_basis == "equal" and eq.portfolio_weights == {"A.LSE": 0.5, "B.LSE": 0.5}


def test_short_history_ticker_is_skipped_not_guessed():
    rng = np.random.default_rng(2)
    px = _px({"A.LSE": rng.normal(0, 0.01, 300), "NEW.LSE": rng.normal(0, 0.01, 300)})
    px.loc[px.index[:-10], "NEW.LSE"] = np.nan    # listed 10 days ago
    f = forecast.forecast(FakeGW(px), ["A.LSE", "NEW.LSE"], str(px.index[-1].date()))
    assert f.skipped == ["NEW.LSE"] and "NEW.LSE" not in f.mu


def test_bad_horizon_rejected():
    px = _px({"A.LSE": np.full(50, 0.001)})
    with pytest.raises(ValueError):
        forecast.forecast(FakeGW(px), ["A.LSE"], str(px.index[-1].date()), horizon=0)


def test_uses_no_data_after_as_of(state):
    tickers = [i.ticker for i in state.gw.catalogue()]
    day = state.clock.as_of_str()
    before = forecast.forecast(state.gw, tickers, day)
    state.clock.set(state.gw.trading_days(day)[30].date())   # 6 weeks later, more data is visible
    again = forecast.forecast(state.gw, tickers, day)
    assert again.model_dump() == before.model_dump()          # same as_of -> same numbers
    later = forecast.forecast(state.gw, tickers, state.clock.as_of_str())
    assert later.mu != before.mu


def test_gateway_refuses_a_future_as_of(state):
    with pytest.raises(AsOfViolation):
        forecast.forecast(state.gw, ["VWRP.LSE"], "2999-01-01")


def test_lambda_zero_ablation_equals_no_forecast(state, monkeypatch):
    import copy

    insts = state.gw.catalogue()
    tickers = [i.ticker for i in insts]
    cov = risk.covariance(risk.log_returns(state.gw.prices(tickers).tail(params()["optimiser"]["lookback"] + 1)))
    m = mandate_for("balanced")
    mu = pd.Series(forecast.forecast(state.gw, tickers, state.clock.as_of_str()).mu)
    base = optimiser.optimise(optimiser.OptimiseRequest(mandate=m, instruments=insts, cov=cov))
    p = copy.deepcopy(params())
    p["forecast"]["lambda_return"] = 0.0
    monkeypatch.setattr(optimiser, "params", lambda: p)
    ablated = optimiser.optimise(optimiser.OptimiseRequest(mandate=m, instruments=insts, cov=cov, mu=mu))
    assert ablated.weights == base.weights


def test_agent_tool_now_returns_the_forecast(state):
    import asyncio

    from app.agents.tools import ToolContext, default_registry

    reg = default_registry(ToolContext(gw=state.gw, events=state.events, state=state))
    out = asyncio.run(reg._tools["forecast"](reg.ctx, {"tickers": ["VWRP.LSE", "VAGS.LSE"]}, None))
    assert out["ok"] and "estimate, not a promise" in out["summary"]
    assert out["forecast"]["mu"] and out["forecast"]["label"] == "estimate, not a promise"


def _opt_inputs(state):
    insts = state.gw.catalogue()
    tickers = [i.ticker for i in insts]
    cov = risk.covariance(risk.log_returns(state.gw.prices(tickers).tail(params()["optimiser"]["lookback"] + 1)))
    mu = pd.Series(forecast.forecast(state.gw, tickers, state.clock.as_of_str()).mu)
    return insts, cov, mu


@pytest.mark.parametrize("profile", ["cautious", "balanced", "growth", "adventurous"])
def test_forecast_only_leans_the_portfolio(state, profile):
    insts, cov, mu = _opt_inputs(state)
    m = mandate_for(profile)
    base = optimiser.optimise(optimiser.OptimiseRequest(mandate=m, instruments=insts, cov=cov))
    for lam in (params()["forecast"]["lambda_return"], 5.0):   # even a huge weight can't rebuild it
        r = optimiser.optimise(optimiser.OptimiseRequest(mandate=m, instruments=insts, cov=cov, mu=mu, lambda_return=lam))
        assert r.status == "optimal"
        keys = set(r.weights) | set(base.weights)
        moves = [abs(r.weights.get(k, 0) - base.weights.get(k, 0)) for k in keys]
        assert max(moves) <= params()["forecast"]["max_tilt_per_holding"] + 1e-4
        assert sum(moves) / 2 <= params()["forecast"]["max_tilt_total"] + 1e-4
        from app.engine import checker
        assert checker.check_proposal(r.weights, r.cash_weight, m, insts).passed


def test_uncapped_huge_weight_would_rebuild_it(state):
    insts, cov, mu = _opt_inputs(state)
    m = mandate_for("balanced")
    base = optimiser.optimise(optimiser.OptimiseRequest(mandate=m, instruments=insts, cov=cov))
    r = optimiser.optimise(optimiser.OptimiseRequest(mandate=m, instruments=insts, cov=cov, mu=mu,
                                                     lambda_return=5.0, tilt_caps=False))
    keys = set(r.weights) | set(base.weights)
    assert sum(abs(r.weights.get(k, 0) - base.weights.get(k, 0)) for k in keys) / 2 > 0.3  # why the caps exist


def test_calibration_uses_development_data_only(state):
    seen: list[str] = []
    real = state.gw.prices

    def spy(tickers=None, start=None, end=None, caller=""):
        if caller.startswith("engine.forecast"):
            seen.append(end)
        return real(tickers, start=start, end=end, caller=caller)

    state.gw.prices = spy
    before = state.clock.as_of_str()
    res = forecast.calibrate_lambda(state, every=120, grid=(0.0, 0.05, 5.0))
    dev_end = params()["periods"]["development"][1]
    assert seen and max(seen) <= dev_end                     # never reads the sim window
    assert state.clock.as_of_str() == before                 # clock restored
    assert res["chosen"] in (0.0, 0.05) and res["median_added_turnover"]["balanced"][0.0] == 0.0
