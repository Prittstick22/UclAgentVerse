"""Cooldowns and grouping so triggers don't flood the agents. Owner: Cem."""
from __future__ import annotations

from app.monitors.rules import Hit


class Cooldowns:
    def __init__(self, cooldown_days: int, fold_into_review_days: int):
        self.cooldown_days = cooldown_days
        self.fold_days = fold_into_review_days
        self._last_run_idx: dict[str, int] = {}

    def filter(self, hits: list[Hit], day_idx: int, days_to_next_review: int) -> list[Hit]:
        """Drop hits in cooldown; corr_regime never runs ad hoc; fold into review if due within fold_days."""
        out = []
        for h in hits:
            if h.kind == "corr_regime":
                continue
            key = h.ticker or f"portfolio:{h.kind}"
            last = self._last_run_idx.get(key)
            if last is not None and day_idx - last < self.cooldown_days:
                continue
            out.append(h)
        if out and days_to_next_review <= self.fold_days and all(h.kind not in ("cap_breach",) for h in out):
            return []  # folded into the upcoming scheduled review
        for h in out:
            self._last_run_idx[h.ticker or f"portfolio:{h.kind}"] = day_idx
        return out


def primary_kind(hits: list[Hit]) -> str:
    order = ["cap_breach", "nav_drop", "price_move", "news", "drift"]
    for k in order:
        if any(h.kind == k for h in hits):
            return {"cap_breach": "cap_breach", "drift": "drift"}.get(k, k)
    return "review"


def describe(hits: list[Hit]) -> str:
    if not hits:
        return "Scheduled fortnightly review"
    if len(hits) > 3:
        return f"{len(hits)} triggers today, grouped into one run: " + "; ".join(h.text for h in hits[:3]) + "…"
    return "; ".join(h.text for h in hits)
