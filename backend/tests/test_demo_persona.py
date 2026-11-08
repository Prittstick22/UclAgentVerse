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
