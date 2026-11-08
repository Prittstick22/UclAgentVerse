"""The historical demo persona must score exactly to the profile the recorded 4-month run uses."""
from app.config import demo_persona, params
from app.profile.quiz import QUESTIONS, mandate_for, score
from app.schemas import Goal


def test_persona_answers_score_to_its_profile_without_conflict():
    p = demo_persona()
    r = score(p["answers"])
    assert r.name == p["profile"] == "balanced"
    assert not r.conflict and r.follow_up_question is None
    assert 0.35 < min(r.tolerance_score, r.capacity_score) < 0.50   # well inside the balanced band (0.30-0.55)


def test_persona_answers_every_question_with_a_valid_option():
    answers = demo_persona()["answers"]
    for q in QUESTIONS:
        assert answers[q["id"]] in {oid for oid, _, _ in q["options"]}, q["id"]


def test_persona_money_matches_the_sim_and_is_labelled_fictional():
    p = demo_persona()
    assert p["synthetic"] is True
    assert p["goal"]["starting_amount_gbp"] == params()["sim"]["capital_gbp"]
    assert p["goal"]["monthly_contribution_gbp"] == params()["sim"]["monthly_contribution_gbp"]
    m = mandate_for(p["profile"], goal=Goal(**p["goal"]), exclusions=p["exclusions"])
    assert m.profile == "balanced" and m.caps.stocks_total > 0       # stocks allowed -> stock analyst runs


# ---------------------------------------------------------------- Caroline: higher-risk scenario (aggressive profile)
def test_caroline_scores_to_the_quiz_top_band_and_uses_the_aggressive_policy():
    p = demo_persona("caroline")
    r = score(p["answers"])
    assert r.name == "adventurous" and not r.conflict          # the quiz's highest band; aggressive is beyond it
    assert p["profile"] == "aggressive" and p["synthetic"] is True
    assert p["goal"]["starting_amount_gbp"] == params()["sim"]["capital_gbp"]
    assert p["goal"]["monthly_contribution_gbp"] == params()["sim"]["monthly_contribution_gbp"]
    for q in QUESTIONS:
        assert p["answers"][q["id"]] in {oid for oid, _, _ in q["options"]}, q["id"]


def test_priya_is_unchanged_by_the_second_persona():
    assert demo_persona() == demo_persona("priya") and demo_persona()["profile"] == "balanced"
    assert mandate_for("balanced").caps.stocks_min == 0.0


def test_aggressive_portfolio_is_about_60_stocks_40_etfs_no_bonds():
    import numpy as np
    import pandas as pd
    from app.config import catalogue_raw
    from app.engine import checker, optimiser
    from app.schemas import Instrument

    m = mandate_for("aggressive", goal=Goal(**demo_persona("caroline")["goal"]))
    insts = [Instrument(**i) for i in catalogue_raw() if i.get("eligible", True)]
    tickers = [i.ticker for i in insts]
    vols = np.array([0.30 if i.kind == "stock" else 0.15 if i.asset_class == "equity" else 0.06 for i in insts])
    cov = pd.DataFrame(np.diag(vols ** 2) + 0.3 * np.outer(vols, vols) * (1 - np.eye(len(insts))),
                       index=tickers, columns=tickers)
    res = optimiser.optimise(optimiser.OptimiseRequest(mandate=m, instruments=insts, cov=cov))
    assert res.status == "optimal", res.binding_constraints
    by = {i.ticker: i for i in insts}
    stocks = sum(w for t, w in res.weights.items() if by[t].kind == "stock")
    etfs = sum(w for t, w in res.weights.items() if by[t].kind != "stock")
    bonds = sum(w for t, w in res.weights.items() if by[t].asset_class == "bond")
    assert 0.57 - 1e-6 <= stocks <= 0.60 + 1e-6 and 0.35 <= etfs <= 0.41 and bonds < 1e-6
    assert max(w for t, w in res.weights.items() if by[t].kind == "stock") <= 0.10 + 1e-6
    assert checker.check_proposal(res.weights, res.cash_weight, m, insts).passed
    low = {t: w for t, w in res.weights.items() if by[t].kind != "stock"}
    rep = checker.check_proposal(low, 1 - sum(low.values()), m, insts)
    assert "stocks_min" in {v.code for v in rep.violations}
