"""Deterministic trigger rules. Owner: Cem. Spec: docs/03-how-it-works.md §4."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.schemas import Instrument, Mandate

HitKind = Literal["drift", "cap_breach", "price_move", "nav_drop", "news", "corr_regime"]


class Hit(BaseModel):
    kind: HitKind
    ticker: str | None
    value: float
    threshold: float
    text: str


def drift_hits(weights: dict[str, float], targets: dict[str, float], catalogue: dict[str, Instrument],
               threshold: float) -> list[Hit]:
    hits: list[Hit] = []
    by_class: dict[str, list[float]] = {}
    for t in set(weights) | set(targets):
        ac = catalogue[t].asset_class if t in catalogue else "cash"
        cur, tgt = weights.get(t, 0.0), targets.get(t, 0.0)
        by_class.setdefault(ac, [0.0, 0.0])
        by_class[ac][0] += cur
        by_class[ac][1] += tgt
        if abs(cur - tgt) >= threshold:
            hits.append(Hit(kind="drift", ticker=t, value=cur - tgt, threshold=threshold,
                            text=f"{t} is {cur:.0%} vs target {tgt:.0%}"))
    for ac, (cur, tgt) in by_class.items():
        if abs(cur - tgt) >= threshold:
            hits.append(Hit(kind="drift", ticker=None, value=cur - tgt, threshold=threshold,
                            text=f"{ac.capitalize()} drifted to {cur:.0%} vs target {tgt:.0%}"))
    return hits


def cap_hits(weights: dict[str, float], mandate: Mandate, catalogue: dict[str, Instrument]) -> list[Hit]:
    out = []
    for t, w in weights.items():
        inst = catalogue.get(t)
        if not inst:
            continue
        cap = mandate.caps.per_stock if inst.kind == "stock" else mandate.caps.per_fund
        if w > cap + 1e-6:
            out.append(Hit(kind="cap_breach", ticker=t, value=w, threshold=cap, text=f"{t} at {w:.1%} is over its {cap:.0%} cap"))
    return out


def price_move_hits(day_returns: dict[str, float], since_review: dict[str, float], day_thr: float,
                    review_thr: float) -> list[Hit]:
    out = []
    for t, r in day_returns.items():
        if abs(r) >= day_thr:
            out.append(Hit(kind="price_move", ticker=t, value=r, threshold=day_thr,
                           text=f"{t} {'rose' if r > 0 else 'fell'} {abs(r):.1%} today"))
    for t, r in since_review.items():
        if abs(r) >= review_thr and not any(h.ticker == t for h in out):
            out.append(Hit(kind="price_move", ticker=t, value=r, threshold=review_thr,
                           text=f"{t} is {'up' if r > 0 else 'down'} {abs(r):.1%} since the last review"))
    return out


def nav_drop_hit(nav: float, nav_at_last_review: float | None, threshold: float) -> list[Hit]:
    if not nav_at_last_review:
        return []
    change = nav / nav_at_last_review - 1
    if change <= -threshold:
        return [Hit(kind="nav_drop", ticker=None, value=change, threshold=threshold,
                    text=f"Portfolio is {abs(change):.1%} below its value at the last review")]
    return []


def corr_regime_hit(avg_now: float, avg_6m_ago: float | None, threshold: float) -> list[Hit]:
    if avg_6m_ago is not None and avg_now - avg_6m_ago > threshold:
        return [Hit(kind="corr_regime", ticker=None, value=avg_now - avg_6m_ago, threshold=threshold,
                    text=f"Holdings are moving together more (avg correlation {avg_now:.2f} vs {avg_6m_ago:.2f})")]
    return []
