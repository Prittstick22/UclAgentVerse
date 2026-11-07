"""Monitor spec templates for agent-designed monitors (docs/05-agent-system.md §8). Owner: Cem (runner) + Dev (designer).

TODO(issue: adaptive monitors): runner that evaluates specs daily, shadow mode, activation rule.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Template = Literal["price_threshold", "drift_band", "news_entity", "filing_appears", "correlation_jump",
                   "earnings_window", "nav_drop"]


class MonitorSpec(BaseModel):
    monitor_id: str
    investment_case_id: str | None = None
    question: str
    template: Template
    entities: list[str] = Field(default_factory=list)
    trigger: str                      # e.g. "relevance >= 0.7", "move <= -0.08"
    schedule: Literal["daily", "weekly"] = "daily"
    on_trigger: Literal["trigger_pipeline", "note_for_review"] = "trigger_pipeline"
    review_after_days: int = 30
    status: Literal["shadow", "active", "disabled"] = "shadow"
    shadow_days_remaining: int = 10
