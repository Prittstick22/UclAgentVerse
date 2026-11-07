"""Risk quiz → profile → mandate. Deterministic scoring (code scores; Argon only explains). Owner: Jin.

Prototype policy, NOT a suitability assessment. Questions phrased in £ where possible.
"""
from __future__ import annotations

from pydantic import BaseModel

from app.config import params, policy
from app.schemas import Approval, Caps, Goal, Mandate, ProfileName, Ranges, Triggers

QUESTIONS = [
    {"id": "horizon", "measures": "capacity", "text": "When might you need this money?",
     "help": "Money you need soon can't ride out a fall.",
     "options": [("lt3", "Within 3 years", 0), ("3to7", "In 3–7 years", 2), ("7to15", "In 7–15 years", 3), ("gt15", "More than 15 years away", 4)]},
    {"id": "emergency", "measures": "capacity", "text": "Do you have 3+ months of spending saved separately for emergencies?",
     "help": "If not, you may be forced to sell at a bad time.",
     "options": [("no", "No", 0), ("some", "About 1–2 months", 2), ("yes", "Yes, 3 months or more", 4)]},
    {"id": "loss_goal", "measures": "capacity", "text": "If £10,000 fell to £8,000 for a year, would that stop you reaching your goal?",
     "help": "This is about your situation, not your feelings.",
     "options": [("yes", "Yes, it would", 0), ("maybe", "It would set me back", 2), ("no", "No, I could wait", 4)]},
    {"id": "income", "measures": "capacity", "text": "How steady is your income?",
     "help": "", "options": [("unsteady", "Unsteady / none", 0), ("ok", "Fairly steady", 2), ("steady", "Very steady", 4)]},
    {"id": "reaction", "measures": "tolerance", "text": "Your £10,000 drops to £8,000 in a month. What do you do?",
     "help": "", "options": [("sell", "Sell everything", 0), ("some", "Sell some", 1), ("hold", "Wait it out", 3), ("buy", "Invest more", 4)]},
    {"id": "swings", "measures": "tolerance", "text": "Which yearly range would you accept on £10,000?",
     "help": "Higher possible gains come with bigger possible falls.",
     "options": [("narrow", "£9,500 to £10,700", 0), ("mid", "£9,000 to £11,200", 2), ("wide", "£8,000 to £12,500", 3), ("widest", "£7,000 to £13,500", 4)]},
    {"id": "experience", "measures": "context", "text": "Have you invested before?",
     "help": "", "options": [("never", "Never", 0), ("little", "A little (ISA, pension app)", 1), ("yes", "Yes, regularly", 2)]},
    {"id": "worry", "measures": "tolerance", "text": "How often would you check your portfolio when markets fall?",
     "help": "", "options": [("daily", "Daily and I'd worry", 0), ("weekly", "Weekly", 2), ("rarely", "Rarely", 4)]},
]

BANDS: list[tuple[float, ProfileName]] = [(0.30, "cautious"), (0.55, "balanced"), (0.80, "growth"), (1.01, "adventurous")]


class ProfileResult(BaseModel):
    name: ProfileName
    tolerance_score: float
    capacity_score: float
    conflict: bool
    follow_up_question: str | None
    explanation: str


def questions_payload() -> list[dict]:
    return [{"id": q["id"], "text": q["text"], "help": q["help"], "measures": q["measures"],
             "options": [{"id": oid, "label": label} for oid, label, _ in q["options"]]} for q in QUESTIONS]


def _score(answers: dict[str, str], measures: str) -> float:
    got = maximum = 0.0
    for q in QUESTIONS:
        if q["measures"] != measures:
            continue
        pts = {oid: p for oid, _, p in q["options"]}
        maximum += max(pts.values())
        got += pts.get(answers.get(q["id"], ""), 0)
    return got / maximum if maximum else 0.0


def _band(score: float) -> ProfileName:
    for upper, name in BANDS:
        if score < upper:
            return name
    return "adventurous"


def score(answers: dict[str, str]) -> ProfileResult:
    tol, cap = _score(answers, "tolerance"), _score(answers, "capacity")
    name = _band(min(tol, cap))
    conflict = abs(tol - cap) >= 0.35
    follow_up = None
    if conflict and tol > cap:
        follow_up = "You're comfortable with swings, but your situation suggests a fall could hurt your goal. Could you leave this money untouched for at least 7 years?"
    elif conflict:
        follow_up = "Your situation could absorb a fall, but you said falls would worry you. Would a smaller, steadier portfolio feel better even if it may grow more slowly?"
    explanation = (f"We used the lower of your comfort with risk ({tol:.0%}) and your ability to absorb a loss ({cap:.0%}), "
                   f"so your profile is {name}. This is a prototype policy, not a suitability assessment.")
    return ProfileResult(name=name, tolerance_score=round(tol, 3), capacity_score=round(cap, 3), conflict=conflict,
                         follow_up_question=follow_up, explanation=explanation)


def mandate_for(profile: ProfileName, goal: Goal | None = None, exclusions: list[str] | None = None) -> Mandate:
    p = policy()[profile]
    prm = params()
    return Mandate(
        profile=profile,
        goal=goal or Goal(starting_amount_gbp=prm["sim"]["capital_gbp"],
                          monthly_contribution_gbp=prm["sim"]["monthly_contribution_gbp"]),
        ranges=Ranges(equity=tuple(p["equity"]), bond=tuple(p["bond"]), cash_min=p["cash_min"]),
        caps=Caps(per_fund=p["per_fund"], per_stock=p["per_stock"], stocks_total=p["stocks_total"]),
        exclusions=exclusions or [],
        review_every_n_days=prm["review_every_n_days"],
        triggers=Triggers(**{k: prm["triggers"][k] for k in Triggers.model_fields}),
        approval=Approval(batch_auto_approve_turnover_max=prm["batch_auto_approve_turnover_max"]),
    )
