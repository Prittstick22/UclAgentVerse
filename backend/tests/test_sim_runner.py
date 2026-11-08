"""Simulator day loop (#19): deterministic, engine-only baseline, triggers + cooldowns, events."""
import asyncio
import itertools
import time

import pytest

from app.config import params
from app.sim import runner

START = params()["sim"]["start"]


def _run(state, **kw):
    return asyncio.run(runner.run(state, START, **kw))


def test_full_window_runs_fast_and_is_engine_only(state):
    t = time.perf_counter()
    r = _run(state)
    assert time.perf_counter() - t < 60
    assert r.days > 60 and r.start == START
    assert r.trigger_counts["review"] == (r.days - 1) // state.mandate.review_every_n_days
    assert r.runs[0]["kind"] == "construction"
    assert set(r.benchmarks) == {"buy_and_hold", "quarterly_rebalance", "global_etf", "mechanical_5pct"}


def test_rerun_is_identical(snapshot_dir, state):
    from app.container import build_state
    from app.settings import Settings

    a = _run(state)
    b = _run(build_state(Settings(snapshot_dir=snapshot_dir, llm_mode="fake", app_mode="historical"),
                         db_path=":memory:"))
    assert a.nav_series == b.nav_series and a.runs == b.runs and a.benchmarks == b.benchmarks
    assert a.trigger_counts == b.trigger_counts and a.fills == b.fills


def test_decide_today_fill_tomorrow_and_contributions(state):
    r = _run(state)
    first_fill = min(f.date for f in state.ledger.fills)
    assert first_fill == r.nav_series[1][0]   # built on day 0, filled at day 1's close
    months = len({d[:7] for d, _ in r.nav_series}) - 1
    expected = params()["sim"]["capital_gbp"] + months * params()["sim"]["monthly_contribution_gbp"]
    assert r.contributions_gbp == expected
    assert state.ledger.fees_paid_gbp > 0
    assert state.ledger.cash_gbp >= 0


def test_events_tick_every_day(state):
    r = _run(state)
    evs = state.events.history(limit=100000)
    ticks = [e for e in evs if e.type == "clock.tick"]
    assert len(ticks) == r.days
    assert {"nav_gbp", "weights", "benchmarks", "status"} <= set(ticks[-1].payload)
    assert sum(e.type == "decision.made" for e in evs) == len(r.runs)


def test_price_shock_triggers_one_run_then_cooldown(state, monkeypatch):
    shock_day = state.gw.trading_days(START)[23]   # not a review day (reviews every 10) or within 2 of one
    real = state.gw.latest_prices

    def shocked(tickers=None):
        s = real(tickers).copy()
        if state.clock.now().date() >= shock_day.date():
            s.loc[s.index.str.endswith(".LSE")] *= 0.90   # every UK line falls 10% and stays down
        return s

    monkeypatch.setattr(state.gw, "latest_prices", shocked)
    r = _run(state)
    shock = [x for x in r.runs if x["date"] == str(shock_day.date())]
    assert shock and shock[0]["kind"] in ("price_move", "nav_drop")   # grouped into ONE portfolio run
    assert r.trigger_counts["price_move"] >= 1
    fired = [e for e in state.events.history(limit=100000) if e.type == "monitor.fired"]
    assert fired and all(e.payload["rule"] in ("price_move", "nav_drop", "drift", "cap_breach") for e in fired)
    # cooldown: the same holding can't start another run within cooldown_days
    by_ticker: dict[str, list[int]] = {}
    days = [d for d, _ in r.nav_series]
    for e in fired:
        if e.payload["ticker"]:
            by_ticker.setdefault(e.payload["ticker"], []).append(days.index(e.as_of[:10]))
    for idx in by_ticker.values():
        assert all(b - a >= params()["cooldown_days"] for a, b in itertools.pairwise(idx))


def test_no_trading_days_is_a_clear_error(state):
    with pytest.raises(ValueError):
        asyncio.run(runner.run(state, "2030-01-01", "2030-02-01"))


def test_agents_mode_two_weeks_in_fake_mode(state):
    end = str(state.gw.trading_days(START)[10].date())
    r = asyncio.run(runner.run(state, START, end, agents=True))
    assert r.days == 11
    assert any(e.type == "run.started" for e in state.events.history(limit=100000))


def _shock(state, monkeypatch, day, factor, uk_only=True):
    real = state.gw.latest_prices

    def shocked(tickers=None):
        s = real(tickers).copy()
        if state.clock.now().date() >= day.date():
            mask = s.index.str.endswith(".LSE") if uk_only else s.index == s.index
            s.loc[mask] *= factor
        return s

    monkeypatch.setattr(state.gw, "latest_prices", shocked)


def test_triggers_on_a_review_day_are_kept_in_the_review(state, monkeypatch):
    day = state.gw.trading_days(START)[30]   # a review day
    _shock(state, monkeypatch, day, 0.90)
    r = _run(state)
    review = next(x for x in r.runs if x["date"] == str(day.date()))
    assert review["kind"] == "review" and "fell" in review["text"]   # used to say only "Scheduled review"


def test_contribution_does_not_hide_a_nav_drop(state, monkeypatch):
    days = state.gw.trading_days(START)
    n = state.mandate.review_every_n_days
    i = next(k for k in range(1, len(days)) if days[k].month != days[k - 1].month and 1 <= k % n <= n - 3)
    _shock(state, monkeypatch, days[i], 0.94, uk_only=False)   # ~5.8% NAV fall on a £200 contribution day
    r = _run(state)
    assert next(x for x in r.runs if x["date"] == str(days[i].date()))["kind"] == "nav_drop"


def test_benchmarks_get_each_contribution_once(state):
    days = state.gw.trading_days(START)
    last_july = [d for d in days if d.month == 7][-1]   # first invested day is 1 Aug (a contribution day)
    r = asyncio.run(runner.run(state, str(last_july.date()), str(days[-1].date())))
    for nav in r.benchmarks.values():
        assert abs(nav / r.final_nav - 1) < 0.10   # used to start £200 ahead of us
    assert r.contributions_gbp == params()["sim"]["capital_gbp"] + 200 * (len({d[:7] for d, _ in r.nav_series}) - 1)


def test_failed_optimiser_on_review_holds_instead_of_crashing(state, monkeypatch):
    calls = {"n": 0}
    real = runner.build_targets

    def flaky(st, current=None):
        calls["n"] += 1
        if calls["n"] > 1:
            raise RuntimeError("infeasible")
        return real(st, current)

    monkeypatch.setattr(runner, "build_targets", flaky)
    r = _run(state)
    assert all(x["action"] == "maintain" for x in r.runs[1:]) and len(r.nav_series) == r.days


def test_run_refuses_a_ledger_that_already_has_money(state):
    end = str(state.gw.trading_days(START)[5].date())
    asyncio.run(runner.run(state, START, end))
    with pytest.raises(ValueError, match="fresh ledger"):
        asyncio.run(runner.run(state, START, end))   # used to deposit the capital a second time
