"""Structured outputs for agents. Keep these Gemini-schema friendly (no free-form dicts → use *_json strings)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    tool: str
    args_json: str = "{}"          # JSON object as a string (Gemini response_schema can't do open dicts)


class SpawnRequest(BaseModel):
    role: str
    question: str
    purpose: str
    deep: bool = False


class Finding(BaseModel):
    claim: str
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: Literal["low", "med", "high"] = "med"
    uncertainties: list[str] = Field(default_factory=list)
    recommendation: str | None = None


class Decision(BaseModel):
    action: Literal["maintain", "adjust", "investigate_further"]
    reason: str
    evidence_ids: list[str] = Field(default_factory=list)


class Verdict(BaseModel):
    status: Literal["pass", "fail", "pass_with_flags"]
    issues: list[str] = Field(default_factory=list)
    required_changes: list[str] = Field(default_factory=list)


class View(BaseModel):
    """An agent's directional view on one ticker for the next ~2 weeks (#74). No numbers: code sizes it."""
    ticker: str
    direction: Literal["up", "down", "neutral"]
    confidence: Literal["low", "med", "high"] = "low"
    horizon_days: int = 10
    evidence_ids: list[str] = Field(default_factory=list)


class AgentFinal(BaseModel):
    findings: list[Finding] = Field(default_factory=list)
    decision: Decision | None = None        # lead
    verdict: Verdict | None = None          # assurance roles
    text: str | None = None                 # explainer / chat / profiler
    views: list[View] = Field(default_factory=list)   # stock_analyst / news_analyst only (#74)


class AgentStep(BaseModel):
    """What an agent returns each turn. The supervisor executes tool_calls and spawns, then calls it again."""
    message: str = ""                        # short, user-visible explanation (NOT raw chain of thought)
    tool_calls: list[ToolCall] = Field(default_factory=list)
    spawns: list[SpawnRequest] = Field(default_factory=list)
    final: AgentFinal | None = None


class InvestmentCase(BaseModel):
    case_id: str
    ticker: str
    purpose: str
    evidence_ids: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    reconsider_if: list[str] = Field(default_factory=list)
    version: int = 1
