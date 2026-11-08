"""Validate live visitor edits and retain immutable mandate versions (#8)."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from app.config import policy
from app.schemas import Mandate

if TYPE_CHECKING:
    from app.container import AppState


def validate(mandate: Mandate, current: Mandate | None = None) -> dict[str, str]:
    errors: dict[str, str] = {}
    limits = policy()[mandate.profile]
    if current is not None:
        if mandate.profile != current.profile:
            errors["profile"] = "Use the quiz to change your risk profile."
        if mandate.version != current.version:
            errors["version"] = "Reload the latest mandate before editing."
    for asset in ("equity", "bond"):
        low, high = getattr(mandate.ranges, asset)
        floor, ceiling = limits[asset]
        if not all(math.isfinite(x) for x in (low, high)) or not floor <= low <= high <= ceiling:
            errors[f"ranges.{asset}"] = f"Choose an ordered range within [{floor}, {ceiling}]."
    cash = mandate.ranges.cash_min
    if not math.isfinite(cash) or not limits["cash_min"] <= cash <= 1:
        errors["ranges.cash_min"] = f"Cash must be between {limits['cash_min']} and 1."
    elif mandate.ranges.equity[0] + mandate.ranges.bond[0] + cash > 1 + 1e-9:
        errors["ranges.cash_min"] = "Minimum equity, bond and cash weights cannot total more than 1."
    for name, value in mandate.caps.model_dump().items():
        if not math.isfinite(value) or not 0 <= value <= limits[name]:
            errors[f"caps.{name}"] = f"Choose a cap between 0 and {limits[name]}."
    for name in ("starting_amount_gbp", "monthly_contribution_gbp"):
        value = getattr(mandate.goal, name)
        if not math.isfinite(value) or value < 0:
            errors[f"goal.{name}"] = "Enter a finite, non-negative amount."
    if mandate.review_every_n_days < 1:
        errors["review_every_n_days"] = "Review cadence must be at least one trading day."
    for name, value in mandate.triggers.model_dump().items():
        if not math.isfinite(value) or not 0 <= value <= 1:
            errors[f"triggers.{name}"] = "Enter a finite fraction between 0 and 1."
    turnover = mandate.approval.batch_auto_approve_turnover_max
    if not math.isfinite(turnover) or not 0 <= turnover <= 1:
        errors["approval.batch_auto_approve_turnover_max"] = "Enter a finite fraction between 0 and 1."
    return errors


def save(state: AppState, mandate: Mandate) -> Mandate:
    """Caller holds mandate_lock; write history/latest atomically before changing memory."""
    previous = state.mandate
    saved = mandate.model_copy(update={"version": previous.version + 1}, deep=True)
    state.db.execute(
        "INSERT INTO kv(ns, key, json) VALUES ('mandate', ?, ?), ('mandate', ?, ?), ('mandate', ?, ?) "
        "ON CONFLICT(ns, key) DO UPDATE SET json=excluded.json WHERE excluded.key='latest'",
        (str(previous.version), previous.model_dump_json(), str(saved.version), saved.model_dump_json(),
         "latest", saved.model_dump_json()),
    )
    state.mandate = saved
    state.events.emit("mandate.updated", title="Live mandate saved",
                      payload={"version": saved.version, "profile": saved.profile})
    return saved
