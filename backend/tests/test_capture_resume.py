"""8 Nov Caroline fixes + continuing a capture from an earlier attempt's saved answers (offline)."""
import json

import numpy as np
import pandas as pd

from app.config import catalogue_raw
from app.engine import checker, optimiser
from app.profile.quiz import mandate_for
from app.schemas import Instrument
from app.sim import compat
from app.sim.capture import is_fatal


def _aggressive():
    m = mandate_for("aggressive")
    insts = [Instrument(**i) for i in catalogue_raw() if i.get("eligible", True)]
    t = [i.ticker for i in insts]
    vols = np.array([0.30 if i.kind == "stock" else 0.15 if i.asset_class == "equity" else 0.06 for i in insts])
    cov = pd.DataFrame(np.diag(vols ** 2) + 0.3 * np.outer(vols, vols) * (1 - np.eye(len(t))), index=t, columns=t)
    return m, insts, cov


def test_fixed_behaviour_is_the_default():
    assert compat.legacy is False


def test_stocks_solve_inside_their_cap_and_above_the_floor():
    m, insts, cov = _aggressive()
    res = optimiser.optimise(optimiser.OptimiseRequest(mandate=m, instruments=insts, cov=cov))
    kinds = {i.ticker: i.kind for i in insts}
    stocks = {t: w for t, w in res.weights.items() if kinds[t] == "stock"}
    assert max(stocks.values()) <= 0.09 + 1e-6                       # 90% of the 10% cap: room for normal moves
    assert sum(round(w, 4) for w in stocks.values()) >= 0.57          # rounding can't drop below the floor
    assert checker.check_proposal(res.weights, res.cash_weight, m, insts).passed


def test_legacy_reproduces_the_old_solution():
    m, insts, cov = _aggressive()
    low = next(i.ticker for i in insts if i.kind == "stock")
    cov.loc[low, :] *= 0.2
    cov.loc[:, low] *= 0.2                                            # one very calm stock: the optimiser packs it
    compat.legacy = True
    try:
        old = optimiser.optimise(optimiser.OptimiseRequest(mandate=m, instruments=insts, cov=cov))
    finally:
        compat.legacy = False
    kinds = {i.ticker: i.kind for i in insts}
    assert max(w for t, w in old.weights.items() if kinds[t] == "stock") > 0.09   # packs to the real cap, as before


def test_case_ids_resolve_to_the_latest_case_version(state):
    state.db.put("cases", "AAPL.US", json.dumps({"ticker": "AAPL.US", "version": 3}))
    sup = state.supervisor
    run = type("R", (), {"evidence_map": {}})()
    assert sup._real_ids(run, ["case_AAPL.US", "case_NONE.US", "news_1"]) == ["case:AAPL.US:v3", "case_NONE.US", "news_1"]
    compat.legacy = True
    try:
        assert sup._real_ids(run, ["case_AAPL.US"]) == ["case_AAPL.US"]
    finally:
        compat.legacy = False


def test_only_provider_failures_stop_a_recording():
    failed = {"type": "agent.status", "status": "failed"}
    assert is_fatal({**failed, "payload": {"reason": "LLMError: quota exhausted on all keys"}}, agents=True)
    assert not is_fatal({**failed, "payload": {"reason": "reply did not match the schema after 2 attempts"}}, agents=True)
    assert not is_fatal({"type": "budget.exceeded", "title": "Run hit its token budget"}, agents=True)
    assert not is_fatal({"type": "run.completed", "status": "ok", "payload": {"budget_exceeded": True}}, agents=True)
    assert is_fatal({"type": "run.completed", "status": "failed", "payload": {}}, agents=True)
    assert is_fatal({"type": "decision.made", "title": "Initial portfolio built by the engine"}, agents=True)


def test_monthly_review_fallback_keeps_earlier_reviews(state):
    from app.sim.runner import Simulation
    sim = Simulation(state, "2026-07-07", "2026-11-06")
    before = [i for i in range(len(sim.days)) if sim._review_cadence(i)[0]]
    sim.set_review_every_from(str(sim.days[25].date()), 20)
    after = [i for i in range(len(sim.days)) if sim._review_cadence(i)[0]]
    assert before[:3] == after[:3] == [0, 10, 20]
    assert after[3:5] == [40, 60]
