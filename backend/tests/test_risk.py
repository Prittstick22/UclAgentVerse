"""Risk engine tests (#15): hand-checked tiny datasets + properties on seeded random data. No network."""
import numpy as np
import pandas as pd
import pytest

from app.engine import risk


def _prices(rets: np.ndarray, start: str = "2024-01-01", cols=("A", "B", "C", "D", "E")) -> pd.DataFrame:
    idx = pd.bdate_range(start, periods=len(rets) + 1)
    px = 100 * np.vstack([np.ones(rets.shape[1]), np.exp(np.cumsum(rets, axis=0))])
    return pd.DataFrame(px, index=idx, columns=list(cols)[: rets.shape[1]])


def _rand_prices(n: int = 600, k: int = 5, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return _prices(rng.normal(0.0003, 0.01, size=(n, k)))


# ------------------------------------------------------------------ hand-checked basics
def test_log_returns_hand_checked():
    px = pd.DataFrame({"A": [100.0, 110.0, 121.0]}, index=pd.bdate_range("2026-01-05", periods=3))
    r = risk.log_returns(px)
    assert len(r) == 2
    assert r["A"].tolist() == pytest.approx([np.log(1.1)] * 2)


def test_max_drawdown_hand_checked():
    assert risk.max_drawdown(pd.Series([1.0, 1.2, 0.9, 1.0])) == pytest.approx(0.9 / 1.2 - 1)  # -25%


def test_herfindahl_hand_checked():
    assert risk.herfindahl(pd.Series({"A": 0.5, "B": 0.5})) == pytest.approx(0.5)
    assert risk.herfindahl(pd.Series({"A": 1.0})) == pytest.approx(1.0)
    assert risk.herfindahl(pd.Series({"A": 0.25, "B": 0.25, "C": 0.25, "D": 0.25})) == pytest.approx(0.25)


def test_beta_hand_checked():
    m = pd.Series([0.01, -0.02, 0.03, 0.00])
    assert risk.beta(2 * m, m) == pytest.approx(2.0)
    assert risk.beta(-m, m) == pytest.approx(-1.0)
    assert np.isnan(risk.beta(m, pd.Series([0.01] * 4)))  # benchmark has no variance


# ------------------------------------------------------------------ covariance / correlation properties
def test_covariance_symmetric_and_psd():
    cov = risk.covariance(risk.log_returns(_rand_prices()))
    assert np.allclose(cov.values, cov.values.T)
    assert np.linalg.eigvalsh(cov.values).min() >= -1e-12


def test_covariance_psd_even_with_more_assets_than_days():
    # Ledoit-Wolf shrinkage must keep it PSD where the sample covariance would be singular
    cov = risk.covariance(risk.log_returns(_rand_prices(n=20, k=5)))
    assert np.linalg.eigvalsh(cov.values).min() >= -1e-12


def test_correlation_diagonal_is_one_and_bounded():
    corr = risk.correlation_from_cov(risk.covariance(risk.log_returns(_rand_prices())))
    assert np.allclose(np.diag(corr.values), 1.0)
    assert np.allclose(corr.values, corr.values.T)
    assert corr.values.max() <= 1.0 and corr.values.min() >= -1.0


def test_zero_variance_ticker_gives_no_nan():
    rets = np.random.default_rng(1).normal(0, 0.01, size=(300, 2))
    px = _prices(rets)
    px["FLAT"] = 100.0  # a price that never moves has no defined correlation
    corr = risk.correlation_from_cov(risk.covariance(risk.log_returns(px)))
    assert not np.isnan(corr.values).any()
    assert corr.loc["FLAT", "FLAT"] == 1.0 and corr.loc["FLAT", "A"] == 0.0


# ------------------------------------------------------------------ callout thresholds
def _three_way_prices() -> pd.DataFrame:
    """A; B ~ A (corr ~1); C ~ -A (corr ~-1); D ~ half A + noise (corr ~0.5); E independent."""
    rng = np.random.default_rng(7)
    n = 800
    a = rng.normal(0, 0.01, n)
    b = a + rng.normal(0, 0.001, n)
    c = -a + rng.normal(0, 0.001, n)
    d = 0.5 * a + np.sqrt(0.75) * rng.normal(0, 0.01, n)
    e = rng.normal(0, 0.01, n)
    return _prices(np.column_stack([a, b, c, d, e]))


def test_callout_thresholds():
    px = _three_way_prices()
    rep = risk.correlation_report(px, str(px.index[-1].date()), names={"A": "Alpha", "B": "Beta"})
    ix = {t: i for i, t in enumerate(rep.tickers)}
    got = {frozenset((c.a, c.b)): c for c in rep.callouts}
    # >= 0.8 → "rise and fall together"
    ab = got[frozenset(("A", "B"))]
    assert ab.corr >= risk.CALLOUT_HIGH and "rise and fall together" in ab.text and "Alpha and Beta" in ab.text
    # <= 0.2 → "diversify each other"
    ac = got[frozenset(("A", "C"))]
    assert ac.corr <= risk.CALLOUT_LOW and "diversify each other" in ac.text
    # every callout obeys the thresholds, and every pair in the middle band is left out
    for c in rep.callouts:
        assert c.corr >= risk.CALLOUT_HIGH or c.corr <= risk.CALLOUT_LOW
    ad = rep.matrix[ix["A"]][ix["D"]]
    assert risk.CALLOUT_LOW < ad < risk.CALLOUT_HIGH and frozenset(("A", "D")) not in got
    # sorted by strength, capped at 8
    assert [abs(c.corr) for c in rep.callouts] == sorted((abs(c.corr) for c in rep.callouts), reverse=True)
    assert len(rep.callouts) <= 8


def test_report_matrix_shape_and_avg():
    px = _rand_prices(k=4)
    rep = risk.correlation_report(px, str(px.index[-1].date()))
    n = len(rep.tickers)
    assert n == 4 and len(rep.matrix) == n and all(len(r) == n for r in rep.matrix)
    off = [rep.matrix[i][j] for i in range(n) for j in range(i + 1, n)]
    assert rep.avg_pairwise == pytest.approx(np.mean(off), abs=1e-3)


# ------------------------------------------------------------------ lookback + short history + NaNs
def test_default_lookback_comes_from_params():
    lb, mn = risk.lookbacks()
    assert (lb, mn) == (504, 252)  # frozen in params.yaml
    px = _rand_prices(n=700)
    rep = risk.correlation_report(px, str(px.index[-1].date()))
    assert rep.lookback == 504 and rep.history_days == 504 and not rep.short_history


def test_explicit_lookback_overrides_default():
    px = _rand_prices(n=700)
    rep = risk.correlation_report(px, str(px.index[-1].date()), lookback=300)
    assert rep.lookback == 300 and rep.history_days == 300 and not rep.short_history


def test_short_history_is_used_and_flagged():
    px = _rand_prices(n=100)  # fewer than 252 rows
    rep = risk.correlation_report(px, str(px.index[-1].date()))
    assert rep.short_history and rep.history_days == 100


def test_exactly_min_lookback_is_not_flagged():
    px = _rand_prices(n=252)
    assert not risk.correlation_report(px, str(px.index[-1].date())).short_history


def test_too_little_history_raises_clearly():
    px = _rand_prices(n=1)
    with pytest.raises(ValueError, match="Not enough price history"):
        risk.correlation_report(px, str(px.index[-1].date()))


def test_nan_rows_are_dropped_not_zero_filled():
    px = _rand_prices(n=400, k=3)
    px.iloc[50, 1] = np.nan  # one missing price for B → two missing returns (into and out of the gap)
    r = risk.log_returns(px)
    assert not r.isna().any().any()
    assert len(r) == 400 - 2
    assert (r == 0).sum().sum() == 0  # no fake "calm day"
    rep = risk.correlation_report(px, str(px.index[-1].date()))
    assert not np.isnan(rep.matrix).any() and rep.history_days == 400 - 2


def test_non_positive_price_is_bad_data_not_a_return():
    px = _rand_prices(n=300, k=2)
    px.iloc[10, 0] = 0.0
    r = risk.log_returns(px)
    assert np.isfinite(r.values).all() and len(r) == 300 - 2


def test_late_listed_ticker_shortens_window_and_flags():
    px = _rand_prices(n=400, k=3)
    px.iloc[:300, 2] = np.nan  # C only has ~100 days of prices
    rep = risk.correlation_report(px, str(px.index[-1].date()))
    assert rep.short_history and rep.history_days < 252 and not np.isnan(rep.matrix).any()


@pytest.mark.parametrize("bad", [-5, 0, 1])
def test_bad_lookback_is_rejected(bad):
    px = _rand_prices(n=300)
    with pytest.raises(ValueError):
        risk.correlation_report(px, str(px.index[-1].date()), lookback=bad)  # -5 used to mean "all but 4 rows"


def test_lookback_from_agent_json_is_coerced_or_rejected():
    px = _rand_prices(n=300)
    day = str(px.index[-1].date())
    assert risk.correlation_report(px, day, lookback="120").lookback == 120   # LLM tool args can be strings
    assert risk.correlation_report(px, day, lookback=120.0).lookback == 120
    with pytest.raises(ValueError):
        risk.correlation_report(px, day, lookback="lots")


def test_unsorted_prices_give_same_answer():
    px = _rand_prices(n=300)
    asof = str(px.index[-1].date())
    assert risk.correlation_report(px.iloc[::-1], asof) == risk.correlation_report(px, asof)


# ------------------------------------------------------------------ as_of
def test_report_ignores_data_after_as_of():
    px = _rand_prices(n=600)
    cut = px.index[400]
    past = risk.correlation_report(px, str(cut.date()))
    truncated = risk.correlation_report(px.loc[:cut], str(cut.date()))
    assert past == truncated  # same answer whether or not the future rows are present
    scrambled = px.copy()
    scrambled.loc[scrambled.index > cut] *= 7.0
    assert risk.correlation_report(scrambled, str(cut.date())) == past


# ------------------------------------------------------------------ risk_stats
def _tiny() -> pd.DataFrame:
    # A: 100 → 110 → 99 (+10%, -10%); B never moves; M (benchmark) copies A
    idx = pd.bdate_range("2026-01-05", periods=3)
    return pd.DataFrame({"A": [100.0, 110.0, 99.0], "B": [100.0] * 3, "M": [100.0, 110.0, 99.0]}, index=idx)


def test_risk_stats_hand_checked():
    # 50% A + 50% B. Day 1 +5%, day 2 -5%. NAV 1 → 1.05 → 0.9975, so max drawdown = 0.9975/1.05 - 1 = -5%.
    s = risk.risk_stats({"A": 0.5, "B": 0.5}, _tiny(), benchmark="M")
    assert s.max_drawdown == pytest.approx(-0.05)
    assert s.herfindahl == pytest.approx(0.5)
    assert s.beta == pytest.approx(0.5)  # portfolio return = 0.5 × benchmark return
    assert s.vol > 0 and s.history_days == 2 and s.short_history


def test_risk_stats_cash_is_zero_risk_and_not_in_herfindahl():
    # 50% A, 50% cash: same drawdown/beta as above; weights sum to 0.5 so Herfindahl = 0.25
    s = risk.risk_stats(pd.Series({"A": 0.5}), _tiny(), benchmark="M")
    assert s.max_drawdown == pytest.approx(-0.05)
    assert s.beta == pytest.approx(0.5)
    assert s.herfindahl == pytest.approx(0.25)


def test_risk_stats_vol_matches_portfolio_vol():
    px = _rand_prices(n=600, k=3)
    w = pd.Series({"A": 0.5, "B": 0.3, "C": 0.2})
    s = risk.risk_stats(w, px, benchmark="A")
    rets, _ = risk.prepare_returns(px)
    assert s.vol == pytest.approx(risk.portfolio_vol(w, risk.covariance(rets)))
    assert 0 < s.vol < 1 and s.max_drawdown <= 0 and not s.short_history


def test_risk_stats_beta_none_without_benchmark_and_default_from_params():
    px = _rand_prices(n=300, k=2)
    assert risk.risk_stats({"A": 1.0}, px, benchmark="NOT_THERE").beta is None
    px["VWRP.LSE"] = px["B"]  # default benchmark is params benchmark_global_etf
    assert risk.risk_stats({"A": 1.0}, px).beta is not None


@pytest.mark.parametrize("w", [{"A": float("nan"), "B": 0.5}, {"A": 0.7, "B": 0.7}, {"A": 1.2, "B": -0.2}])
def test_risk_stats_rejects_nan_leveraged_and_short_weights(w):
    with pytest.raises(ValueError):
        risk.risk_stats(w, _rand_prices(k=2))


def test_risk_stats_rejects_bad_input():
    with pytest.raises(ValueError):
        risk.risk_stats({"A": 0.0}, _rand_prices(k=1))
    with pytest.raises(KeyError):
        risk.risk_stats({"ZZZ": 1.0}, _rand_prices(k=1))


# ------------------------------------------------------------------ API: /api/risk/correlation?as_of=
@pytest.fixture()
def client(state):
    from fastapi.testclient import TestClient

    from app.main import app

    app.state.app = state
    return TestClient(app)


def test_api_correlation_works_for_any_past_date(client, state):
    days = [d for d in state.gw.trading_days("2024-01-01") if d.date().isoformat() < state.clock.as_of_str()]
    assert len(days) > 300
    for d in (days[260], days[len(days) // 2], days[-1]):
        body = client.get("/api/risk/correlation", params={"as_of": d.date().isoformat()}).json()
        assert body["as_of"] == d.date().isoformat()
        assert body["history_days"] <= body["lookback"] == 504
        assert len(body["matrix"]) == len(body["tickers"])
    first = state.gw.trading_days("2000-01-01")[100].date().isoformat()  # ~100 days into the snapshot
    early = client.get("/api/risk/correlation", params={"as_of": first}).json()
    assert early["short_history"] is True and early["history_days"] < 252  # used anyway, flagged


def test_api_correlation_past_date_ignores_the_future(client, state):
    day = state.gw.trading_days("2024-01-01")[400].date().isoformat()
    assert day < state.clock.as_of_str()
    a = client.get("/api/risk/correlation", params={"as_of": day, "tickers": "VWRP.LSE,VAGS.LSE"}).json()
    px = state.gw.prices(["VWRP.LSE", "VAGS.LSE"], end=day)
    assert a == risk.correlation_report(px, day).model_dump()


def test_api_correlation_default_is_now_with_504_lookback(client, state):
    body = client.get("/api/risk/correlation").json()
    assert body["as_of"] == state.clock.as_of_str() and body["lookback"] == 504


def test_api_correlation_future_and_bad_dates(client):
    r = client.get("/api/risk/correlation", params={"as_of": "2999-01-01"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "asof_violation"
    for bad in ["not-a-date", "now", "today", "NaT"]:  # "now"/"today" would read the wall clock
        r = client.get("/api/risk/correlation", params={"as_of": bad})
        assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error", bad
    r = client.get("/api/risk/correlation", params={"as_of": "2000-01-03"})  # before any data
    assert r.status_code == 422
    r = client.get("/api/risk/correlation", params={"lookback": -5})
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"
