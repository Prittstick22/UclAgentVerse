"""Fixed fictional persona shared by historical state and the public demo endpoint."""

from app.config import demo_persona
from app.profile.quiz import mandate_for, score
from app.schemas import DemoProfile, Goal, Mandate


def demo_mandate(name: str = "priya") -> Mandate:
    persona = demo_persona(name)
    return mandate_for(persona["profile"], Goal(**persona["goal"]), persona.get("exclusions", []))


def demo_profile(name: str = "priya") -> DemoProfile:
    persona = demo_persona(name)
    return DemoProfile(
        **{key: persona[key] for key in ("name", "age", "story", "profile", "goal", "answers", "synthetic")},
        result=score(persona["answers"]),
        mandate=demo_mandate(name),
    )
